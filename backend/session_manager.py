"""
Session Manager — Smart Classroom Manager
==========================================
Manages the lifecycle of a class session:
  - Start / Stop
  - Present / Late / Absent classification
  - Auto-end when duration expires
  - Persists session records to MongoDB
"""

import threading
import time
from datetime import datetime

import shared_state
from database.mongo_client import mongo


class SessionManager:
    """
    Controls a single active session at a time.

    Attendance rules:
      - Recognized within attendance_window  → PRESENT
      - Recognized after  attendance_window but before duration → LATE
      - Never recognized during session → ABSENT (computed at end)
    """

    def __init__(self, face_manager):
        # Reference to FaceManager so we can compute absent list on stop
        self.face_manager = face_manager

        # Lock for thread-safe state changes
        self._lock = threading.Lock()

        # Internal session state
        self._session_id = None
        self._start_time = None
        self._duration_minutes = 60
        self._window_minutes = 10
        self._auto_end_thread = None

    # ----------------------------------------------------------
    # SESSION LIFECYCLE
    # ----------------------------------------------------------

    def start_session(self, duration_minutes: int, window_minutes: int) -> dict:
        """
        Start a new class session.
        Returns the session dict or raises if one is already active.
        """
        with self._lock:
            if shared_state.active_session is not None:
                raise ValueError("A session is already active. Stop it first.")

            self._duration_minutes = duration_minutes
            self._window_minutes = window_minutes
            self._start_time = datetime.utcnow()

            session_doc = {
                "start_time": self._start_time.isoformat(),
                "end_time": None,
                "duration_minutes": duration_minutes,
                "window_minutes": window_minutes,
                "status": "active",
                "present_count": 0,
                "late_count": 0,
                "absent_count": 0,
                "total_students": self.face_manager.get_total_students()
            }

            # Persist to MongoDB
            self._session_id = mongo.create_session(session_doc)
            session_doc["session_id"] = self._session_id

            # Update global shared state
            shared_state.active_session = {
                "session_id": self._session_id,
                "start_time": self._start_time.isoformat(),
                "duration_minutes": duration_minutes,
                "window_minutes": window_minutes,
                "status": "active"
            }
            shared_state.session_attendance = {}

            # Log activity
            self._log_activity("Session started", "session")

            print(f"[SessionManager] Session started: {self._session_id}")

        # Start auto-end timer in a daemon thread
        self._auto_end_thread = threading.Thread(
            target=self._auto_end_loop, daemon=True
        )
        self._auto_end_thread.start()

        return shared_state.active_session

    def stop_session(self) -> dict:
        """
        Stop the current session and compute final attendance.
        Returns session summary.
        """
        with self._lock:
            if shared_state.active_session is None:
                raise ValueError("No active session to stop.")

            end_time = datetime.utcnow()
            session_id = self._session_id

            # --- Compute absent list ---
            all_students = self.face_manager.get_all_students()
            present_names = {
                name for name, rec in shared_state.session_attendance.items()
                if rec["status"] in ("Present", "Late")
            }

            for student in all_students:
                name = student["name"]
                if name not in present_names:
                    shared_state.session_attendance[name] = {
                        "status": "Absent",
                        "timestamp": None,
                        "roll_no": student.get("roll_no", ""),
                        "prn": student.get("prn", "")
                    }
                    # Persist to MongoDB
                    mongo.save_attendance_record(
                        session_id, name,
                        student.get("roll_no", ""),
                        student.get("prn", ""),
                        "Absent", None
                    )

            # --- Compute counts ---
            present_count = sum(
                1 for r in shared_state.session_attendance.values()
                if r["status"] == "Present"
            )
            late_count = sum(
                1 for r in shared_state.session_attendance.values()
                if r["status"] == "Late"
            )
            absent_count = sum(
                1 for r in shared_state.session_attendance.values()
                if r["status"] == "Absent"
            )

            # --- Update MongoDB session ---
            actual_duration = int(
                (end_time - self._start_time).total_seconds() / 60
            ) if self._start_time else self._duration_minutes

            mongo.update_session(session_id, {
                "end_time": end_time.isoformat(),
                "status": "completed",
                "present_count": present_count,
                "late_count": late_count,
                "absent_count": absent_count,
                "actual_duration_minutes": actual_duration
            })

            # --- Clear shared state ---
            summary = {
                "session_id": session_id,
                "start_time": self._start_time.isoformat() if self._start_time else None,
                "end_time": end_time.isoformat(),
                "present_count": present_count,
                "late_count": late_count,
                "absent_count": absent_count
            }

            shared_state.active_session = None
            self._session_id = None
            self._start_time = None

            self._log_activity("Session ended", "session")
            print(f"[SessionManager] Session stopped. P:{present_count} L:{late_count} A:{absent_count}")

        return summary

    def get_status(self) -> dict:
        """Return current session status with elapsed/remaining time."""
        if shared_state.active_session is None:
            return {"status": "idle", "session": None}

        elapsed_seconds = int(
            (datetime.utcnow() - self._start_time).total_seconds()
        ) if self._start_time else 0

        remaining_seconds = max(
            0,
            self._duration_minutes * 60 - elapsed_seconds
        )

        # Count live attendees
        present = sum(
            1 for r in shared_state.session_attendance.values()
            if r["status"] == "Present"
        )
        late = sum(
            1 for r in shared_state.session_attendance.values()
            if r["status"] == "Late"
        )

        return {
            "status": "active",
            "session": shared_state.active_session,
            "elapsed_seconds": elapsed_seconds,
            "remaining_seconds": remaining_seconds,
            "occupancy": shared_state.occupancy_count,
            "present_count": present,
            "late_count": late,
            "detected_count": shared_state.occupancy_count
        }

    # ----------------------------------------------------------
    # ATTENDANCE MARKING
    # ----------------------------------------------------------

    def mark_attendance(self, name: str, roll_no: str, prn: str):
        """
        Called by async_detection when a face is recognized.
        Determines PRESENT vs LATE based on window.
        """
        if shared_state.active_session is None:
            return  # No session active — don't mark

        if name == "Unknown":
            return

        # Don't re-mark if already marked
        if name in shared_state.session_attendance:
            return

        elapsed_minutes = 0
        if self._start_time:
            elapsed_minutes = (
                datetime.utcnow() - self._start_time
            ).total_seconds() / 60

        status = "Present" if elapsed_minutes <= self._window_minutes else "Late"
        timestamp = datetime.utcnow().isoformat()

        shared_state.session_attendance[name] = {
            "status": status,
            "timestamp": timestamp,
            "roll_no": roll_no,
            "prn": prn
        }

        # Persist to MongoDB
        mongo.save_attendance_record(
            self._session_id, name, roll_no, prn, status, timestamp
        )

        # Log activity
        self._log_activity(f"{name} marked {status}", "attendance")
        print(f"[SessionManager] {name} → {status}")

    # ----------------------------------------------------------
    # AUTO-END LOOP
    # ----------------------------------------------------------

    def _auto_end_loop(self):
        """Background thread — auto-stops session when duration expires."""
        while True:
            time.sleep(5)
            with self._lock:
                if shared_state.active_session is None:
                    break  # Session was manually stopped

                if self._start_time is None:
                    break

                elapsed = (datetime.utcnow() - self._start_time).total_seconds()
                if elapsed >= self._duration_minutes * 60:
                    print("[SessionManager] Auto-ending session (duration expired).")
                    break  # Will call stop below

            # Auto-stop (outside lock to avoid deadlock)
            if shared_state.active_session is not None and self._start_time:
                elapsed = (datetime.utcnow() - self._start_time).total_seconds()
                if elapsed >= self._duration_minutes * 60:
                    try:
                        self.stop_session()
                    except Exception as e:
                        print(f"[SessionManager] Auto-stop error: {e}")
                    break

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def _log_activity(self, message: str, activity_type: str):
        """Add entry to the global activity log."""
        import time as t
        entry = {
            "timestamp": t.strftime("%H:%M:%S"),
            "message": message,
            "type": activity_type
        }
        shared_state.activity_log.insert(0, entry)
        # Keep log trimmed
        if len(shared_state.activity_log) > 100:
            shared_state.activity_log.pop()


# Singleton — initialized in main.py after face_manager is ready
session_manager = None
