import os
import shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash
from routes.auth_routes import login_required, role_required
from database.db import query_db, execute_db
from ai_engine.face_recognizer import recognizer
from config import Config

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@role_required('admin')
def dashboard():
    # Key statistics
    total_students = query_db("SELECT COUNT(*) as count FROM students", one=True)['count']
    total_teachers = query_db("SELECT COUNT(*) as count FROM teachers", one=True)['count']
    total_courses = query_db("SELECT COUNT(*) as count FROM courses", one=True)['count']
    faces_registered = query_db("SELECT COUNT(*) as count FROM students WHERE is_face_registered = 1", one=True)['count']

    # Total attendance stats
    total_records = query_db("SELECT COUNT(*) as count FROM attendance_records", one=True)['count']
    present_records = query_db("SELECT COUNT(*) as count FROM attendance_records WHERE status IN ('Present', 'Late')", one=True)['count']
    overall_attendance_pct = round((present_records / total_records * 100), 1) if total_records > 0 else 0.0

    # Low attendance count (< 75%)
    # Calculate each student's attendance percentage
    student_stats = query_db("""
        SELECT s.id, s.roll_number, u.full_name,
               COUNT(a.id) as total_sessions,
               SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as present_count
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN attendance_records a ON s.id = a.student_id
        GROUP BY s.id, s.roll_number, u.full_name
    """)
    defaulters_count = 0
    for s in student_stats:
        if s['total_sessions'] > 0:
            pct = (s['present_count'] / s['total_sessions']) * 100.0
            if pct < Config.MIN_ATTENDANCE_PERCENT:
                defaulters_count += 1

    # Recent attendance records
    recent_records = query_db("""
        SELECT a.id, a.attendance_date, a.status, a.confidence_score, a.marked_by, a.marked_at,
               s.roll_number, u.full_name as student_name,
               c.course_name, c.course_code,
               sec.name as section_name
        FROM attendance_records a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        JOIN courses c ON a.course_id = c.id
        JOIN attendance_sessions sess ON a.session_id = sess.id
        JOIN sections sec ON sess.section_id = sec.id
        ORDER BY a.marked_at DESC
        LIMIT 10
    """)

    # AI Model status
    model_status = {
        'is_trained': recognizer.is_trained,
        'registered_faces': faces_registered,
        'model_file_exists': os.path.exists(Config.TRAINED_MODEL_PATH)
    }

    return render_template('admin/dashboard.html',
                           total_students=total_students,
                           total_teachers=total_teachers,
                           total_courses=total_courses,
                           faces_registered=faces_registered,
                           overall_attendance_pct=overall_attendance_pct,
                           defaulters_count=defaulters_count,
                           recent_records=recent_records,
                           model_status=model_status)

@admin_bp.route('/students', methods=['GET', 'POST'])
@role_required('admin')
def students():
    if request.method == 'POST':
        # Add new student
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', 'student123').strip()
        roll_number = request.form.get('roll_number', '').strip().upper()
        department_id = request.form.get('department_id') or None
        section_id = request.form.get('section_id') or None
        semester = int(request.form.get('semester', 1))
        phone = request.form.get('phone', '').strip()

        if not full_name or not username or not email or not roll_number:
            flash('Full Name, Username, Email, and Roll Number are required.', 'danger')
            return redirect(url_for('admin.students'))

        # Check duplicates
        existing = query_db("SELECT id FROM users WHERE username = %s OR email = %s", (username, email), one=True)
        if existing:
            flash('Username or Email already registered.', 'danger')
            return redirect(url_for('admin.students'))
        
        existing_roll = query_db("SELECT id FROM students WHERE roll_number = %s", (roll_number,), one=True)
        if existing_roll:
            flash(f"Roll Number '{roll_number}' already exists.", 'danger')
            return redirect(url_for('admin.students'))

        # Insert user
        pw_hash = generate_password_hash(password)
        user_id = execute_db("INSERT INTO users (username, password_hash, email, role, full_name) VALUES (%s, %s, %s, 'student', %s)",
                             (username, pw_hash, email, full_name))

        # Insert student
        student_id = execute_db("""
            INSERT INTO students (user_id, roll_number, department_id, section_id, semester, phone, is_face_registered)
            VALUES (%s, %s, %s, %s, %s, %s, 0)
        """, (user_id, roll_number, department_id, section_id, semester, phone))

        flash(f"Student '{full_name}' ({roll_number}) registered successfully! You can now enroll their facial data.", 'success')
        return redirect(url_for('admin.student_register_face', student_id=student_id))

    # GET: List all students
    all_students = query_db("""
        SELECT s.id as student_id, s.roll_number, s.semester, s.phone, s.is_face_registered, s.face_registered_at,
               u.id as user_id, u.username, u.email, u.full_name, u.is_active,
               d.name as department_name, sec.name as section_name
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN departments d ON s.department_id = d.id
        LEFT JOIN sections sec ON s.section_id = sec.id
        ORDER BY s.roll_number ASC
    """)
    departments = query_db("SELECT * FROM departments ORDER BY name")
    sections = query_db("SELECT * FROM sections ORDER BY name")

    return render_template('admin/students.html',
                           students=all_students,
                           departments=departments,
                           sections=sections)

