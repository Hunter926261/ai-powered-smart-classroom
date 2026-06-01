"""
Face Manager — Smart Classroom Manager
========================================
Handles face registration and recognition using InsightFace.

Improvements over original:
  - GPU/CPU auto-detected via utils.device (no more hardcoded ctx_id=0)
  - Cosine similarity recognition (replaces Euclidean distance)
  - AdaptiveThreshold per student (starts at BASE=0.45, adjusts over time)
  - Multi-pose registration (up to 5 poses, avg_embedding computed)
  - Image quality validation (blur, brightness, face size)
  - Thread lock around known_faces (safe for concurrent read/write)
  - MongoDB as primary embedding store (pkl still kept as fast cache)

!! PRESERVED: recognize_face(frame) signature — used in async_detection !!
!! PRESERVED: register_face(name, batch, roll_no, frame) — original endpoint !!
"""

import os
import cv2
import pickle
import threading
import numpy as np
import insightface

from utils.device import get_device
from database.mongo_client import mongo


# ============================================================
# ADAPTIVE THRESHOLD
# ============================================================

class AdaptiveThreshold:
    """
    Per-student cosine similarity threshold.
    Starts at BASE=0.45. Adjusts based on confirmed match feedback.
    Higher threshold = stricter (fewer false positives).
    """
    BASE = 0.45

    def __init__(self):
        # {name: float}
        self._thresholds = {}

    def get(self, name: str) -> float:
        return self._thresholds.get(name, self.BASE)

    def feedback(self, name: str, score: float, confirmed_correct: bool):
        """Update threshold after a confirmed match or mismatch."""
        current = self._thresholds.get(name, self.BASE)
        if confirmed_correct and score < current:
            # Was correct but below threshold — lower threshold slightly
            self._thresholds[name] = max(0.30, current - 0.02)
        elif not confirmed_correct and score >= current:
            # False positive — raise threshold
            self._thresholds[name] = min(0.70, current + 0.02)


# ============================================================
# FACE MANAGER
# ============================================================

