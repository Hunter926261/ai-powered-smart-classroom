from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

import threading
import time


class DetectionManager:

    def __init__(
        self,
        frame_manager,
        face_manager,
        attendance_manager
    ):

        self.frame_manager = frame_manager

        self.face_manager = face_manager

        self.attendance_manager = attendance_manager

        # YOLO MODEL
        self.model = YOLO("yolov8n.pt")

        # GPU PREPARATION
        self.device = "cuda"

        self.tracker = DeepSort(
            max_age=30
        )

        self.recognized_ids = {}

        self.latest_tracks = []

        self.running = True

        self.frame_skip = 0

        self.thread = threading.Thread(
            target=self.detect_loop,
            daemon=True
        )

        self.thread.start()

    def detect_loop(self):

        while self.running:

            frame = self.frame_manager.get_frame()

            if frame is None:
                continue

            detection_frame = frame.copy()

            self.frame_skip += 1

            # FRAME SKIPPING
            if self.frame_skip % 3 != 0:
                time.sleep(0.01)
                continue

            # YOLO TRACKING
            results = self.model.track(
                detection_frame,
                persist=True,
                verbose=False,
                device=self.device
            )

            detections = []

            for result in results:

                boxes = result.boxes

                if boxes is None:
                    continue

                for box in boxes:

                    cls = int(box.cls[0])

                    confidence = float(box.conf[0])

                    # PERSON CLASS
                    if cls == 0 and confidence > 0.5:

                        x1, y1, x2, y2 = map(
                            int,
                            box.xyxy[0]
                        )

                        width = x2 - x1
                        height = y2 - y1

                        detections.append([
                            [x1, y1, width, height],
                            confidence,
                            "person"
                        ])

            tracks = self.tracker.update_tracks(
                detections,
                frame=detection_frame
            )

            tracked_people = []

            for track in tracks:

                if not track.is_confirmed():
                    continue

                track_id = track.track_id

                ltrb = track.to_ltrb()

                x1, y1, x2, y2 = map(
                    int,
                    ltrb
                )

                # PERSON CROP
                person_crop = detection_frame[
                    y1:y2,
                    x1:x2
                ]

                # FACE RECOGNITION
                name = "Unknown"

                if person_crop.size > 0:

                    detected_name = self.face_manager.recognize_face(
                        person_crop
                    )

                    # UPDATE IF NEW PERSON FOUND
                    if detected_name != "Unknown":

                        self.recognized_ids[track_id] = detected_name

                        name = detected_name

                        self.attendance_manager.mark_attendance(
                            detected_name
                        )

                    else:

                        name = self.recognized_ids.get(
                            track_id,
                            "Unknown"
                        )

                tracked_people.append({
                    "id": track_id,
                    "name": name,
                    "box": [x1, y1, x2, y2]
                })

            self.latest_tracks = tracked_people

            time.sleep(0.01)