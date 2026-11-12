import os
import cv2
import json
import numpy as np
from PIL import Image
from config import Config
from ai_engine.face_detector import detector

class FaceRecognizer:
    def __init__(self, model_path=None):
        self.model_path = model_path or Config.TRAINED_MODEL_PATH
        self.map_path = os.path.join(os.path.dirname(self.model_path), 'students_map.json')
        self.recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1,
            neighbors=8,
            grid_x=8,
            grid_y=8
        )
        self.is_trained = False
        self.student_map = {} # { student_id_int: { 'roll_number': ..., 'name': ... } }
        self.load_model()

    def load_model(self):
        """Load trained LBPH model and student metadata from disk if present."""
        if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 0:
            try:
                self.recognizer.read(self.model_path)
                self.is_trained = True
                if os.path.exists(self.map_path):
                    with open(self.map_path, 'r', encoding='utf-8') as f:
                        self.student_map = json.load(f)
                print(f"[FaceRecognizer] Successfully loaded model with {len(self.student_map)} students.")
                return True
            except Exception as e:
                print(f"[FaceRecognizer] Error loading model: {e}")
                self.is_trained = False
        else:
            self.is_trained = False
        return False

    def train(self, dataset_folder=None, student_metadata=None):
        """Train the LBPH recognizer using cropped face images in dataset folder."""
        dataset_folder = dataset_folder or Config.DATASET_FOLDER
        if not os.path.exists(dataset_folder):
            os.makedirs(dataset_folder, exist_ok=True)
            return False, "Dataset directory is empty."

        faces = []
        labels = []
        new_map = student_metadata or {}

        # Loop through subdirectories in dataset
        # Each folder name format: student_<id>
        for entry in os.scandir(dataset_folder):
            if entry.is_dir() and entry.name.startswith("student_"):
                try:
                    s_id = int(entry.name.replace("student_", ""))
                except ValueError:
                    continue

                for img_file in os.listdir(entry.path):
                    if img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        img_path = os.path.join(entry.path, img_file)
                        try:
                            pil_img = Image.open(img_path).convert('L')
                            img_np = np.array(pil_img, 'uint8')
                            
                            # Normalize size to 200x200
                            if img_np.shape != (200, 200):
                                img_np = cv2.resize(img_np, (200, 200), interpolation=cv2.INTER_AREA)
                            
                            # Equalize histogram
                            img_np = cv2.equalizeHist(img_np)
                            
                            faces.append(img_np)
                            labels.append(s_id)
                        except Exception as ex:
                            print(f"Error reading image {img_path}: {ex}")

        if len(faces) == 0:
            return False, "No face samples found to train."

        try:
            self.recognizer.train(faces, np.array(labels))
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            self.recognizer.write(self.model_path)
            
            # Save student mapping
            if new_map:
                self.student_map.update(new_map)
            with open(self.map_path, 'w', encoding='utf-8') as f:
                json.dump(self.student_map, f, indent=2)

            self.is_trained = True
            print(f"[FaceRecognizer] Successfully trained model on {len(faces)} face samples across {len(set(labels))} students.")
            return True, f"Successfully trained model with {len(faces)} images across {len(set(labels))} students."
        except Exception as e:
            return False, f"Training failed: {str(e)}"

    def predict(self, face_roi_gray, distance_threshold=75.0):
        """Predict student ID and compute confidence percentage."""
        if not self.is_trained:
            return {
                'matched': False,
                'student_id': None,
                'confidence': 0.0,
                'distance': 999.0,
                'message': 'Model not trained yet'
            }

        try:
            # Predict returns (label, distance). Lower distance = higher match
            label, distance = self.recognizer.predict(face_roi_gray)
            
            # Convert LBPH distance (typically 0 - 100) to confidence percentage
            # Distance 0 => 100%
            # Distance 50 => ~75%
            # Distance 75 => ~55%
            # Distance >= 95 => 0%
            confidence = max(0.0, min(100.0, round(100.0 - (distance * 0.65), 1)))
            
            # Distance threshold for positive identification
            is_matched = (distance <= distance_threshold) and (confidence >= 45.0)

            return {
                'matched': is_matched,
                'student_id': int(label) if is_matched else None,
                'confidence': confidence,
                'distance': round(float(distance), 2),
                'message': 'Face recognized' if is_matched else 'Unknown face'
            }
        except Exception as e:
            print(f"[FaceRecognizer] Prediction error: {e}")
            return {
                'matched': False,
                'student_id': None,
                'confidence': 0.0,
                'distance': 999.0,
                'message': str(e)
            }

    def save_samples_and_train(self, student_id, roll_number, full_name, frames_list):
        """Save a list of cropped face frames into student's dataset directory and retrain model."""
        student_dir = os.path.join(Config.DATASET_FOLDER, f"student_{student_id}")
        os.makedirs(student_dir, exist_ok=True)

        saved_count = 0
        for i, frame in enumerate(frames_list):
            if frame is None:
                continue
            # If color image, detect or convert
            if len(frame.shape) == 3:
                detected = detector.detect_faces(frame)
                if detected:
                    roi = detected[0]['face_roi']
                else:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    roi = cv2.resize(gray, (200, 200))
            else:
                roi = cv2.resize(frame, (200, 200))

            file_path = os.path.join(student_dir, f"sample_{saved_count + 1}.jpg")
            cv2.imwrite(file_path, roi)
            saved_count += 1

        # Update metadata mapping
        str_id = str(student_id)
        self.student_map[str_id] = {
            'student_id': student_id,
            'roll_number': roll_number,
            'full_name': full_name
        }

        # Retrain model
        success, msg = self.train(student_metadata=self.student_map)
        return success, saved_count, msg

# Singleton instance for application reuse
recognizer = FaceRecognizer()