@admin_bp.route('/students/register-face/<int:student_id>')
@role_required('admin')
def student_register_face(student_id):
    student = query_db("""
        SELECT s.*, u.full_name, u.email, d.name as dept_name, sec.name as sec_name
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN departments d ON s.department_id = d.id
        LEFT JOIN sections sec ON s.section_id = sec.id
        WHERE s.id = %s
    """, (student_id,), one=True)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('admin.students'))

    return render_template('admin/student_register.html', student=student)

@admin_bp.route('/students/delete/<int:student_id>', methods=['POST'])
@role_required('admin')
def delete_student(student_id):
    student = query_db("SELECT user_id, roll_number FROM students WHERE id = %s", (student_id,), one=True)
    if student:
        # Delete dataset folder if exists
        dataset_path = os.path.join(Config.DATASET_FOLDER, f"student_{student_id}")
        if os.path.exists(dataset_path):
            shutil.rmtree(dataset_path, ignore_errors=True)
            
        # Delete user record (cascades to student and attendance)
        execute_db("DELETE FROM users WHERE id = %s", (student['user_id'],))
        
        # Retrain model if required
        recognizer.train()
        flash(f"Student {student['roll_number']} removed successfully.", 'success')
    else:
        flash('Student not found.', 'danger')
    return redirect(url_for('admin.students'))

@admin_bp.route('/retrain-model', methods=['POST'])
@role_required('admin')
def retrain_model():
    success, msg = recognizer.train()
    if success:
        flash(f"AI Face Recognition Model updated! {msg}", 'success')
    else:
        flash(f"Training notification: {msg}", 'warning')
    return redirect(request.referrer or url_for('admin.dashboard'))

