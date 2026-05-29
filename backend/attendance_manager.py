import csv
import os
import time
from datetime import datetime

from database.database import AttendanceDatabase


class AttendanceManager:

    def __init__(self):

        self.file_path = "attendance.csv"

        # DATABASE
        self.database = AttendanceDatabase()

        # PREVENT DUPLICATE ATTENDANCE
        self.marked_today = set()

        # ATTENDANCE COOLDOWN (SECONDS)
        self.cooldown = 60

        # LAST MARKED TIME
        self.last_marked_time = {}

        # CREATE CSV IF NOT EXISTS
        if not os.path.exists(self.file_path):

            with open(
                self.file_path,
                mode="w",
                newline=""
            ) as file:

                writer = csv.writer(file)

                writer.writerow([
                    "Name",
                    "Batch",
                    "RollNo",
                    "Date",
                    "Time",
                    "Status"
                ])

    # MARK ATTENDANCE
    def mark_attendance(

        self,

        name,

        batch,

        roll_no
    ):

        if name == "Unknown":
            return

        today = datetime.now().strftime("%Y-%m-%d")

        unique_key = f"{name}_{today}"

        current_timestamp = time.time()

        # COOLDOWN CHECK
        if name in self.last_marked_time:

            elapsed_time = (
                current_timestamp
                - self.last_marked_time[name]
            )

            if elapsed_time < self.cooldown:
                return

        # PREVENT DUPLICATE DAILY ATTENDANCE
        if unique_key in self.marked_today:
            return

        self.marked_today.add(unique_key)

        self.last_marked_time[name] = current_timestamp

        current_time = datetime.now().strftime("%H:%M:%S")

        # SAVE TO CSV
        with open(
            self.file_path,
            mode="a",
            newline=""
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                name,
                batch,
                roll_no,
                today,
                current_time,
                "Present"
            ])

        # SAVE TO DATABASE
        self.database.insert_attendance(

            name,
            batch,
            roll_no,
            today,
            current_time,
            "Present"
        )

        print(f"Attendance Marked: {name}")

    # GET ALL ATTENDANCE
    def get_attendance(self):

        return self.database.get_attendance()

    # GET TODAY ATTENDANCE COUNT
    def get_today_attendance_count(self):

        today = datetime.now().strftime("%Y-%m-%d")

        count = 0

        if not os.path.exists(self.file_path):
            return 0

        with open(
            self.file_path,
            mode="r"
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                if row["Date"] == today:

                    count += 1

        return count