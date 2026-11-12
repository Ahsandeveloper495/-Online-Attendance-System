import os
import unittest
import base64
import cv2
import numpy as np
from app import create_app
from config import Config
from database.db import execute_db

class SmartAttendanceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_01_public_redirect(self):
        """Root should redirect to login when unauthenticated."""
        response = self.client.get('/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sign In to Dashboard', response.data)

    def test_02_admin_login_and_pages(self):
        """Admin should log in and view admin portals."""
        res = self.login('admin', 'admin123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Administrator Dashboard', res.data)

        # Check Students page
        res_stu = self.client.get('/admin/students')
        self.assertEqual(res_stu.status_code, 200)
        self.assertIn(b'Student Management', res_stu.data)

        # Check Teachers page
        res_tea = self.client.get('/admin/teachers')
        self.assertEqual(res_tea.status_code, 200)
        self.assertIn(b'Faculty Teacher Management', res_tea.data)

        # Check Courses page
        res_crs = self.client.get('/admin/courses')
        self.assertEqual(res_crs.status_code, 200)
        self.assertIn(b'Academic Courses', res_crs.data)

        # Check Audit logs
        res_audit = self.client.get('/admin/audit-logs')
        self.assertEqual(res_audit.status_code, 200)
        self.assertIn(b'Attendance Correction Audit Logs', res_audit.data)

        # Check Settings
        res_set = self.client.get('/admin/settings')
        self.assertEqual(res_set.status_code, 200)
        self.assertIn(b'System &amp; Attendance Rules', res_set.data)

        self.logout()

    def test_03_teacher_dashboard_and_features(self):
        """Teacher should log in and view assigned courses and attendance tools."""
        res = self.login('teacher1', 'teacher123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Instructor Dashboard', res.data)

        # Start session page
        res_start = self.client.get('/teacher/session/start')
        self.assertEqual(res_start.status_code, 200)

        # Manual attendance page
        res_man = self.client.get('/teacher/manual-attendance')
        self.assertEqual(res_man.status_code, 200)

        # Low attendance alerts page
        res_low = self.client.get('/teacher/low-attendance')
        self.assertEqual(res_low.status_code, 200)

        self.logout()

    def test_04_student_dashboard_and_history(self):
        """Student should log in and see personal attendance metrics and low-attendance alert."""
        res = self.login('student1', 'student123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Student Portal', res.data)

        # History page
        res_hist = self.client.get('/student/history')
        self.assertEqual(res_hist.status_code, 200)
        self.assertIn(b'My Attendance History', res_hist.data)

        # Profile page
        res_prof = self.client.get('/student/profile')
        self.assertEqual(res_prof.status_code, 200)
        self.assertIn(b'Student Biometric Profile', res_prof.data)

        self.logout()

    def test_05_reports_and_export(self):
        """Reports should render and generate valid Excel and PDF files."""
        self.login('admin', 'admin123')

        # Index page
        res_rep = self.client.get('/reports/')
        self.assertEqual(res_rep.status_code, 200)
        self.assertIn(b'Comprehensive Attendance Reports', res_rep.data)

        # Export Excel
        res_excel = self.client.get('/reports/export/excel')
        self.assertEqual(res_excel.status_code, 200)
        self.assertEqual(res_excel.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertGreater(len(res_excel.data), 1000)

        # Export PDF
        res_pdf = self.client.get('/reports/export/pdf')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.content_type, 'application/pdf')
        self.assertGreater(len(res_pdf.data), 1000)

        self.logout()

    def test_06_ai_face_recognition_api(self):
        """API should process base64 face frame and return valid JSON response."""
        with self.app.app_context():
            # Ensure there is an active session for testing
            execute_db("UPDATE attendance_sessions SET is_active = 1 WHERE id = 1")
            
        sample_path = os.path.join(Config.DATASET_FOLDER, 'student_1', 'sample_1.jpg')
        if os.path.exists(sample_path):
            with open(sample_path, 'rb') as f:
                b64_img = 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode('utf-8')
            
            res = self.client.post('/api/recognize_frame', json={
                'session_id': 1,
                'image': b64_img
            })
            self.assertEqual(res.status_code, 200)
            json_data = res.get_json()
            self.assertTrue(json_data['success'])

if __name__ == '__main__':
    unittest.main()