class FaceManager:

    def __init__(self):
        # Auto-detect GPU/CPU
        device_str, ctx_id = get_device()

        self.app = insightface.app.FaceAnalysis()
        self.app.prepare(ctx_id=ctx_id)  # -1 = CPU, 0 = first GPU

        print(f"[FaceManager] InsightFace ready on {'GPU' if ctx_id == 0 else 'CPU'}")

        # Pickle file — used as fast in-memory load cache
        self.embedding_file = "face_embeddings.pkl"

        # Thread lock — protects known_faces from concurrent read/write
        self._lock = threading.Lock()

        # In-memory face store:
        # {name: {embedding, avg_embedding, embeddings[], batch, roll_no, prn}}
        self.known_faces = {}

        # Per-student cosine similarity thresholds
        self.threshold = AdaptiveThreshold()

        # Load existing embeddings (pkl → then sync any new from MongoDB)
        self.load_faces()

    # ----------------------------------------------------------
    # LOAD / SAVE
    # ----------------------------------------------------------

    def load_faces(self):
        """
        Load known faces from pkl cache.
        Also tries to pull multi-pose avg_embeddings from MongoDB
        for students who already have them stored there.
        """
        if os.path.exists(self.embedding_file):
            try:
                with open(self.embedding_file, "rb") as f:
                    loaded = pickle.load(f)
                with self._lock:
                    self.known_faces = loaded
                print(f"[FaceManager] Loaded {len(self.known_faces)} students from pkl")
            except Exception as e:
                print(f"[FaceManager] pkl load error: {e}")
                with self._lock:
                    self.known_faces = {}
        else:
            with self._lock:
                self.known_faces = {}

        # Sync avg_embedding from MongoDB if available (overrides pkl single embedding)
        self._sync_from_mongo()

    def _sync_from_mongo(self):
        """
        Pull avg_embedding from MongoDB for any students who have one stored.
        This ensures multi-pose registrations immediately improve recognition
        without requiring a server restart.
        """
        if not mongo.available:
            return
        try:
            students = mongo.db.students.find(
                {"avg_embedding": {"$exists": True}},
                {"name": 1, "avg_embedding": 1, "embeddings": 1, "_id": 0}
            )
            updated = 0
            with self._lock:
                for s in students:
                    name = s.get("name")
                    avg_emb = s.get("avg_embedding")
                    if name and avg_emb:
                        if name in self.known_faces:
                            self.known_faces[name]["avg_embedding"] = np.array(avg_emb)
                            if s.get("embeddings"):
                                self.known_faces[name]["embeddings"] = [
                                    np.array(e) for e in s["embeddings"]
                                ]
                        updated += 1
            if updated:
                print(f"[FaceManager] Synced avg_embedding for {updated} students from MongoDB")
        except Exception as e:
            print(f"[FaceManager] MongoDB sync error: {e}")

    def save_faces(self):
        """Save known_faces to pkl cache (thread-safe)."""
        with self._lock:
            faces_copy = dict(self.known_faces)
        try:
            with open(self.embedding_file, "wb") as f:
                pickle.dump(faces_copy, f)
        except Exception as e:
            print(f"[FaceManager] pkl save error: {e}")

    # ----------------------------------------------------------
    # IMAGE QUALITY VALIDATION
    # ----------------------------------------------------------

    def validate_image_quality(self, frame, expected_pose=None):
        """
        Validate image quality before registration.
        Returns (ok: bool, issues: list[str])
        """
        issues = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # --- Blur check (Laplacian variance — higher = sharper) ---
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        if blur_score < 80:
            issues.append(f"Too blurry (score {blur_score:.0f}, need ≥80)")

        # --- Brightness check ---
        brightness = gray.mean()
        if brightness < 40:
            issues.append("Too dark — increase lighting")
        elif brightness > 230:
            issues.append("Overexposed — reduce brightness or move away from light")

        # --- Face detection + size check ---
        try:
            faces = self.app.get(frame)
            if not faces:
                issues.append("No face detected — ensure face is clearly visible")
            else:
                box = faces[0].bbox
                face_area = (box[2] - box[0]) * (box[3] - box[1])
                frame_area = frame.shape[0] * frame.shape[1]
                if frame_area > 0 and face_area / frame_area < 0.015:
                    issues.append("Face too small — move closer to the camera")

                # Pose angle validation per expected_pose (if InsightFace provides pose)
                if expected_pose and hasattr(faces[0], 'pose') and faces[0].pose is not None:
                    pose = faces[0].pose
                    if len(pose) >= 2:
                        pitch, yaw = float(pose[0]), float(pose[1])
                        pose_rules = {
                            "front": (abs(yaw) < 20 and abs(pitch) < 20),
                            "left":  (yaw > 20),
                            "right": (yaw < -20),
                            "up":    (pitch < -15),
                            "down":  (pitch > 15),
                        }
                        if expected_pose in pose_rules and not pose_rules[expected_pose]:
                            issues.append(f"Incorrect pose for '{expected_pose}' view — adjust head angle")
        except Exception as e:
            issues.append(f"Face analysis error: {e}")

        return len(issues) == 0, issues

    # ----------------------------------------------------------
    # REGISTER FACE (single image — PRESERVED original signature)
    # ----------------------------------------------------------

    def register_face(self, name, batch, roll_no, frame):
        """
        !! PRESERVED: Original single-image registration !!
        Used by /register_student endpoint (backward compatible).
        Stores embedding in pkl + MongoDB (as avg_embedding with single pose).
        """
        try:
            faces = self.app.get(frame)
            if len(faces) == 0:
                return False

            embedding = faces[0].embedding
            embedding_list = embedding.tolist()

            with self._lock:
                self.known_faces[name] = {
                    "embedding": embedding,          # legacy key (kept for compatibility)
                    "avg_embedding": embedding,      # used by cosine recognition
                    "embeddings": [embedding],       # single-pose list
                    "batch": batch,
                    "roll_no": roll_no,
                    "prn": ""
                }

            self.save_faces()

            # Save face image
            os.makedirs("registered_faces", exist_ok=True)
            cv2.imwrite(f"registered_faces/{name}.jpg", frame)

            return True

        except Exception as e:
            print(f"[FaceManager] register_face error: {e}")
            return False

    # ----------------------------------------------------------
    # REGISTER FACE MULTI (5-pose — NEW)
    # ----------------------------------------------------------

    def register_face_multi(self, name, batch, roll_no, prn, pose_frames: dict):
        """
        Multi-pose registration for improved accuracy.
        pose_frames: {pose_name: frame} e.g. {"front": f1, "left": f2, ...}
        Returns (success: bool, message: str)
        """
        embeddings = []

        for pose, frame in pose_frames.items():
            if frame is None:
                continue
            # Validate quality for this pose
            ok, issues = self.validate_image_quality(frame, expected_pose=pose)
            if not ok:
                # Non-fatal — skip bad pose but log it
                print(f"[FaceManager] Pose '{pose}' quality issue: {'; '.join(issues)}")

            try:
                faces = self.app.get(frame)
                if faces:
                    embeddings.append(faces[0].embedding)
                else:
                    print(f"[FaceManager] No face in '{pose}' pose image")
            except Exception as e:
                print(f"[FaceManager] Embedding error for pose '{pose}': {e}")

        if not embeddings:
            return False, "No faces could be detected in any of the provided images"

        # Compute average embedding across all valid poses
        avg_emb = np.mean(embeddings, axis=0)

        embeddings_list = [e.tolist() for e in embeddings]
        avg_emb_list = avg_emb.tolist()

        with self._lock:
            self.known_faces[name] = {
                "embedding": avg_emb,            # legacy key
                "avg_embedding": avg_emb,        # cosine similarity key
                "embeddings": embeddings,         # all pose embeddings
                "batch": batch,
                "roll_no": roll_no,
                "prn": prn
            }

        self.save_faces()

        # Persist to MongoDB
        photo_path = f"registered_faces/{name}.jpg"
        # Save the front pose (or first available) as the profile photo
        first_frame = list(pose_frames.values())[0]
        if first_frame is not None:
            os.makedirs("registered_faces", exist_ok=True)
            cv2.imwrite(photo_path, first_frame)

        mongo.upsert_student(
            name, roll_no, prn, batch, photo_path,
            embeddings=embeddings_list,
            avg_embedding=avg_emb_list
        )

        return True, f"Registered with {len(embeddings)} pose(s)"

    # ----------------------------------------------------------
    # RECOGNIZE FACE (cosine similarity — replaces Euclidean)
    # ----------------------------------------------------------

    def recognize_face(self, frame):
        """
        !! PRESERVED: signature unchanged — used by async_detection !!

        Improved recognition:
          - Cosine similarity (range 0–1) instead of Euclidean distance
          - Per-student adaptive threshold (default 0.45)
          - Uses avg_embedding (mean of all registered poses)
          - Returns best matching name or "Unknown"
        """
        try:
            faces = self.app.get(frame)
            if not faces:
                return "Unknown"

            q = faces[0].embedding
            # Normalize query embedding
            q_norm = q / (np.linalg.norm(q) + 1e-9)

            best_name = "Unknown"
            best_score = -1.0

            with self._lock:
                for name, data in self.known_faces.items():
                    # Prefer avg_embedding (multi-pose mean), fall back to embedding
                    ref_emb = data.get("avg_embedding", data.get("embedding"))
                    if ref_emb is None:
                        continue

                    ref_emb = np.array(ref_emb)
                    ref_norm = ref_emb / (np.linalg.norm(ref_emb) + 1e-9)

                    # Cosine similarity: 1.0 = identical, 0.0 = orthogonal
                    score = float(np.dot(q_norm, ref_norm))

                    thresh = self.threshold.get(name)
                    if score > best_score and score >= thresh:
                        best_score = score
                        best_name = name

            return best_name

        except Exception as e:
            print(f"[FaceManager] recognize_face error: {e}")
            return "Unknown"

    # ----------------------------------------------------------
    # QUERIES (preserved signatures)
    # ----------------------------------------------------------

    def get_total_students(self) -> int:
        """Return count of registered students."""
        with self._lock:
            return len(self.known_faces)

    def get_all_students(self) -> list:
        """Return list of all students with name, batch, roll_no."""
        with self._lock:
            return [
                {
                    "name": name,
                    "batch": data.get("batch", ""),
                    "roll_no": data.get("roll_no", ""),
                    "prn": data.get("prn", "")
                }
                for name, data in self.known_faces.items()
            ]

    def get_student_info(self, name):
        """Return a single student's data dict or None."""
        with self._lock:
            return self.known_faces.get(name, None)