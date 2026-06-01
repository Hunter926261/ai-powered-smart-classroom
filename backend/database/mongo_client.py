"""
MongoDB Client — Smart Classroom Manager
========================================
Primary database for all collections:
  students, sessions, attendance, attention_logs, iot_logs

MongoDB is the ONLY storage backend (SQLite removed).
CSV is export-only, never written during operation.
"""

from datetime import datetime, timezone
from bson import ObjectId

try:
    from pymongo import MongoClient as PyMongoClient
    from pymongo.errors import ServerSelectionTimeoutError
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

from config import MONGO_URI, MONGO_DB


def _to_str_id(doc):
    """Convert ObjectId _id to string for JSON serialization."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


class MongoDBClient:
    """
    MongoDB client wrapper.
    Falls back gracefully (no-ops) if MongoDB is not reachable.
    """

    def __init__(self):
        self.available = False
        self.db = None

        if not MONGO_AVAILABLE:
            print("[MongoDB] pymongo not installed — MongoDB disabled.")
            return

        try:
            # Short timeout so startup isn't blocked if Mongo is down
            client = PyMongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            # Ping to verify connection
            client.admin.command("ping")
            self.db = client[MONGO_DB]
            self.available = True
            print(f"[MongoDB] Connected to '{MONGO_DB}' at {MONGO_URI}")
            self._ensure_indexes()
        except Exception as e:
            print(f"[MongoDB] Connection failed: {e}")

    def _ensure_indexes(self):
        """Create indexes for performance."""
        if not self.available:
            return
        # roll_no must be unique per student
        self.db.students.create_index("roll_no", unique=True)
        # prn: sparse (not unique) — multiple students can have empty prn=""
        self.db.students.create_index("prn", sparse=True)
        self.db.sessions.create_index("start_time")
        self.db.attendance.create_index([("session_id", 1), ("student_name", 1)])
        self.db.iot_logs.create_index("timestamp")

    # ============================================================
    # STUDENT OPERATIONS
    # ============================================================

    def upsert_student(self, name, roll_no, prn, batch, photo_path="",
                       embeddings=None, avg_embedding=None):
        """
        Insert or update a student record.
        embeddings: list of per-pose embeddings (optional — used by multi-pose registration)
        avg_embedding: mean embedding across all poses (optional)
        """
        if not self.available:
            return None

        update_fields = {
            "name": name,
            "roll_no": roll_no,
            "prn": prn,
            "batch": batch,
            "photo_path": photo_path,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        # Store multi-pose embeddings in MongoDB if provided
        if embeddings is not None:
            update_fields["embeddings"] = embeddings
        if avg_embedding is not None:
            update_fields["avg_embedding"] = avg_embedding

        result = self.db.students.update_one(
            {"roll_no": roll_no},
            {"$set": update_fields,
             "$setOnInsert": {"registered_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        return str(result.upserted_id) if result.upserted_id else roll_no

    def update_student_embeddings(self, name, embeddings, avg_embedding):
        """Update face embeddings for an existing student (after re-registration)."""
        if not self.available:
            return
        self.db.students.update_one(
            {"name": name},
            {"$set": {
                "embeddings": embeddings,
                "avg_embedding": avg_embedding,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )

    def get_all_students(self):
        """Return all registered students (without raw embedding bytes for speed)."""
        if not self.available:
            return []
        docs = list(self.db.students.find({}, {"_id": 0, "embeddings": 0, "avg_embedding": 0}))
        return docs

    def delete_student(self, roll_no):
        """Delete a student by roll_no."""
        if not self.available:
            return False
        result = self.db.students.delete_one({"roll_no": roll_no})
        return result.deleted_count > 0

    def get_student(self, roll_no):
        """Get a single student by roll_no."""
        if not self.available:
            return None
        return self.db.students.find_one({"roll_no": roll_no}, {"_id": 0})

    def get_student_by_name(self, name):
        """Get a single student by name (for embedding lookup)."""
        if not self.available:
            return None
        return self.db.students.find_one({"name": name}, {"_id": 0})

    # ============================================================
    # SESSION OPERATIONS
    # ============================================================

    def create_session(self, session_data: dict) -> str:
        """Insert a new session document. Returns session_id string."""
        if not self.available:
            return ""
        result = self.db.sessions.insert_one(session_data)
        return str(result.inserted_id)

    def update_session(self, session_id: str, updates: dict):
        """Update an existing session by ID."""
        if not self.available:
            return
        try:
            self.db.sessions.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": updates}
            )
        except Exception as e:
            print(f"[MongoDB] update_session error: {e}")

    def save_avg_attention_to_session(self, session_id: str, avg_attention: float):
        """Save computed average attention score to the session document on stop."""
        if not self.available:
            return
        try:
            self.db.sessions.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {"avg_attention": round(avg_attention, 1)}}
            )
        except Exception as e:
            print(f"[MongoDB] save_avg_attention error: {e}")

    def get_session(self, session_id: str) -> dict:
        """Get a session by its ID."""
        if not self.available:
            return {}
        try:
            doc = self.db.sessions.find_one({"_id": ObjectId(session_id)})
            return _to_str_id(doc) if doc else {}
        except Exception as e:
            print(f"[MongoDB] get_session error: {e}")
            return {}

    def get_all_sessions(self, limit=50) -> list:
        """Return recent sessions ordered newest first."""
        if not self.available:
            return []
        docs = list(
            self.db.sessions.find({})
            .sort("start_time", -1)
            .limit(limit)
        )
        return [_to_str_id(d) for d in docs]

    # ============================================================
    # ATTENDANCE OPERATIONS
    # ============================================================

    def save_attendance_record(self, session_id, student_name, roll_no, prn,
                                status, timestamp):
        """Save/update an attendance record for a session."""
        if not self.available:
            return
        self.db.attendance.update_one(
            {"session_id": session_id, "student_name": student_name},
            {"$set": {
                "session_id": session_id,
                "student_name": student_name,
                "roll_no": roll_no,
                "prn": prn,
                "status": status,
                "timestamp": timestamp
            }},
            upsert=True
        )

    def get_session_attendance(self, session_id) -> list:
        """Get all attendance records for a session."""
        if not self.available:
            return []
        return list(self.db.attendance.find(
            {"session_id": session_id}, {"_id": 0}
        ))

    def get_all_attendance(self) -> list:
        """Get all attendance records across all sessions (most recent first)."""
        if not self.available:
            return []
        return list(self.db.attendance.find({}, {"_id": 0}).sort("timestamp", -1).limit(500))

    def count_today_attendance(self) -> int:
        """Count distinct present/late students marked today."""
        if not self.available:
            return 0
        today = datetime.now().strftime("%Y-%m-%d")
        return self.db.attendance.count_documents({
            "status": {"$in": ["Present", "Late"]},
            "timestamp": {"$regex": f"^{today}"}
        })

    # ============================================================
    # ATTENTION / ANALYTICS
    # ============================================================

    def save_attention_log(self, session_id, student_name, score,
                            phone_detected, phone_count,
                            head_pose_score=None, face_visible_ratio=None):
        """Upsert attention log for a student in a session."""
        if not self.available:
            return
        update_doc = {
            "$set": {
                "session_id": session_id,
                "student_name": student_name,
                "score": score,
                "phone_detected": phone_detected,
                "last_update": datetime.now(timezone.utc).isoformat()
            },
            "$inc": {"phone_count": 1 if phone_detected else 0}
        }
        # Add head_pose and face_visibility if provided
        if head_pose_score is not None:
            update_doc["$set"]["head_pose_score"] = head_pose_score
        if face_visible_ratio is not None:
            update_doc["$set"]["face_visible_ratio"] = face_visible_ratio

        self.db.attention_logs.update_one(
            {"session_id": session_id, "student_name": student_name},
            update_doc,
            upsert=True
        )

    def get_session_analytics(self, session_id) -> list:
        """Get attention analytics for a session."""
        if not self.available:
            return []
        return list(self.db.attention_logs.find(
            {"session_id": session_id}, {"_id": 0}
        ))

    # ============================================================
    # IOT LOGS
    # ============================================================

    def log_iot_action(self, device, action, mode):
        """Insert an IoT activity log entry."""
        if not self.available:
            return
        self.db.iot_logs.insert_one({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device": device,
            "action": action,
            "mode": mode
        })

    def get_recent_iot_logs(self, limit=20) -> list:
        """Return recent IoT activity logs."""
        if not self.available:
            return []
        docs = list(
            self.db.iot_logs.find({}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return docs


# Singleton instance
mongo = MongoDBClient()
