import os
import sys
import sqlite3
import datetime
import random
from werkzeug.security import generate_password_hash

# Add parent directory to path so config can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Config
from database.db import test_mysql_connection

SQLITE_SCHEMA = """
-- Users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'student')),
    full_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

-- Departments
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Courses
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL UNIQUE,
    course_name TEXT NOT NULL,
    department_id INTEGER,
    credit_hours INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
);

-- Sections
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department_id INTEGER,
    semester INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
);

-- Teachers
CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    employee_id TEXT NOT NULL UNIQUE,
    department_id INTEGER,
    phone TEXT,
    designation TEXT DEFAULT 'Lecturer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
);

-- Students
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    roll_number TEXT NOT NULL UNIQUE,
    department_id INTEGER,
    section_id INTEGER,
    semester INTEGER DEFAULT 1,
    phone TEXT,
    photo_path TEXT DEFAULT NULL,
    is_face_registered INTEGER DEFAULT 0,
    face_registered_at TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE SET NULL
);

-- Teacher Course Assignments
CREATE TABLE IF NOT EXISTS teacher_course_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
    UNIQUE (teacher_id, course_id, section_id)
);

-- Attendance Sessions
CREATE TABLE IF NOT EXISTS attendance_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_uuid TEXT NOT NULL UNIQUE,
    course_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    session_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME DEFAULT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
);

-- Attendance Records
CREATE TABLE IF NOT EXISTS attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    attendance_date DATE NOT NULL,
    status TEXT DEFAULT 'Present' CHECK(status IN ('Present', 'Absent', 'Late')),
    confidence_score REAL DEFAULT NULL,
    marked_by TEXT DEFAULT 'AI_FACE_RECOGNITION',
    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE (session_id, student_id)
);

-- Attendance Audit Logs
CREATE TABLE IF NOT EXISTS attendance_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attendance_id INTEGER NOT NULL,
    modified_by_user_id INTEGER NOT NULL,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attendance_id) REFERENCES attendance_records(id) ON DELETE CASCADE,
    FOREIGN KEY (modified_by_user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- System Settings
CREATE TABLE IF NOT EXISTS system_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def seed_database(cursor, mode='sqlite'):
    """Populate default users, courses, students, and demo attendance."""
    print("Seeding initial data...")
    
    # Check if admin already exists
    if mode == 'sqlite':
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    else:
        cursor.execute("SELECT id FROM users WHERE username = %s", ('admin',))
    if cursor.fetchone():
        print("Database already contains data. Skipping seed.")
        return

    # Passwords hashed
    admin_pw = generate_password_hash('admin123')
    teacher_pw = generate_password_hash('teacher123')
    student_pw = generate_password_hash('student123')

    # Helper placeholders
    ph = '?' if mode == 'sqlite' else '%s'

    # 1. Departments
    cursor.execute(f"INSERT INTO departments (name, code) VALUES ({ph}, {ph})", 
                   ('Computer Science & IT', 'CS'))
    dept_id = cursor.lastrowid

    # 2. Sections
    cursor.execute(f"INSERT INTO sections (name, department_id, semester) VALUES ({ph}, {ph}, {ph})",
                   ('BSCS-8A', dept_id, 8))
    sec_id_1 = cursor.lastrowid
    cursor.execute(f"INSERT INTO sections (name, department_id, semester) VALUES ({ph}, {ph}, {ph})",
                   ('BSCS-8B', dept_id, 8))
    sec_id_2 = cursor.lastrowid

    # 3. Courses
    courses = [
        ('CS-401', 'Artificial Intelligence & Computer Vision', dept_id, 3),
        ('CS-402', 'Cloud Computing & Distributed Systems', dept_id, 3),
        ('CS-403', 'Machine Learning & Data Mining', dept_id, 3)
    ]
    course_ids = []
    for c_code, c_name, d_id, ch in courses:
        cursor.execute(f"INSERT INTO courses (course_code, course_name, department_id, credit_hours) VALUES ({ph}, {ph}, {ph}, {ph})",
                       (c_code, c_name, d_id, ch))
        course_ids.append(cursor.lastrowid)

    # 4. Users & Profiles
    # Admin
    cursor.execute(f"INSERT INTO users (username, password_hash, email, role, full_name) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                   ('admin', admin_pw, 'admin@university.edu', 'admin', 'System Administrator'))

    # Teacher
    cursor.execute(f"INSERT INTO users (username, password_hash, email, role, full_name) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                   ('teacher1', teacher_pw, 'dr.tariq@university.edu', 'teacher', 'Prof. Dr. Tariq Mahmood'))
    teacher_user_id = cursor.lastrowid

    cursor.execute(f"INSERT INTO teachers (user_id, employee_id, department_id, phone, designation) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                   (teacher_user_id, 'EMP-1042', dept_id, '+92 300 1234567', 'Associate Professor'))
    teacher_id = cursor.lastrowid

    # Assign Teacher to Courses
    for cid in course_ids:
        cursor.execute(f"INSERT INTO teacher_course_assignments (teacher_id, course_id, section_id) VALUES ({ph}, {ph}, {ph})",
                       (teacher_id, cid, sec_id_1))

    # Students
    demo_students = [
        ('student1', 'ahsan@university.edu', 'Ahsan Ali', '2021-CS-101', '+92 301 1112233', 1),
        ('student2', 'fatima@university.edu', 'Fatima Zahra', '2021-CS-102', '+92 302 2223344', 1),
        ('student3', 'bilal@university.edu', 'Bilal Ahmed', '2021-CS-103', '+92 303 3334455', 0),
        ('student4', 'zainab@university.edu', 'Zainab Bibi', '2021-CS-104', '+92 304 4445566', 1),
        ('student5', 'hamza@university.edu', 'Hamza Tariq', '2021-CS-105', '+92 305 5556677', 0),
    ]

    student_records = []
    for uname, email, fname, roll, phone, is_face in demo_students:
        cursor.execute(f"INSERT INTO users (username, password_hash, email, role, full_name) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                       (uname, student_pw, email, 'student', fname))
        u_id = cursor.lastrowid
        
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') if is_face else None
        cursor.execute(f"INSERT INTO students (user_id, roll_number, department_id, section_id, semester, phone, is_face_registered, face_registered_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                       (u_id, roll, dept_id, sec_id_1, 8, phone, is_face, now_str))
        student_records.append((cursor.lastrowid, roll, fname))

    # 5. System Settings
    settings = [
        ('min_attendance_percent', '75.0', 'Minimum required attendance percentage for exam eligibility'),
        ('duplicate_cooldown_minutes', '60', 'Minutes cooldown before a student can be marked again in same course'),
        ('face_confidence_threshold', '70.0', 'Confidence percentage threshold for AI face recognition'),
        ('institution_name', 'Faculty of Computing & Information Technology', 'Institutional header on reports')
    ]
    for k, v, d in settings:
        cursor.execute(f"INSERT INTO system_settings (setting_key, setting_value, description) VALUES ({ph}, {ph}, {ph})",
                       (k, v, d))

    # 6. Seed Realistic Historical Attendance for the Past 14 Days
    print("Generating demo attendance sessions and records...")
    today = datetime.date.today()
    main_course_id = course_ids[0]

    for day_offset in range(14, 0, -1):
        s_date = today - datetime.timedelta(days=day_offset)
        # Skip Sundays
        if s_date.weekday() == 6:
            continue
            
        uuid_str = f"sess-{s_date.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        cursor.execute(f"INSERT INTO attendance_sessions (session_uuid, course_id, section_id, teacher_id, session_date, start_time, end_time, is_active) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                       (uuid_str, main_course_id, sec_id_1, teacher_id, s_date.strftime('%Y-%m-%d'), '09:00:00', '10:30:00', 0))
        sess_id = cursor.lastrowid

        for s_idx, (st_id, roll, s_name) in enumerate(student_records):
            # Student 5 will have intentionally low attendance (< 75%) to demonstrate low attendance alerts!
            if s_idx == 4:
                # Hamza attends only ~50%
                status = 'Present' if random.random() < 0.50 else 'Absent'
            elif s_idx == 2:
                # Bilal attends ~70%
                status = 'Present' if random.random() < 0.70 else 'Absent'
            else:
                # Others have high attendance (85-95%)
                status = 'Present' if random.random() < 0.90 else ( 'Late' if random.random() < 0.5 else 'Absent' )

            conf = round(random.uniform(85.0, 98.5), 1) if status in ('Present', 'Late') else None
            cursor.execute(f"INSERT INTO attendance_records (session_id, student_id, course_id, attendance_date, status, confidence_score, marked_by, marked_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                           (sess_id, st_id, main_course_id, s_date.strftime('%Y-%m-%d'), status, conf, 'AI_FACE_RECOGNITION', f"{s_date.strftime('%Y-%m-%d')} 09:05:22"))

    print("Initial seed data successfully inserted!")

def init_db(force_mysql=False):
    """Initialize database schema and seed data."""
    use_mysql = force_mysql or (Config.DB_TYPE == 'mysql') or (Config.DB_TYPE == 'auto' and test_mysql_connection())
    
    if use_mysql:
        import pymysql
        print(f"Connecting to MySQL database at {Config.MYSQL_HOST}:{Config.MYSQL_PORT}...")
        try:
            conn = pymysql.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                port=Config.MYSQL_PORT,
                autocommit=True
            )
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DB}` DEFAULT CHARACTER SET utf8mb4;")
            conn.select_db(Config.MYSQL_DB)
            
            # Read schema.sql
            schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
            with open(schema_file, 'r', encoding='utf-8') as f:
                sql_commands = f.read().split(';')
                with conn.cursor() as cur:
                    for command in sql_commands:
                        cmd = command.strip()
                        if cmd:
                            cur.execute(cmd)
            
            with conn.cursor() as cur:
                seed_database(cur, mode='mysql')
            conn.close()
            print("MySQL database initialization complete!")
            return True
        except Exception as e:
            print(f"MySQL error: {e}. Falling back to SQLite.")
    
    # SQLite initialization
    db_path = Config.SQLITE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    print(f"Initializing SQLite database at: {db_path}...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(SQLITE_SCHEMA)
    seed_database(cur, mode='sqlite')
    conn.commit()
    conn.close()
    print("SQLite database initialization complete!")
    return True

if __name__ == '__main__':
    force_mysql = '--mysql' in sys.argv
    init_db(force_mysql=force_mysql)
