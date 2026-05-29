import sqlite3


class AttendanceDatabase:

    def __init__(self):

        self.connection = sqlite3.connect(
            "attendance.db",
            check_same_thread=False
        )

        self.cursor = self.connection.cursor()

        self.create_table()

    def create_table(self):

        self.cursor.execute("""

            CREATE TABLE IF NOT EXISTS attendance (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT,

                batch TEXT,

                roll_no TEXT,

                date TEXT,

                time TEXT,

                status TEXT
            )

        """)

        self.connection.commit()

    def insert_attendance(

        self,

        name,

        batch,

        roll_no,

        date,

        time,

        status

    ):

        self.cursor.execute("""

            INSERT INTO attendance (

                name,
                batch,
                roll_no,
                date,
                time,
                status

            )

            VALUES (?, ?, ?, ?, ?, ?)

        """, (

            name,
            batch,
            roll_no,
            date,
            time,
            status

        ))

        self.connection.commit()

    def get_attendance(self):

        self.cursor.execute("""

            SELECT
                name,
                batch,
                roll_no,
                date,
                time,
                status

            FROM attendance

            ORDER BY id DESC

        """)

        rows = self.cursor.fetchall()

        data = []

        for row in rows:

            data.append({

                "Name": row[0],
                "Batch": row[1],
                "RollNo": row[2],
                "Date": row[3],
                "Time": row[4],
                "Status": row[5]

            })

        return data