@admin_bp.route('/teachers', methods=['GET', 'POST'])
@role_required('admin')
def teachers():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_teacher':
            full_name = request.form.get('full_name', '').strip()
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', 'teacher123').strip()
            employee_id = request.form.get('employee_id', '').strip()
            department_id = request.form.get('department_id') or None
            designation = request.form.get('designation', 'Lecturer').strip()
            phone = request.form.get('phone', '').strip()

            existing = query_db("SELECT id FROM users WHERE username = %s OR email = %s", (username, email), one=True)
            if existing:
                flash('Username or Email already registered.', 'danger')
                return redirect(url_for('admin.teachers'))

            pw_hash = generate_password_hash(password)
            user_id = execute_db("INSERT INTO users (username, password_hash, email, role, full_name) VALUES (%s, %s, %s, 'teacher', %s)",
                                 (username, pw_hash, email, full_name))
            execute_db("""
                INSERT INTO teachers (user_id, employee_id, department_id, phone, designation)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, employee_id, department_id, phone, designation))
            flash(f"Teacher '{full_name}' added successfully!", 'success')

        elif action == 'assign_course':
            teacher_id = request.form.get('teacher_id')
            course_id = request.form.get('course_id')
            section_id = request.form.get('section_id')
            
            # Check duplicate assignment
            existing = query_db("SELECT id FROM teacher_course_assignments WHERE teacher_id = %s AND course_id = %s AND section_id = %s",
                                (teacher_id, course_id, section_id), one=True)
            if not existing:
                execute_db("INSERT INTO teacher_course_assignments (teacher_id, course_id, section_id) VALUES (%s, %s, %s)",
                           (teacher_id, course_id, section_id))
                flash('Course successfully assigned to teacher!', 'success')
            else:
                flash('This teacher is already assigned to this course and section.', 'warning')

        return redirect(url_for('admin.teachers'))

    all_teachers = query_db("""
        SELECT t.id as teacher_id, t.employee_id, t.phone, t.designation,
               u.id as user_id, u.full_name, u.username, u.email,
               d.name as department_name,
               (SELECT COUNT(*) FROM teacher_course_assignments WHERE teacher_id = t.id) as assigned_classes_count
        FROM teachers t
        JOIN users u ON t.user_id = u.id
        LEFT JOIN departments d ON t.department_id = d.id
        ORDER BY u.full_name ASC
    """)
    departments = query_db("SELECT * FROM departments ORDER BY name")
    courses = query_db("SELECT * FROM courses ORDER BY course_code")
    sections = query_db("SELECT * FROM sections ORDER BY name")
    assignments = query_db("""
        SELECT a.id, t.id as teacher_id, u.full_name as teacher_name,
               c.course_code, c.course_name, s.name as section_name
        FROM teacher_course_assignments a
        JOIN teachers t ON a.teacher_id = t.id
        JOIN users u ON t.user_id = u.id
        JOIN courses c ON a.course_id = c.id
        JOIN sections s ON a.section_id = s.id
        ORDER BY u.full_name, c.course_code
    """)

    return render_template('admin/teachers.html',
                           teachers=all_teachers,
                           departments=departments,
                           courses=courses,
                           sections=sections,
                           assignments=assignments)

@admin_bp.route('/courses', methods=['GET', 'POST'])
@role_required('admin')
def courses():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_course':
            course_code = request.form.get('course_code', '').strip().upper()
            course_name = request.form.get('course_name', '').strip()
            department_id = request.form.get('department_id') or None
            credit_hours = int(request.form.get('credit_hours', 3))
            
            try:
                execute_db("INSERT INTO courses (course_code, course_name, department_id, credit_hours) VALUES (%s, %s, %s, %s)",
                           (course_code, course_name, department_id, credit_hours))
                flash(f"Course '{course_code} - {course_name}' created successfully!", 'success')
            except Exception as e:
                flash(f"Error creating course: {e}", 'danger')

        elif action == 'add_section':
            name = request.form.get('name', '').strip()
            department_id = request.form.get('department_id') or None
            semester = int(request.form.get('semester', 1))
            
            execute_db("INSERT INTO sections (name, department_id, semester) VALUES (%s, %s, %s)",
                       (name, department_id, semester))
            flash(f"Section '{name}' created successfully!", 'success')

        return redirect(url_for('admin.courses'))

    all_courses = query_db("""
        SELECT c.*, d.name as department_name,
               (SELECT COUNT(*) FROM teacher_course_assignments WHERE course_id = c.id) as teachers_count
        FROM courses c
        LEFT JOIN departments d ON c.department_id = d.id
        ORDER BY c.course_code
    """)
    all_sections = query_db("""
        SELECT s.*, d.name as department_name,
               (SELECT COUNT(*) FROM students WHERE section_id = s.id) as students_count
        FROM sections s
        LEFT JOIN departments d ON s.department_id = d.id
        ORDER BY s.name
    """)
    departments = query_db("SELECT * FROM departments ORDER BY name")

    return render_template('admin/courses.html',
                           courses=all_courses,
                           sections=all_sections,
                           departments=departments)

@admin_bp.route('/audit-logs')
@role_required('admin')
def audit_logs():
    logs = query_db("""
        SELECT l.*, u.full_name as modified_by_name, u.role as modified_by_role,
               s.roll_number, stu_u.full_name as student_name,
               c.course_code, c.course_name,
               a.attendance_date
        FROM attendance_audit_logs l
        JOIN users u ON l.modified_by_user_id = u.id
        JOIN attendance_records a ON l.attendance_id = a.id
        JOIN students s ON a.student_id = s.id
        JOIN users stu_u ON s.user_id = stu_u.id
        JOIN courses c ON a.course_id = c.id
        ORDER BY l.timestamp DESC
        LIMIT 100
    """)
    return render_template('admin/audit_logs.html', logs=logs)

@admin_bp.route('/settings', methods=['GET', 'POST'])
@role_required('admin')
def settings():
    if request.method == 'POST':
        min_pct = request.form.get('min_attendance_percent', '75.0')
        cooldown = request.form.get('duplicate_cooldown_minutes', '60')
        conf = request.form.get('face_confidence_threshold', '70.0')
        inst_name = request.form.get('institution_name', 'Faculty of Computing & Information Technology')

        execute_db("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'min_attendance_percent'", (min_pct,))
        execute_db("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'duplicate_cooldown_minutes'", (cooldown,))
        execute_db("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'face_confidence_threshold'", (conf,))
        execute_db("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'institution_name'", (inst_name,))

        flash('System settings updated successfully!', 'success')
        return redirect(url_for('admin.settings'))

    current_settings = {}
    rows = query_db("SELECT setting_key, setting_value, description FROM system_settings")
    for r in rows:
        current_settings[r['setting_key']] = r['setting_value']

    return render_template('admin/settings.html', settings=current_settings)
