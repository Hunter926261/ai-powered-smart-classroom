"""
Async Detection — Smart Classroom Manager
==========================================
Background thread that reads camera frames, runs YOLO tracking,
face recognition, phone detection, head pose scoring, and fires
WebSocket events.

!! HARDWARE CRITICAL — DO NOT MODIFY detection/tracking core !!
  - Camera stream from Raspberry Pi is read via Camera class
  - YOLO tracking: class 0 = person, class 67 = cell phone (single call)
  - Face recognition uses InsightFace via FaceManager
  - Attendance marking delegated to SessionManager

Key improvements over original:
  - GPU/CPU auto-detected via utils.device (no more hardcoded cuda)
  - asyncio.run_coroutine_threadsafe() replaces asyncio.run() from thread
  - Single YOLO call with classes=[0,67] instead of two separate calls
  - Head pose score computed from InsightFace face.pose
  - Face visibility ratio tracked per person per session
  - Phone attribution uses proximity (closest person box) not random name
  - Attention score = 0.5*head_pose + 0.2*face_visibility + 0.3*phone_score
  - Duplicate FaceManager/AttendanceManager removed (injected from main.py)
"""

import threading
import time
import asyncio
import cv2
from datetime import datetime

from ultralytics import YOLO
import numpy as np

import shared_state
from event_manager import event_manager
from automation_manager import automation_manager
from utils.device import get_device

# FaceManager and AttendanceManager are injected from main.py
# (not instantiated here — prevents duplicate objects)


# ============================================================
# ATTENTION SCORE HELPERS
# ============================================================

def _head_pose_score(pitch: float, yaw: float) -> float:
    """
    Returns 0.0–1.0: 1.0 = perfectly facing forward.
    InsightFace face.pose = [pitch, yaw, roll] in degrees.
    Weight: Head Pose = 50% of attention score.
    """
    yaw_score   = max(0.0, 1.0 - abs(yaw)   / 45.0)  # ±45° range
    pitch_score = max(0.0, 1.0 - abs(pitch) / 30.0)  # ±30° range
    return round((yaw_score + pitch_score) / 2.0, 3)


def _calculate_attention_score(
    head_pose_score: float,    # 0–1  (1 = looking forward)
    face_visible_ratio: float, # 0–1  (1 = face visible in frame always)
    phone_count: int           # cumulative phone detections this session
) -> float:
    """
    Composite attention score (0–100).
    Weights configured from user answers:
      Head Pose    = 50%
      Visibility   = 20%
      Phone usage  = 30%
    """
    W_POSE       = 0.50
    W_VISIBILITY = 0.20
    W_PHONE      = 0.30

    phone_penalty = min(0.50, phone_count * 0.05)  # max −50%
    phone_score = 1.0 - phone_penalty

    raw = (W_POSE       * head_pose_score +
           W_VISIBILITY * face_visible_ratio +
           W_PHONE      * phone_score)

    return round(max(0.0, min(100.0, raw * 100)), 1)


# ============================================================
# ASYNC DETECTION
# ============================================================

