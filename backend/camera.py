import cv2
import threading
import time

from config import PI_STREAM_URL


class Camera:

    def __init__(self):

        # PI CAMERA STREAM URL
        self.stream_url = (
            PI_STREAM_URL
        )

        # STREAM CAPTURE
        self.cap = cv2.VideoCapture(
            self.stream_url
        )

        # BUFFER REDUCTION
        self.cap.set(
            cv2.CAP_PROP_BUFFERSIZE,
            1
        )

        # SET FPS
        self.cap.set(
            cv2.CAP_PROP_FPS,
            30
        )

        self.frame = None

        self.running = True

        self.lock = threading.Lock()

        self.fps = 0

        self.thread = threading.Thread(
            target=self.update,
            daemon=True
        )

        self.thread.start()

    def reconnect(self):

        print("Reconnecting to Pi stream...")

        try:
            self.cap.release()
        except:
            pass

        time.sleep(2)

        self.cap = cv2.VideoCapture(
            self.stream_url
        )

        # APPLY SETTINGS AGAIN AFTER RECONNECT
        self.cap.set(
            cv2.CAP_PROP_BUFFERSIZE,
            1
        )

        self.cap.set(
            cv2.CAP_PROP_FPS,
            30
        )

    def update(self):

        prev_time = time.time()

        while self.running:

            try:

                success, frame = self.cap.read()

                if not success:

                    print("Frame read failed")

                    self.reconnect()

                    continue

                # VALID FRAME CHECK
                if frame is None:
                    continue

                with self.lock:

                    self.frame = frame.copy()

                current_time = time.time()

                delta = current_time - prev_time

                if delta > 0:

                    self.fps = int(1 / delta)

                prev_time = current_time

            except Exception as e:

                print("Camera Error:", e)

                self.reconnect()

            time.sleep(0.001)

    def get_frame(self):

        with self.lock:

            if self.frame is None:
                return None

            return self.frame.copy()

    def stop(self):

        self.running = False

        self.thread.join()

        self.cap.release()