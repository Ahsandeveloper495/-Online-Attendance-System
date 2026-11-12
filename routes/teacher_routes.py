import uuid
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from routes.auth_routes import login_required, role_required
from database.db import query_db, execute_db
from config import Config

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def get_current_teacher_id():
    """Retrieve teacher profile ID for logged in user."""
    t = query_db("SELECT id FROM teachers WHERE user_id = %s", (session.get('user_id'),), one=True)
    return t['id'] if t else None

@teacher_bp.route('/dashboard')
@role_required('teacher')
def dashboard():
    teacher_id = get_current_teacher_id()
    if not teacher_id:
        flash('Teacher profile not found.', 'danger')
        return redirect(url_for('auth.login'))

    teacher_info = query_db("""
        SELECT t.*, u.full_name, u.email, d.name as department_name
        FROM teachers t
        JOIN users u ON t.user_id = u.id
        LEFT JOIN departments d ON t.department_id = d.id
        WHERE t.id = %s
    """, (teacher_id,), one=True)

    # Assigned courses & sections
    assigned_classes = query_db("""
        SELECT a.id as assignment_id, c.id as course_id, c.course_code, c.course_name,
               s.id as section_id, s.name as section_name,
               (SELECT COUNT(*) FROM students WHERE section_id = s.id) as enrolled_students
        FROM teacher_course_assignments a
        JOIN courses c ON a.course_id = c.id
        JOIN sections s ON a.section_id = s.id
        WHERE a.teacher_id = %s
        ORDER BY c.course_code
    """, (teacher_id,))

    # Today's active sessions
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    active_sessions = query_db("""
        SELECT sess.*, c.course_code, c.course_name, s.name as section_name,
               (SELECT COUNT(*) FROM attendance_records WHERE session_id = sess.id) as marked_count
        FROM attendance_sessions sess
        JOIN courses c ON sess.course_id = c.id
        JOIN sections s ON sess.section_id = s.id
        WHERE sess.teacher_id = %s AND sess.session_date = %s
        ORDER BY sess.start_time DESC
    """, (teacher_id, today_str))

    # Low attendance alert count for teacher's courses
    low_attendance_students = query_db("""
        SELECT s.id, s.roll_number, u.full_name, c.course_code, c.course_name,
               COUNT(a.id) as total_sessions,
               SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended
        FROM teacher_course_assignments tca
        JOIN students s ON s.section_id = tca.section_id
        JOIN users u ON s.user_id = u.id
        JOIN courses c ON tca.course_id = c.id
        LEFT JOIN attendance_records a ON s.id = a.student_id AND a.course_id = c.id
        WHERE tca.teacher_id = %s
        GROUP BY s.id, s.roll_number, u.full_name, c.course_code, c.course_name
        HAVING total_sessions > 0 AND (attended * 100.0 / total_sessions) < 75.0
    """, (teacher_id,))

    return render_template('teacher/dashboard.html',
                           teacher=teacher_info,
                           assigned_classes=assigned_classes,
                           active_sessions=active_sessions,
                           low_attendance_count=len(low_attendance_students))

@teacher_bp.route('/session/start', methods=['GET', 'POST'])
@role_required('teacher')
def start_session():
    teacher_id = get_current_teacher_id()
    if request.method == 'POST':
        assignment_id = request.form.get('assignment_id')
        assignment = query_db("""
            SELECT * FROM teacher_course_assignments
            WHERE id = %s AND teacher_id = %s
        """, (assignment_id, teacher_id), one=True)

        if not assignment:
            flash('Invalid class assignment selected.', 'danger')
            return redirect(url_for('teacher.start_session'))

        session_uuid = str(uuid.uuid4())
        today = datetime.date.today().strftime('%Y-%m-%d')
        now_time = datetime.datetime.now().strftime('%H:%M:%S')

        session_id = execute_db("""
            INSERT INTO attendance_sessions (session_uuid, course_id, section_id, teacher_id, session_date, start_time, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
        """, (session_uuid, assignment['course_id'], assignment['section_id'], teacher_id, today, now_time))

        return redirect(url_for('teacher.attendance_console', session_uuid=session_uuid))

    assigned_classes = query_db("""
        SELECT a.id as assignment_id, c.course_code, c.course_name, s.name as section_name
        FROM teacher_course_assignments a
        JOIN courses c ON a.course_id = c.id
        JOIN sections s ON a.section_id = s.id
        WHERE a.teacher_id = %s
    """, (teacher_id,))

    return render_template('teacher/start_session.html', assigned_classes=assigned_classes)

