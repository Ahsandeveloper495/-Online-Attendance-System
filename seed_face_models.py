import os
import cv2
import numpy as np
from config import Config
from ai_engine.face_recognizer import recognizer
from database.db import query_db, execute_db
from app import create_app

app = create_app()

def generate_face_sample(seed_val, variation):
    """Generate a 200x200 simulated face image with consistent features per student."""
    np.random.seed(seed_val + variation)
    img = np.ones((200, 200), dtype=np.uint8) * 128
    
    # Base face ellipse
    cv2.ellipse(img, (100, 100), (60 + (seed_val % 10), 75 + (variation % 5)), 0, 0, 360, 210, -1)
    
    # Left eye
    eye_x_offset = (seed_val * 7) % 15
    cv2.circle(img, (75 + eye_x_offset, 85), 10, 40, -1)
    cv2.circle(img, (75 + eye_x_offset, 85), 3, 240, -1)

    # Right eye
    cv2.circle(img, (125 - eye_x_offset, 85), 10, 40, -1)
    cv2.circle(img, (125 - eye_x_offset, 85), 3, 240, -1)

    # Nose
    cv2.line(img, (100, 95), (100, 120), 80, 2)
    cv2.line(img, (95, 120), (105, 120), 80, 2)

    # Mouth
    mouth_curve = (seed_val % 12) + 5
    cv2.ellipse(img, (100, 140), (25, mouth_curve), 0, 0, 180, 50, 3)

    # Add minor noise for texture variation
    noise = np.random.normal(0, 4, img.shape).astype(np.uint8)
    img = cv2.add(img, noise)
    
    # Equalize histogram
    img = cv2.equalizeHist(img)
    return img

def seed_demo_faces():
    with app.app_context():
        students = query_db("""
            SELECT s.id, s.roll_number, u.full_name 
            FROM students s 
            JOIN users u ON s.user_id = u.id
        """)
        if not students:
            print("No students in database to seed faces for.")
            return

        print(f"Generating initial face datasets for {len(students)} students...")
        student_map = {}
        for st in students:
            s_id = st['id']
            roll = st['roll_number']
            name = st['full_name']
            s_dir = os.path.join(Config.DATASET_FOLDER, f"student_{s_id}")
            os.makedirs(s_dir, exist_ok=True)

            for v in range(12):
                sample = generate_face_sample(s_id * 101, v)
                cv2.imwrite(os.path.join(s_dir, f"sample_{v+1}.jpg"), sample)

            student_map[str(s_id)] = {
                'student_id': s_id,
                'roll_number': roll,
                'full_name': name
            }

            # Update student as face registered
            execute_db("UPDATE students SET is_face_registered = 1, face_registered_at = '2026-11-05 09:00:00' WHERE id = %s", (s_id,))

        # Train recognizer
        success, msg = recognizer.train(student_metadata=student_map)
        print("Face model training result:", success, msg)

if __name__ == '__main__':
    seed_demo_faces()
