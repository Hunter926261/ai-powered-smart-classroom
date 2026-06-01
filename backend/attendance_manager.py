"""
Attendance Manager — Smart Classroom Manager
=============================================
Manages attendance cooldown logic.
MongoDB is the SOLE persistence backend (SQLite and CSV removed).

Actual attendance marking/status (Present/Late/Absent) is handled
by SessionManager. This class handles:
  - Cooldown to prevent duplicate marks within 60 seconds
  - Query helpers that read from MongoDB
"""

import time
from datetime import datetime

from database.mongo_client import mongo


class AttendanceManager:

    def __init__(self):
        # Cooldown period in seconds between marks for the same person
        self.cooldown = 60

        # Track last marked time per student: {name: float(unix_ts)}
        self.last_marked_time = {}

        print("[AttendanceManager] Initialized (MongoDB-only)")

    # ----------------------------------------------------------
    # MARK ATTENDANCE (cooldown gate — actual persistence in SessionManager)
    # ----------------------------------------------------------

    def mark_attendance(self, name, batch, roll_no):
        """
        !! PRESERVED: signature unchanged — called by async_detection !!

        Cooldown check only. Actual Present/Late/Absent persistence
        is handled by SessionManager.mark_attendance() which is called
        separately after this gate passes.
        """
        if name == "Unknown":
            return

        now = time.time()
        if name in self.last_marked_time:
            if now - self.last_marked_time[name] < self.cooldown:
                return  # Still in cooldown

        self.last_marked_time[name] = now
        print(f"[AttendanceManager] Cooldown gate passed: {name}")

    # ----------------------------------------------------------
    # QUERIES — READ FROM MONGODB
    # ----------------------------------------------------------

    def get_attendance(self) -> list:
        """
        !! PRESERVED: called by /attendance endpoint !!
        Returns all attendance records from MongoDB.
        """
        return mongo.get_all_attendance()

    def get_today_attendance_count(self) -> int:
        """
        !! PRESERVED: called by /dashboard/stats !!
        Returns count of present/late students today from MongoDB.
        """
        return mongo.count_today_attendance()