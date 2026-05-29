import cv2
import threading
import time

latest_frame = None

def camera_loop():

    global latest_frame

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    while True:

        success, frame = cap.read()

        if success:
            latest_frame = frame.copy()

        time.sleep(0.01)

threading.Thread(
    target=camera_loop,
    daemon=True
).start()

while True:

    if latest_frame is not None:

        cv2.imshow(
            "Thread Camera Test",
            latest_frame
        )

    if cv2.waitKey(1) == ord("q"):
        break

cv2.destroyAllWindows()