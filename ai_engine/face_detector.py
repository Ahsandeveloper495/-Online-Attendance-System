import os
import cv2
import numpy as np
import base64
from config import Config

class FaceDetector:
    def __init__(self, face_cascade_path=None, eye_cascade_path=None):
        self.face_cascade_path = face_cascade_path or Config.FACE_CASCADE_PATH
        self.eye_cascade_path = eye_cascade_path or Config.EYE_CASCADE_PATH
        
        self.face_cascade = cv2.CascadeClassifier(self.face_cascade_path)
        self.eye_cascade = cv2.CascadeClassifier(self.eye_cascade_path)
        
        if self.face_cascade.empty():
            print(f"Warning: Failed to load face cascade from {self.face_cascade_path}")
        if self.eye_cascade.empty():
            print(f"Warning: Failed to load eye cascade from {self.eye_cascade_path}")

    def detect_faces(self, frame_bgr, scale_factor=1.1, min_neighbors=5, min_size=(60, 60)):
        """Detect faces in a BGR frame and return bounding boxes + normalized cropped face ROIs."""
        if frame_bgr is None:
            return []
            
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        # Apply histogram equalization for contrast/lighting normalization
        equalized = cv2.equalizeHist(gray)
        
        faces = self.face_cascade.detectMultiScale(
            equalized,
            scaleFactor=scale_factor,
            minNeighbors=min_neighbors,
            minSize=min_size,
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        results = []
        for (x, y, w, h) in faces:
            # Add small padding margin if within image boundaries
            margin_x = int(w * 0.08)
            margin_y = int(h * 0.08)
            x1 = max(0, x - margin_x)
            y1 = max(0, y - margin_y)
            x2 = min(frame_bgr.shape[1], x + w + margin_x)
            y2 = min(frame_bgr.shape[0], y + h + margin_y)
            
            face_roi_gray = equalized[y1:y2, x1:x2]
            
            # Detect eyes within the face ROI for liveness/quality check
            eyes = []
            if not self.eye_cascade.empty():
                eyes = self.eye_cascade.detectMultiScale(face_roi_gray, scaleFactor=1.1, minNeighbors=3, minSize=(15, 15))
            
            # Resize face ROI to standard 200x200
            face_resized = cv2.resize(face_roi_gray, (200, 200), interpolation=cv2.INTER_AREA)
            
            results.append({
                'box': (int(x), int(y), int(w), int(h)),
                'face_roi': face_resized,
                'eyes_count': len(eyes),
                'confidence_heuristic': min(100, int(len(eyes) * 35 + 30))
            })
            
        return results

    @staticmethod
    def decode_base64_frame(data_url_or_base64):
        """Decode base64 image string (such as from HTML5 canvas) to OpenCV BGR image."""
        try:
            if ',' in data_url_or_base64:
                base64_data = data_url_or_base64.split(',')[1]
            else:
                base64_data = data_url_or_base64
            
            img_bytes = base64.b64decode(base64_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            print(f"Error decoding base64 frame: {e}")
            return None

    @staticmethod
    def encode_frame_to_base64(frame_bgr, quality=85):
        """Encode OpenCV BGR frame to JPEG base64 string."""
        try:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            _, buffer = cv2.imencode('.jpg', frame_bgr, encode_param)
            b64_str = base64.b64encode(buffer).decode('utf-8')
            return f"data:image/jpeg;base64,{b64_str}"
        except Exception as e:
            print(f"Error encoding frame: {e}")
            return None

# Singleton instance for application reuse
detector = FaceDetector()
