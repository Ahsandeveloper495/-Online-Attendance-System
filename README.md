# AI-Based Smart Attendance System

> **Final Year Project (FYP)**  
> Developed using **Python Flask**, **OpenCV**, **LBPH Face Recognition**, **MySQL / SQLite**, **HTML5/CSS3/JavaScript**, and **Bootstrap 5**.

---

## 📌 1. Project Overview

The **AI-Based Smart Attendance System** is an intelligent, automated attendance management platform designed for universities and academic institutions. Traditional manual paper rolls or RFID cards suffer from time consumption, proxy attendance, and human recording errors. This solution automates the attendance lifecycle via live facial recognition, anti-proxy duplicate prevention, role-based dashboards (Admin, Teacher, Student), automated low-attendance warnings (< 75%), audit-trailed manual corrections, and one-click PDF & Excel report exports.

---

## 🌟 2. Key Features

- **Multi-Role Authentication**:
  - **Admin**: Student & teacher management, course/section allocations, face model retraining, audit trails, and institutional thresholds.
  - **Teacher**: Live camera attendance session, real-time bounding box recognition, audio confirmation, manual status overrides with mandatory audit justification, and low-attendance defaulter tracking.
  - **Student**: Personal attendance profile, overall attendance %, subject-wise progress meters, historical log, and low-attendance alert banners (< 75%).
- **Computer Vision & AI Engine**:
  - **Face Detection**: Multi-scale OpenCV Haar Cascade (`haarcascade_frontalface_default.xml`) with histogram equalization for lighting invariance.
  - **Face Recognition**: Local Binary Patterns Histograms (**LBPH**) classifier with dynamic confidence scoring.
  - **Liveness & Anti-Spoofing**: Texture blur variance (Laplacian) and facial landmark checks to detect printed photos and screen replays.
  - **Anti-Duplicate Logic**: Automatically blocks duplicate marking within the same active class session.
- **Reporting & Analytics**:
  - Daily, weekly, and monthly attendance reports filterable by Course, Section, and Date range.
  - **Excel Export (`.xlsx`)**: Formatted spreadsheets with highlighted defaulters using `openpyxl`.
  - **PDF Export (`.pdf`)**: University-grade printable attendance sheets with signature blocks using `reportlab`.
- **Database Architecture**:
  - **Dual-Engine Auto-Fallback**: Pre-configured for **MySQL** (`smart_attendance_db`), with seamless, automatic fallback to **SQLite** (`database/smart_attendance.db`) if MySQL is not running. Works out of the box with zero external configuration!

---

## 📂 3. Project Directory Structure