class AsyncDetection:

    def __init__(self, camera):
        self.camera = camera

        # Auto-detect GPU/CPU
        device_str, _ = get_device()
        self.device_str = device_str

        # !! PRESERVED: YOLO model load !!
        self.model = YOLO("yolov8n.pt")
        self.model.to(device_str)
        print(f"[AsyncDetection] YOLO loaded on {device_str.upper()}")

        # These are set from main.py after init to avoid duplicate instantiation
        self.face_manager = None
        self.attendance_manager = None
        self.session_manager = None

        # Track cache: {track_id -> {name, entry_time, last_recognition, time}}
        self.track_memory = {}

        # Track memory timeout (seconds without detection before forgetting a track)
        self.track_timeout = 5

        # Entry state
        self.active_tracks = set()

        # Phone alert cooldown: {track_id -> last_alert_time}
        self.phone_last_alert = {}

        # Minimum seconds between phone alerts globally
        self.phone_alert_cooldown = 10

        # Frame counter — used for per-N-frame subsampling
        self._frame_count = 0

        # Attention update broadcast every N processed frames
        self._attention_broadcast_interval = 50  # ~10s at 5fps processed

        # Store FastAPI event loop reference for thread-safe WS events
        # This is set in main.py startup after the event loop is running
        self._loop = None

        # Start detection thread
        thread = threading.Thread(target=self.detect_loop, daemon=True)
        thread.start()

    # ----------------------------------------------------------
    # THREAD-SAFE EVENT FIRING
    # ----------------------------------------------------------

    def _fire_event(self, event_type: str, data: dict):
        """
        Fire a WebSocket event from a background thread.
        Uses run_coroutine_threadsafe (not asyncio.run) to avoid
        event loop conflicts with FastAPI's running loop.
        """
        if self._loop is None:
            # Loop not yet set — skip silently (startup phase)
            return
        try:
            asyncio.run_coroutine_threadsafe(
                event_manager.send_event(event_type, data),
                self._loop
            )
        except Exception as e:
            print(f"[AsyncDetection] _fire_event error: {e}")

    # ----------------------------------------------------------
    # MAIN DETECTION LOOP
    # ----------------------------------------------------------

    def detect_loop(self):
        """
        Main detection loop.
        !! CORE HARDWARE LOGIC — preserved from original !!
        Extended with: phone detection (merged), head pose, attention tracking.
        """
        while True:
            frame = self.camera.get_frame()

            if frame is None:
                time.sleep(0.01)
                continue

            # !! PRESERVED: Update latest frame in shared state !!
            shared_state.latest_frame = frame.copy()

            # FRAME SKIPPING — process every 5th frame for performance
            self._frame_count += 1
            if self._frame_count % 5 != 0:
                continue

            # --- Remove expired tracks ---
            current_time = time.time()
            expired_tracks = [
                tid for tid, data in self.track_memory.items()
                if current_time - data["time"] > self.track_timeout
            ]
            for tid in expired_tracks:
                del self.track_memory[tid]

            # ============================================================
            # !! PRESERVED: YOLO TRACKING — person + phone in ONE call !!
            # classes=[0,67] avoids a second full-frame inference pass
            # ============================================================
            results = self.model.track(
                frame,
                persist=True,
                classes=[0, 67],    # 0=person, 67=cell phone
                verbose=False,
                device=self.device_str
            )

            detections = []
            current_tracks = set()
            person_boxes = {}   # {track_id: [x1,y1,x2,y2]} for phone proximity
            phone_boxes = []    # [[x1,y1,x2,y2, conf], ...]

            if results[0].boxes is not None:
                boxes  = results[0].boxes.xyxy.cpu().numpy()
                ids    = results[0].boxes.id
                confs  = results[0].boxes.conf.cpu().numpy()
                clss   = results[0].boxes.cls.cpu().numpy()
                ids_np = ids.cpu().numpy() if ids is not None else None

                for i, (box, cls, conf) in enumerate(zip(boxes, clss, confs)):
                    x1, y1, x2, y2 = map(int, box)
                    cls = int(cls)

                    if cls == 67:
                        # Phone detected — collect for proximity attribution later
                        phone_boxes.append([x1, y1, x2, y2, float(conf)])
                        continue

                    # cls == 0 — person
                    if ids_np is None:
                        continue
                    track_id = int(ids_np[i])
                    current_tracks.add(track_id)
                    person_boxes[track_id] = [x1, y1, x2, y2]

                    # !! PRESERVED: Smart face region (upper 45%) !!
                    face_crop = frame[
                        y1:int(y1 + (y2 - y1) * 0.45),
                        x1:x2
                    ]

                    if face_crop.size == 0:
                        continue

                    name = "Unknown"

                    # !! PRESERVED: Track memory initialization !!
                    if track_id not in self.track_memory:
                        self.track_memory[track_id] = {
                            "name": "Unknown",
                            "entry_time": time.time(),
                            "last_recognition": 0,
                            "time": time.time()
                        }

                    track_data = self.track_memory[track_id]
                    track_data["time"] = time.time()
                    name = track_data["name"]

                    # !! PRESERVED: Retry recognition for Unknown tracks !!
                    if (
                        name == "Unknown"
                        and time.time() - track_data["last_recognition"] > 2
                        and self.face_manager is not None
                    ):
                        track_data["last_recognition"] = time.time()
                        try:
                            recognized_name = self.face_manager.recognize_face(face_crop)

                            if recognized_name and recognized_name != "Unknown":
                                track_data["name"] = recognized_name
                                name = recognized_name

                                student_info = self.face_manager.get_student_info(name)

                                if student_info is not None:
                                    # !! PRESERVED: Original attendance mark (cooldown gate) !!
                                    if self.attendance_manager:
                                        self.attendance_manager.mark_attendance(
                                            name,
                                            student_info.get("batch", ""),
                                            student_info.get("roll_no", "")
                                        )

                                    # Session-aware attendance marking
                                    if self.session_manager is not None:
                                        self.session_manager.mark_attendance(
                                            name,
                                            student_info.get("roll_no", ""),
                                            student_info.get("prn", "")
                                        )

                                print(f"[Detection] {name} recognized")

                                # !! PRESERVED: WebSocket recognition event !!
                                self._fire_event("recognition", {
                                    "name": name,
                                    "status": "Present"
                                })

                                # !! PRESERVED: Entry log !!
                                shared_state.entry_logs.append({
                                    "name": name,
                                    "time": time.strftime("%H:%M:%S")
                                })

                                # Activity log
                                with shared_state._state_lock:
                                    shared_state.activity_log.insert(0, {
                                        "timestamp": time.strftime("%H:%M:%S"),
                                        "message": f"{name} recognized",
                                        "type": "recognition"
                                    })

                        except Exception as e:
                            print(f"[Detection] Recognition error: {e}")

                    else:
                        name = track_data["name"]

                    # --- Head pose scoring ---
                    self._update_head_pose(name, face_crop)

                    # --- Face visibility tracking ---
                    self._update_face_visibility(name)

                    # --- Recompute attention score ---
                    self._update_attention_score(name)

                    detections.append({
                        "id": track_id,
                        "name": name,
                        "box": [x1, y1, x2, y2]
                    })

            # --- Phone attribution and alerts ---
            if phone_boxes:
                self._handle_phones(phone_boxes, person_boxes)

            # !! PRESERVED: Exit detection !!
            exited_tracks = self.active_tracks - current_tracks
            for exited_id in exited_tracks:
                if exited_id in self.track_memory:
                    exited_name = self.track_memory[exited_id]["name"]
                    print(f"[Detection] {exited_name} exited")
                    shared_state.exit_logs.append({
                        "name": exited_name,
                        "time": time.strftime("%H:%M:%S")
                    })

            self.active_tracks = current_tracks

            # !! PRESERVED: Update latest results !!
            shared_state.latest_results = detections

            # Compute unknown_faces count from current detections
            shared_state.unknown_faces_count = sum(
                1 for d in detections if d["name"] == "Unknown"
            )

            # !! PRESERVED: Occupancy event !!
            new_occupancy = len(current_tracks)
            if new_occupancy != shared_state.occupancy_count:
                shared_state.occupancy_count = new_occupancy
                self._fire_event("occupancy", {"count": new_occupancy})

            # !! PRESERVED: Automation trigger — person present keeps devices ON !!
            if len(current_tracks) > 0:
                automation_manager.person_detected()

            # Broadcast attention update every N processed frames
            if self._frame_count % self._attention_broadcast_interval == 0:
                self._broadcast_attention_update()

            time.sleep(0.01)

    # ----------------------------------------------------------
    # HEAD POSE TRACKING
    # ----------------------------------------------------------

    def _update_head_pose(self, name: str, face_crop):
        """
        Extract head pose from InsightFace and update shared_state.head_pose_data.
        Only runs when a face is detected in the crop.
        """
        if name == "Unknown" or self.face_manager is None:
            return
        try:
            faces = self.face_manager.app.get(face_crop)
            if not faces:
                return
            face = faces[0]
            if hasattr(face, 'pose') and face.pose is not None and len(face.pose) >= 2:
                pitch, yaw = float(face.pose[0]), float(face.pose[1])
                score = _head_pose_score(pitch, yaw)
                with shared_state._state_lock:
                    shared_state.head_pose_data[name] = {
                        "pitch": pitch,
                        "yaw": yaw,
                        "score": score
                    }
        except Exception:
            pass  # Head pose is non-critical — don't crash detection loop

    # ----------------------------------------------------------
    # FACE VISIBILITY TRACKING
    # ----------------------------------------------------------

    def _update_face_visibility(self, name: str):
        """
        Track how often each named student's face is visible.
        Increments visible_frames and total_frames in shared_state.
        """
        if name == "Unknown":
            return
        with shared_state._state_lock:
            if name not in shared_state.face_visibility:
                shared_state.face_visibility[name] = {
                    "visible_frames": 0,
                    "total_frames": 0
                }
            shared_state.face_visibility[name]["visible_frames"] += 1
            shared_state.face_visibility[name]["total_frames"] += 1

    # ----------------------------------------------------------
    # ATTENTION SCORE UPDATE
    # ----------------------------------------------------------

    def _update_attention_score(self, name: str):
        """
        Recompute composite attention score for a student.
        Updates shared_state.attention_data[name].
        """
        if name == "Unknown":
            return

        # Head pose score (0–1)
        head_score = shared_state.head_pose_data.get(name, {}).get("score", 0.5)

        # Face visibility ratio (0–1)
        vis = shared_state.face_visibility.get(name, {"visible_frames": 0, "total_frames": 1})
        total = vis.get("total_frames", 1)
        visible = vis.get("visible_frames", 0)
        face_vis_ratio = visible / max(total, 1)

        # Phone count for this student
        phone_count = shared_state.attention_data.get(name, {}).get("phone_count", 0)

        score = _calculate_attention_score(head_score, face_vis_ratio, phone_count)

        with shared_state._state_lock:
            if name not in shared_state.attention_data:
                shared_state.attention_data[name] = {
                    "score": 100.0,
                    "phone_detected": False,
                    "phone_count": 0,
                    "last_update": time.strftime("%H:%M:%S")
                }
            shared_state.attention_data[name]["score"] = score
            shared_state.attention_data[name]["head_pose_score"] = head_score
            shared_state.attention_data[name]["face_visible_ratio"] = face_vis_ratio
            shared_state.attention_data[name]["last_update"] = time.strftime("%H:%M:%S")

    # ----------------------------------------------------------
    # PHONE DETECTION & ATTRIBUTION
    # ----------------------------------------------------------

    def _handle_phones(self, phone_boxes: list, person_boxes: dict):
        """
        Process phone detections:
          - Attribute phone to CLOSEST person box by centroid distance
          - Rate-limit alerts to phone_alert_cooldown seconds
          - Fire WebSocket phone_alert event
        """
        now = time.time()
        now_str = time.strftime("%H:%M:%S")

        for ph_box in phone_boxes:
            px1, py1, px2, py2, conf = ph_box
            phone_cx = (px1 + px2) / 2
            phone_cy = (py1 + py2) / 2

            # Find closest person by centroid distance
            best_track_id = None
            best_dist = float("inf")
            for tid, pbox in person_boxes.items():
                person_cx = (pbox[0] + pbox[2]) / 2
                person_cy = (pbox[1] + pbox[3]) / 2
                dist = ((phone_cx - person_cx) ** 2 + (phone_cy - person_cy) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best_track_id = tid

            # Resolve name from closest track
            student_name = "Unknown"
            if best_track_id is not None and best_track_id in self.track_memory:
                student_name = self.track_memory[best_track_id]["name"]

            # Rate-limit: per-student or global cooldown
            last = self.phone_last_alert.get(student_name, 0)
            if now - last < self.phone_alert_cooldown:
                continue  # Still in cooldown
            self.phone_last_alert[student_name] = now

            alert = {
                "time": now_str,
                "confidence": round(conf, 3),
                "student": student_name
            }

            with shared_state._state_lock:
                shared_state.phone_alerts.insert(0, alert)
                if len(shared_state.phone_alerts) > 50:
                    shared_state.phone_alerts.pop()

            # Update attention data — increment phone count
            with shared_state._state_lock:
                if student_name not in shared_state.attention_data:
                    shared_state.attention_data[student_name] = {
                        "score": 100.0,
                        "phone_detected": False,
                        "phone_count": 0,
                        "last_update": now_str
                    }
                shared_state.attention_data[student_name]["phone_detected"] = True
                shared_state.attention_data[student_name]["phone_count"] = (
                    shared_state.attention_data[student_name].get("phone_count", 0) + 1
                )
                # Recompute score after phone count increment
                pc = shared_state.attention_data[student_name]["phone_count"]
                hp = shared_state.attention_data[student_name].get("head_pose_score", 0.5)
                fv = shared_state.attention_data[student_name].get("face_visible_ratio", 0.5)
                shared_state.attention_data[student_name]["score"] = (
                    _calculate_attention_score(hp, fv, pc)
                )

            # Activity log
            with shared_state._state_lock:
                shared_state.activity_log.insert(0, {
                    "timestamp": now_str,
                    "message": f"📱 Phone detected — {student_name}",
                    "type": "phone_alert"
                })

            # Fire WebSocket event
            self._fire_event("phone_alert", alert)

    # ----------------------------------------------------------
    # ATTENTION BROADCAST
    # ----------------------------------------------------------

    def _broadcast_attention_update(self):
        """
        Fire 'attention_update' WebSocket event with current per-student data.
        Fired every ~10 seconds during an active session.
        """
        if shared_state.active_session is None:
            return

        students = []
        for name, data in shared_state.attention_data.items():
            students.append({
                "name": name,
                "score": data.get("score", 100),
                "phone_count": data.get("phone_count", 0),
                "head_pose_score": data.get("head_pose_score", 0),
                "face_visible_ratio": data.get("face_visible_ratio", 0),
                "phone_detected": data.get("phone_detected", False)
            })

        avg_score = (
            sum(s["score"] for s in students) / len(students)
            if students else 0
        )

        self._fire_event("attention_update", {
            "students": students,
            "avg_score": round(avg_score, 1)
        })