@teacher_bp.route('/session/<session_uuid>')
@role_required('teacher')
def attendance_console(session_uuid):
    teacher_id = get_current_teacher_id()
    sess = query_db("""
        SELECT sess.*, c.course_code, c.course_name, s.name as section_name, s.id as section_id
        FROM attendance_sessions sess
        JOIN courses c ON sess.course_id = c.id
        JOIN sections s ON sess.section_id = s.id
        WHERE sess.session_uuid = %s AND sess.teacher_id = %s
    """, (session_uuid, teacher_id), one=True)

    if not sess:
        flash('Attendance session not found or you are not authorized to view it.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    # Get all students in this section
    class_students = query_db("""
        SELECT s.id as student_id, s.roll_number, u.full_name, s.is_face_registered,
               ar.id as record_id, ar.status, ar.marked_at, ar.confidence_score
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN attendance_records ar ON ar.student_id = s.id AND ar.session_id = %s
        WHERE s.section_id = %s
        ORDER BY s.roll_number ASC
    """, (sess['id'], sess['section_id']))

    marked_present = sum(1 for st in class_students if st['status'] == 'Present')
    marked_late = sum(1 for st in class_students if st['status'] == 'Late')
    total_enrolled = len(class_students)

    return render_template('teacher/attendance_session.html',
                           session_data=sess,
                           students=class_students,
                           present_count=marked_present,
                           late_count=marked_late,
                           total_enrolled=total_enrolled)

@teacher_bp.route('/session/<session_uuid>/close', methods=['POST'])
@role_required('teacher')
def close_session(session_uuid):
    teacher_id = get_current_teacher_id()
    now_time = datetime.datetime.now().strftime('%H:%M:%S')
    
    # Optional: Mark remaining unmarked students in this section as Absent
    sess = query_db("SELECT id, course_id, section_id, session_date FROM attendance_sessions WHERE session_uuid = %s AND teacher_id = %s",
                    (session_uuid, teacher_id), one=True)
    if sess:
        execute_db("UPDATE attendance_sessions SET is_active = 0, end_time = %s WHERE id = %s", (now_time, sess['id']))
        
        # Auto-mark absent for students not marked in this session
        unmarked = query_db("""
            SELECT s.id FROM students s
            WHERE s.section_id = %s AND s.id NOT IN (
                SELECT student_id FROM attendance_records WHERE session_id = %s
            )
        """, (sess['section_id'], sess['id']))
        for u in unmarked:
            execute_db("""
                INSERT INTO attendance_records (session_id, student_id, course_id, attendance_date, status, marked_by)
                VALUES (%s, %s, %s, %s, 'Absent', 'MANUAL_TEACHER')
            """, (sess['id'], u['id'], sess['course_id'], sess['session_date']))

        flash('Attendance session completed and closed. Absent records marked automatically.', 'success')
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/manual-attendance', methods=['GET', 'POST'])
@role_required('teacher', 'admin')
def manual_attendance():
    teacher_id = get_current_teacher_id() if session.get('role') == 'teacher' else None

    if request.method == 'POST':
        attendance_id = request.form.get('attendance_id')
        new_status = request.form.get('status')
        reason = request.form.get('reason', '').strip()

        if not reason:
            flash('Please provide an audit reason for manual correction.', 'danger')
            return redirect(request.referrer or url_for('teacher.manual_attendance'))

        rec = query_db("SELECT * FROM attendance_records WHERE id = %s", (attendance_id,), one=True)
        if rec:
            prev_status = rec['status']
            execute_db("UPDATE attendance_records SET status = %s WHERE id = %s", (new_status, attendance_id))
            
            # Log into audit trail
            execute_db("""
                INSERT INTO attendance_audit_logs (attendance_id, modified_by_user_id, previous_status, new_status, reason)
                VALUES (%s, %s, %s, %s, %s)
            """, (attendance_id, session['user_id'], prev_status, new_status, reason))

            flash(f"Status updated from '{prev_status}' to '{new_status}' with audit trail logged.", 'success')
        return redirect(request.referrer or url_for('teacher.manual_attendance'))

    # Filters
    course_id = request.args.get('course_id')
    date_filter = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))

    sql = """
        SELECT a.id as record_id, a.attendance_date, a.status, a.confidence_score, a.marked_by, a.marked_at,
               s.roll_number, u.full_name as student_name,
               c.course_code, c.course_name,
               sec.name as section_name
        FROM attendance_records a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        JOIN courses c ON a.course_id = c.id
        JOIN attendance_sessions sess ON a.session_id = sess.id
        JOIN sections sec ON sess.section_id = sec.id
        WHERE a.attendance_date = %s
    """
    params = [date_filter]

    if course_id:
        sql += " AND a.course_id = %s"
        params.append(course_id)

    if teacher_id:
        sql += " AND sess.teacher_id = %s"
        params.append(teacher_id)

    sql += " ORDER BY s.roll_number ASC"
    records = query_db(sql, params)

    # Get available courses for dropdown
    if teacher_id:
        available_courses = query_db("""
            SELECT DISTINCT c.id, c.course_code, c.course_name
            FROM teacher_course_assignments a
            JOIN courses c ON a.course_id = c.id
            WHERE a.teacher_id = %s
        """, (teacher_id,))
    else:
        available_courses = query_db("SELECT id, course_code, course_name FROM courses")

    return render_template('teacher/manual_attendance.html',
                           records=records,
                           courses=available_courses,
                           selected_date=date_filter,
                           selected_course=course_id)

@teacher_bp.route('/low-attendance')
@role_required('teacher')
def low_attendance():
    teacher_id = get_current_teacher_id()
    
    # Calculate attendance percentage per student per course
    students = query_db("""
        SELECT s.id as student_id, s.roll_number, s.phone, u.full_name, u.email,
               c.id as course_id, c.course_code, c.course_name,
               sec.name as section_name,
               COUNT(a.id) as total_sessions,
               SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
               SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count
        FROM teacher_course_assignments tca
        JOIN students s ON s.section_id = tca.section_id
        JOIN users u ON s.user_id = u.id
        JOIN courses c ON tca.course_id = c.id
        JOIN sections sec ON s.section_id = sec.id
        LEFT JOIN attendance_records a ON s.id = a.student_id AND a.course_id = c.id
        WHERE tca.teacher_id = %s
        GROUP BY s.id, s.roll_number, s.phone, u.full_name, u.email, c.id, c.course_code, c.course_name, sec.name
        HAVING total_sessions > 0
        ORDER BY (attended * 100.0 / total_sessions) ASC
    """, (teacher_id,))

    defaulters = []
    for st in students:
        pct = round((st['attended'] / st['total_sessions']) * 100.0, 1)
        st['attendance_percent'] = pct
        if pct < Config.MIN_ATTENDANCE_PERCENT:
            defaulters.append(st)

    return render_template('teacher/low_attendance.html',
                           defaulters=defaulters,
                           threshold=Config.MIN_ATTENDANCE_PERCENT)