```
smart_attendance_system/
│
├── app.py                     # Main Flask Application & Blueprints configuration
├── run.py                     # Project starter entrypoint
├── config.py                  # Database, paths, and threshold configurations
├── test_app.py                # Automated test suite (Unit & Integration tests)
├── requirements.txt           # Python dependencies
├── seed_face_models.py        # Face dataset generator and initial model trainer
├── README.md                  # Installation, testing & usage documentation
├── PROJECT_DOCUMENTATION.md   # Comprehensive FYP report & viva defense guide
│
├── database/
│   ├── db.py                  # Dual-engine DB driver (MySQL PyMySQL & SQLite)
│   ├── schema.sql             # Complete MySQL relational database schema
│   ├── init_db.py             # Database creation & demo seeding script
│   └── smart_attendance.db    # SQLite database (auto-created if using SQLite)
│
├── ai_engine/
│   ├── face_detector.py       # OpenCV Haar Cascade face detector & preprocessing
│   ├── face_recognizer.py     # LBPH Face Recognizer (train, predict, confidence)
│   └── liveness_checker.py    # Anti-spoofing texture & landmark analysis
│
├── models/
│   ├── trainer.yml            # Trained LBPH model weights
│   ├── students_map.json      # Biometric student ID to roll number mapping
│   ├── haarcascade_frontalface_default.xml # Face detection cascade
│   └── haarcascade_eye.xml    # Eye detection cascade
│
├── dataset/                   # Biometric training datasets (student_<id>/sample_X.jpg)
├── uploads/                   # User uploads and temporary files
│
├── routes/
│   ├── auth_routes.py         # Login, logout, password change
│   ├── admin_routes.py        # Admin portal, student/teacher/course management
│   ├── teacher_routes.py      # Teacher portal, live camera sessions, manual corrections
│   ├── student_routes.py      # Student portal, attendance breakdown, logs
│   ├── attendance_routes.py   # AI recognition API, sample capture API
│   └── report_routes.py       # Attendance reports, Excel & PDF exports
│
├── static/
│   ├── css/
│   │   └── style.css          # Custom styling, animations, camera overlay
│   └── js/
│       ├── main.js            # General UI helpers
│       ├── webcam_capture.js  # Live WebRTC camera face enrollment
│       └── attendance_live.js # Real-time camera recognition stream & audio chime
│
└── templates/
    ├── base.html              # Responsive navigation & layout
    ├── auth/
    │   └── login.html         # Login with 1-click demo credential pills
    ├── admin/
    │   ├── dashboard.html     # Analytics, KPI widgets, recent feed
    │   ├── students.html      # Student management & enrollment status
    │   ├── student_register.html # Biometric webcam face registration console
    │   ├── teachers.html      # Faculty management & class allocation
    │   ├── courses.html       # Courses & sections configuration
    │   ├── audit_logs.html    # Manual override audit trail
    │   └── settings.html      # Institutional thresholds & parameters
    ├── teacher/
    │   ├── dashboard.html     # Allocated classes & today's schedule
    │   ├── start_session.html # Class selection for attendance
    │   ├── attendance_session.html # Fullscreen live camera attendance marking station
    │   ├── manual_attendance.html  # Attendance sheet with audit justification
    │   └── low_attendance.html     # Low attendance warning table (< 75%)
    ├── student/
    │   ├── dashboard.html     # Student metrics, subject progress, warning banner
    │   ├── history.html       # Full attendance history log
    │   └── profile.html       # Biometric template registration info
    └── reports/
        └── index.html         # Multi-filter reports with Excel/PDF export buttons
```

---

## 🚀 4. Quick Start & Installation

### Step 1: Clone / Navigate to Project Directory
```powershell
cd "e:\Ahsan win"
```

### Step 2: Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Initialize Database
The system supports both SQLite (instant, zero setup) and MySQL (via XAMPP / WAMP / MySQL Server).

- **Option A: SQLite (Default, No setup needed)**:
  ```powershell
  python database/init_db.py
  ```
- **Option B: MySQL / MariaDB**:
  Ensure MySQL is running on port 3306, then execute:
  ```powershell
  python database/init_db.py --mysql
  ```
  *(Or import `database/schema.sql` into phpMyAdmin / MySQL Workbench).*

### Step 4: Run the Application
```powershell
python run.py
```
Open your web browser and navigate to:
👉 **`http://127.0.0.1:5000`**

---

## 🔑 5. Pre-Configured Demo Credentials

For quick evaluation during project defense and testing, click any of the 1-click test buttons on the login page:

| Role | Username | Password | Full Name / Description |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | System Administrator |
| **Teacher** | `teacher1` | `teacher123` | Prof. Dr. Tariq Mahmood |
| **Student 1** | `student1` | `student123` | Ahsan Ali (Roll: 2021-CS-101) - High Attendance (90%) |
| **Student 5** | `student5` | `student123` | Hamza Tariq (Roll: 2021-CS-105) - Defaulter (<75%) |

---

## 🧪 6. Testing Instructions

To run the automated test suite verifying authentication, dashboards, reports, exports, and facial recognition APIs:
```powershell
python test_app.py
```
Expected output:
```
Ran 6 tests in ~5s
OK
```

---

## 📷 7. Live Camera Attendance Workflow

1. Log in as **Teacher** (`teacher1` / `teacher123`).
2. Click **"Start Attendance Session"** and select **CS-401 - Artificial Intelligence & Computer Vision**.
3. Allow camera access in the browser. The live webcam feed will start scanning.
4. When a student stands before the camera:
   - Green bounding box appears around the face with **Student Name** and **Match Confidence %**.
   - An audio chime confirms verification.
   - Student is marked **Present** in the database with exact timestamp.
   - If the student stays in frame, the system displays **"Already Marked"** in amber to prevent duplicate entries.
5. Click **"Finish & Close Session"**. Remaining unmarked students are automatically marked **Absent**.
6. View or export the updated attendance sheet from **Reports** -> **Export to Excel** or **Export Official PDF**.
