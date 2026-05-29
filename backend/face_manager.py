import os
import cv2
import pickle
import numpy as np
import insightface


class FaceManager:

    def __init__(self):

        self.app = insightface.app.FaceAnalysis()

        # GPU MODE
        self.app.prepare(ctx_id=0)

        print("InsightFace GPU Enabled")

        self.embedding_file = "face_embeddings.pkl"

        self.known_faces = {}

        self.load_faces()

    # LOAD REGISTERED FACES
    def load_faces(self):

        if os.path.exists(self.embedding_file):

            try:

                with open(self.embedding_file, "rb") as f:

                    self.known_faces = pickle.load(f)

            except:

                self.known_faces = {}

        else:

            self.known_faces = {}

    # SAVE REGISTERED FACES
    def save_faces(self):

        with open(self.embedding_file, "wb") as f:

            pickle.dump(
                self.known_faces,
                f
            )

    # REGISTER NEW FACE
    def register_face(
        self,
        name,
        batch,
        roll_no,
        frame
    ):

        faces = self.app.get(frame)

        if len(faces) == 0:
            return False

        face = faces[0]

        embedding = face.embedding

        # STORE FULL STUDENT DATA
        self.known_faces[name] = {

            "embedding": embedding,

            "batch": batch,

            "roll_no": roll_no
        }

        self.save_faces()

        # SAVE FACE IMAGE
        os.makedirs(
            "registered_faces",
            exist_ok=True
        )

        cv2.imwrite(
            f"registered_faces/{name}.jpg",
            frame
        )

        return True

    # RECOGNIZE FACE
    def recognize_face(self, frame):

        faces = self.app.get(frame)

        if len(faces) == 0:
            return "Unknown"

        embedding = faces[0].embedding

        best_match = "Unknown"

        best_distance = 999

        for name, data in self.known_faces.items():

            known_embedding = data["embedding"]

            distance = np.linalg.norm(
                embedding - known_embedding
            )

            if distance < best_distance and distance < 25:

                best_distance = distance

                best_match = name

        return best_match

    # GET TOTAL REGISTERED STUDENTS
    def get_total_students(self):

        return len(self.known_faces)

    # GET ALL STUDENTS
    def get_all_students(self):

        students = []

        for name, data in self.known_faces.items():

            students.append({

                "name": name,

                "batch": data["batch"],

                "roll_no": data["roll_no"]
            })

        return students

    # GET SINGLE STUDENT INFO
    def get_student_info(self, name):

        return self.known_faces.get(name, None)