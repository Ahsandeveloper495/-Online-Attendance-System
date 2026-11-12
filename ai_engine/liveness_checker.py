import cv2
import numpy as np

class LivenessChecker:
    @staticmethod
    def check_blur_variance(gray_roi, min_variance=45.0):
        """Compute the Laplacian variance to detect blurry spoofed photos or low-res paper prints."""
        if gray_roi is None or gray_roi.size == 0:
            return 0.0, False
        variance = cv2.Laplacian(gray_roi, cv2.CV_64F).var()
        return round(float(variance), 2), variance >= min_variance

    @staticmethod
    def verify_liveness(face_roi_gray, eyes_count=0):
        """Evaluate multi-factor biometric liveness score."""
        blur_var, is_sharp = LivenessChecker.check_blur_variance(face_roi_gray)
        
        # Scoring components:
        # 1. Image sharpness/texture (50%)
        # 2. Eye presence / natural structure (50%)
        sharpness_score = min(50.0, (blur_var / 120.0) * 50.0)
        eye_score = 50.0 if eyes_count >= 2 else (30.0 if eyes_count == 1 else 15.0)
        
        total_score = round(sharpness_score + eye_score, 1)
        is_live = (total_score >= 50.0) and (blur_var >= 30.0)
        
        reasons = []
        if blur_var < 30.0:
            reasons.append("Low texture variance (possible paper or screen spoof)")
        if eyes_count < 1:
            reasons.append("Facial landmark / eyes occlusion")
        
        return {
            'is_live': is_live,
            'liveness_score': total_score,
            'blur_variance': blur_var,
            'eyes_detected': eyes_count,
            'reasons': reasons
        }

liveness_checker = LivenessChecker()
