"""
Session Manager — Smart Classroom Manager
==========================================
Manages the lifecycle of a class session:
  - Start / Stop
  - Present / Late / Absent classification (configurable window)
  - Auto-end when duration expires (fixed with threading.Event)
  - Persists session records to MongoDB
  - Computes and saves avg_attention on stop
  - Fires session_update WebSocket events

!! HARDWARE: No ESP32 / Pi logic here !!
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
      - Never recognized during session → ABSENT (computed at stop)
    """

    def __init__(self, face_manager):
        # Reference to FaceManager so we can compute absent list on stop
        self.face_manager = face_manager

        # Lock for thread-safe state changes
        self._lock = threading.Lock()

        # Stop event — signals the auto_end_loop thread to exit cleanly
        self._stop_event = threading.Event()

        # Internal session state
        self._session_id = None
        self._start_time = None
        self._duration_minutes = 60
        self._window_minutes = 10
        self._auto_end_thread = None

        # Reference to AsyncDetection (set from main.py) for event loop access
        self.detector = None

    # ----------------------------------------------------------
    # SESSION LIFECYCLE
    # ----------------------------------------------------------

    def start_session(self, duration_minutes: int, window_minutes: int) -> dict:
        """
        Start a new class session.
        Returns the session dict or raises ValueError if already active.
        """
        with self._lock:
            if shared_state.active_session is not None:
                raise ValueError("A session is already active. Stop it first.")

            self._duration_minutes = duration_minutes
            self._window_minutes = window_minutes
            self._start_time = datetime.utcnow()
            self._stop_event.clear()

            session_doc = {
                "start_time": self._start_time.isoformat(),
                "end_time": None,
                "duration_minutes": duration_minutes,
                "window_minutes": window_minutes,
                "status": "active",
                "present_count": 0,
                "late_count": 0,
                "absent_count": 0,
                "total_students": self.face_manager.get_total_students(),
                "avg_attention": None
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

            # Reset per-session attention tracking
            with shared_state._state_lock:
                shared_state.attention_data = {}
                shared_state.head_pose_data = {}
                shared_state.face_visibility = {}

            # Log activity
            self._log_activity("Session started", "session")
            print(f"[SessionManager] Session started: {self._session_id}")

        # Fire session_update WebSocket event
        self._fire_session_update("active")

        # Start auto-end timer in a daemon thread
        self._stop_event.clear()
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

            # Signal auto_end_loop to exit
            self._stop_event.set()

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

            # --- Compute avg_attention across tracked students ---
            attention_scores = [
                data.get("score", 0)
                for data in shared_state.attention_data.values()
                if data.get("score") is not None
            ]
            avg_attention = round(
                sum(attention_scores) / len(attention_scores), 1
            ) if attention_scores else 0.0

            # --- Compute actual session duration ---
            actual_duration = int(
                (end_time - self._start_time).total_seconds() / 60
            ) if self._start_time else self._duration_minutes

            # --- Update MongoDB session ---
            mongo.update_session(session_id, {
                "end_time": end_time.isoformat(),
                "status": "completed",
                "present_count": present_count,
                "late_count": late_count,
                "absent_count": absent_count,
                "actual_duration_minutes": actual_duration,
                "avg_attention": avg_attention
            })

            # Also persist via dedicated helper (explicit for clarity)
            mongo.save_avg_attention_to_session(session_id, avg_attention)

            # --- Save per-student attention logs to MongoDB ---
            for name, data in shared_state.attention_data.items():
                try:
                    mongo.save_attention_log(
                        session_id, name,
                        data.get("score", 0),
                        data.get("phone_detected", False),
                        data.get("phone_count", 0),
                        head_pose_score=data.get("head_pose_score"),
                        face_visible_ratio=data.get("face_visible_ratio")
                    )
                except Exception as e:
                    print(f"[SessionManager] Attention log save error: {e}")

            # --- Build summary ---
            summary = {
                "session_id": session_id,
                "start_time": self._start_time.isoformat() if self._start_time else None,
                "end_time": end_time.isoformat(),
                "present_count": present_count,
                "late_count": late_count,
                "absent_count": absent_count,
                "avg_attention": avg_attention
            }

            # --- Clear shared state ---
            shared_state.active_session = None
            self._session_id = None
            self._start_time = None

            self._log_activity("Session ended", "session")
            print(
                f"[SessionManager] Session stopped. "
                f"P:{present_count} L:{late_count} A:{absent_count} "
                f"Attention:{avg_attention}%"
            )

        # Fire session_update WebSocket event (outside lock)
        self._fire_session_update("idle")

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
        Determines PRESENT vs LATE based on attendance window.
        """
        if shared_state.active_session is None:
            return

        if name == "Unknown":
            return

        # Don't re-mark if already marked (and not overridden)
        existing = shared_state.session_attendance.get(name)
        if existing and not existing.get("overridden", False):
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
            "prn": prn,
            "overridden": False
        }

        # Persist to MongoDB
        mongo.save_attendance_record(
            self._session_id, name, roll_no, prn, status, timestamp
        )

        # Log activity
        self._log_activity(f"{name} marked {status}", "attendance")
        print(f"[SessionManager] {name} → {status}")

        # Fire attendance_update WebSocket event
        self._fire_attendance_update()

    # ----------------------------------------------------------
    # AUTO-END LOOP (fixed with threading.Event)
    # ----------------------------------------------------------

    def _auto_end_loop(self):
        """
        Background thread — auto-stops session when duration expires.
        Uses threading.Event to avoid the original break-inside-lock bug.
        """
        while True:
            # Wait up to 5 seconds, exit if stop_event is set
            if self._stop_event.wait(timeout=5):
                break  # Stop was requested externally

            if shared_state.active_session is None or self._start_time is None:
                break  # Session was manually stopped

            elapsed = (datetime.utcnow() - self._start_time).total_seconds()
            if elapsed >= self._duration_minutes * 60:
                print("[SessionManager] Auto-ending session (duration expired).")
                try:
                    self.stop_session()
                except Exception as e:
                    print(f"[SessionManager] Auto-stop error: {e}")
                break

    # ----------------------------------------------------------
    # WEBSOCKET EVENT HELPERS
    # ----------------------------------------------------------

    def _fire_session_update(self, status: str):
        """Fire session_update WS event to notify frontend of start/stop."""
        if self.detector is None or self.detector._loop is None:
            return
        try:
            import asyncio
            asyncio.run_coroutine_threadsafe(
                __import__("event_manager").event_manager.send_event(
                    "session_update",
                    {"status": status, "session": shared_state.active_session}
                ),
                self.detector._loop
            )
        except Exception as e:
            print(f"[SessionManager] session_update WS error: {e}")

    def _fire_attendance_update(self):
        """Fire attendance_update WS event after each mark."""
        if self.detector is None or self.detector._loop is None:
            return
        try:
            import asyncio
            present = sum(
                1 for r in shared_state.session_attendance.values()
                if r["status"] == "Present"
            )
            late = sum(
                1 for r in shared_state.session_attendance.values()
                if r["status"] == "Late"
            )
            absent = sum(
                1 for r in shared_state.session_attendance.values()
                if r["status"] == "Absent"
            )
            remaining = max(0, self._duration_minutes * 60 - (
                int((datetime.utcnow() - self._start_time).total_seconds())
                if self._start_time else 0
            ))
            asyncio.run_coroutine_threadsafe(
                __import__("event_manager").event_manager.send_event(
                    "attendance_update",
                    {
                        "present": present,
                        "late": late,
                        "absent": absent,
                        "remaining_seconds": remaining,
                        "session_id": self._session_id or ""
                    }
                ),
                self.detector._loop
            )
        except Exception as e:
            print(f"[SessionManager] attendance_update WS error: {e}")

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def _log_activity(self, message: str, activity_type: str):
        """Add entry to the global activity log."""
        entry = {
            "timestamp": time.strftime("%H:%M:%S"),
            "message": message,
            "type": activity_type
        }
        with shared_state._state_lock:
            shared_state.activity_log.insert(0, entry)
            if len(shared_state.activity_log) > 100:
                shared_state.activity_log.pop()


# Singleton — initialized in main.py after face_manager is ready
session_manager = None
