"""
Async Detection — Smart Classroom Manager
==========================================
Background thread that reads camera frames, runs YOLO tracking,
face recognition, phone detection, and fires WebSocket events.

!! HARDWARE CRITICAL — DO NOT MODIFY detection/tracking core !!
  - Camera stream from Raspberry Pi is read via Camera class
  - YOLO GPU tracking: class 0 = person, class 67 = cell phone
  - Face recognition uses InsightFace via FaceManager
  - Attendance marking delegated to SessionManager
"""

import threading
import time
import cv2
import asyncio
from datetime import datetime

from ultralytics import YOLO

import shared_state

from face_manager import FaceManager
from attendance_manager import AttendanceManager

from event_manager import event_manager
from automation_manager import automation_manager


class AsyncDetection:

    def __init__(self, camera):

        self.camera = camera

        # !! PRESERVED: GPU-enabled YOLO model !!
        self.model = YOLO("yolov8n.pt").to("cuda")
        print("YOLO GPU Enabled")

        self.face_manager = FaceManager()
        self.attendance_manager = AttendanceManager()

        # Reference to SessionManager (set from main.py after init)
        self.session_manager = None

        # Track cache: {track_id -> {name, entry_time, last_recognition, time}}
        self.track_memory = {}

        # Track memory timeout (seconds)
        self.track_timeout = 5

        # Entry state
        self.active_tracks = set()

        # Phone detection state per track: {track_id -> last_alert_time}
        self.phone_last_alert = {}

        # Minimum seconds between phone alerts per track
        self.phone_alert_cooldown = 10

        thread = threading.Thread(target=self.detect_loop)
        thread.daemon = True
        thread.start()

    def detect_loop(self):
        """
        Main detection loop.
        !! CORE HARDWARE LOGIC — preserved from original !!
        Extended with: phone detection, session attendance, attention tracking.
        """
        frame_count = 0

        while True:

            frame = self.camera.get_frame()

            if frame is None:
                continue

            # !! PRESERVED: Update latest frame in shared state !!
            shared_state.latest_frame = frame.copy()

            # FRAME SKIPPING — process every 5th frame for performance
            frame_count += 1
            if frame_count % 5 != 0:
                continue

            # --- REMOVE EXPIRED TRACKS ---
            current_time = time.time()
            expired_tracks = [
                tid for tid, data in self.track_memory.items()
                if current_time - data["time"] > self.track_timeout
            ]
            for tid in expired_tracks:
                del self.track_memory[tid]

            # ============================================================
            # !! PRESERVED: GPU YOLO TRACKING (class 0 = person) !!
            # ============================================================
            results = self.model.track(
                frame,
                persist=True,
                classes=[0],    # person only for tracking
                verbose=False,
                device="cuda"
            )

            detections = []
            current_tracks = set()

            if results[0].boxes.id is not None:

                boxes = results[0].boxes.xyxy.cpu().numpy()
                ids = results[0].boxes.id.cpu().numpy()

                for box, track_id in zip(boxes, ids):

                    x1, y1, x2, y2 = map(int, box)
                    track_id = int(track_id)
                    current_tracks.add(track_id)

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
                    ):
                        track_data["last_recognition"] = time.time()

                        try:
                            recognized_name = self.face_manager.recognize_face(face_crop)

                            if recognized_name is not None:
                                track_data["name"] = recognized_name
                                name = recognized_name

                                # Get student info
                                student_info = self.face_manager.get_student_info(name)

                                if student_info is not None:

                                    # !! PRESERVED: Original attendance marking !!
                                    self.attendance_manager.mark_attendance(
                                        name,
                                        student_info["batch"],
                                        student_info["roll_no"]
                                    )

                                    # NEW: Session-aware attendance marking
                                    if self.session_manager is not None:
                                        self.session_manager.mark_attendance(
                                            name,
                                            student_info.get("roll_no", ""),
                                            student_info.get("prn", "")
                                        )

                                print(f"{name} Entered")

                                # !! PRESERVED: WebSocket recognition event !!
                                asyncio.run(
                                    event_manager.send_event(
                                        "recognition",
                                        {"name": name, "status": "Present"}
                                    )
                                )

                                # !! PRESERVED: Entry log !!
                                shared_state.entry_logs.append({
                                    "name": name,
                                    "time": time.strftime("%H:%M:%S")
                                })

                                # NEW: Activity log
                                shared_state.activity_log.insert(0, {
                                    "timestamp": time.strftime("%H:%M:%S"),
                                    "message": f"{name} recognized",
                                    "type": "recognition"
                                })

                        except Exception as e:
                            print("Recognition Error:", e)

                    else:
                        name = track_data["name"]

                    detections.append({
                        "id": track_id,
                        "name": name,
                        "box": [x1, y1, x2, y2]
                    })

            # ============================================================
            # PHONE DETECTION (new — YOLO class 67 = cell phone)
            # Runs as a separate quick inference pass
            # ============================================================
            self._detect_phones(frame)

            # !! PRESERVED: Exit detection !!
            exited_tracks = self.active_tracks - current_tracks
            for exited_id in exited_tracks:
                if exited_id in self.track_memory:
                    exited_name = self.track_memory[exited_id]["name"]
                    print(f"{exited_name} Exited")
                    shared_state.exit_logs.append({
                        "name": exited_name,
                        "time": time.strftime("%H:%M:%S")
                    })

            self.active_tracks = current_tracks

            # !! PRESERVED: Update latest results !!
            shared_state.latest_results = detections

            # !! PRESERVED: Occupancy event !!
            new_occupancy = len(current_tracks)
            if new_occupancy != shared_state.occupancy_count:
                shared_state.occupancy_count = new_occupancy
                asyncio.run(
                    event_manager.send_event(
                        "occupancy", {"count": new_occupancy}
                    )
                )

            # !! PRESERVED: Automation trigger !!
            if len(current_tracks) > 0:
                automation_manager.person_detected()

            time.sleep(0.01)

    def _detect_phones(self, frame):
        """
        Detect mobile phones in frame (YOLO class 67).
        Updates shared_state.phone_alerts and attention_data.
        """
        try:
            phone_results = self.model(
                frame,
                classes=[67],  # cell phone class
                verbose=False,
                device="cuda"
            )

            if phone_results[0].boxes and len(phone_results[0].boxes) > 0:
                now = time.time()
                now_str = time.strftime("%H:%M:%S")

                # Rate-limit alerts
                last = getattr(self, "_last_phone_alert", 0)
                if now - last > self.phone_alert_cooldown:
                    self._last_phone_alert = now

                    alert = {
                        "time": now_str,
                        "confidence": float(
                            phone_results[0].boxes.conf[0].cpu().numpy()
                        ),
                        "student": "Unknown"
                    }

                    # Try to attribute phone to nearest known student
                    # (simple heuristic: use most recent recognized name)
                    for track_data in self.track_memory.values():
                        if track_data["name"] != "Unknown":
                            alert["student"] = track_data["name"]
                            break

                    shared_state.phone_alerts.insert(0, alert)
                    if len(shared_state.phone_alerts) > 50:
                        shared_state.phone_alerts.pop()

                    # Update attention data
                    student_name = alert["student"]
                    if student_name not in shared_state.attention_data:
                        shared_state.attention_data[student_name] = {
                            "score": 100,
                            "phone_detected": False,
                            "phone_count": 0,
                            "last_update": now_str
                        }
                    shared_state.attention_data[student_name]["phone_detected"] = True
                    shared_state.attention_data[student_name]["phone_count"] = (
                        shared_state.attention_data[student_name].get("phone_count", 0) + 1
                    )
                    # Reduce attention score on phone detection
                    shared_state.attention_data[student_name]["score"] = max(
                        0,
                        shared_state.attention_data[student_name]["score"] - 10
                    )

                    # Fire WebSocket phone alert
                    asyncio.run(
                        event_manager.send_event("phone_alert", alert)
                    )

        except Exception as e:
            # Non-critical — don't let phone detection crash the main loop
            print(f"[PhoneDetect] Error: {e}")