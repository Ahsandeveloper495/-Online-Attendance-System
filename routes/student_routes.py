from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from routes.auth_routes import login_required, role_required
from database.db import query_db
from config import Config

student_bp = Blueprint('student', __name__, url_prefix='/student')

def get_current_student():
    """Fetch current logged-in student profile."""
    user_id = session.get('user_id')
    return query_db("""
        SELECT s.*, u.full_name, u.email, u.username,
               d.name as department_name, d.code as department_code,
               sec.name as section_name
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN departments d ON s.department_id = d.id
        LEFT JOIN sections sec ON s.section_id = sec.id
        WHERE s.user_id = %s
    """, (user_id,), one=True)

@student_bp.route('/dashboard')
@role_required('student')
def dashboard():
    student = get_current_student()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('auth.login'))

    # Overall Attendance Metrics
    stats = query_db("""
        SELECT 
            COUNT(*) as total_classes,
            SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended_classes,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_classes,
            SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_classes,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_classes
        FROM attendance_records
        WHERE student_id = %s
    """, (student['id'],), one=True)

    total_classes = stats['total_classes'] or 0
    attended_classes = stats['attended_classes'] or 0
    overall_pct = round((attended_classes / total_classes * 100), 1) if total_classes > 0 else 0.0

    # Course-wise Attendance Breakdown
    course_breakdown = query_db("""
        SELECT c.id as course_id, c.course_code, c.course_name, c.credit_hours,
               COUNT(a.id) as total_sessions,
               SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
               SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent
        FROM courses c
        JOIN teacher_course_assignments tca ON c.id = tca.course_id AND tca.section_id = %s
        LEFT JOIN attendance_records a ON c.id = a.course_id AND a.student_id = %s
        GROUP BY c.id, c.course_code, c.course_name, c.credit_hours
    """, (student['section_id'], student['id']))

    has_low_attendance = False
    for cb in course_breakdown:
        tot = cb['total_sessions'] or 0
        att = cb['attended'] or 0
        pct = round((att / tot * 100), 1) if tot > 0 else 100.0
        cb['percent'] = pct
        if pct < Config.MIN_ATTENDANCE_PERCENT and tot > 0:
            has_low_attendance = True

    # Recent attendance logs
    recent_logs = query_db("""
        SELECT a.*, c.course_code, c.course_name
        FROM attendance_records a
        JOIN courses c ON a.course_id = c.id
        WHERE a.student_id = %s
        ORDER BY a.attendance_date DESC, a.marked_at DESC
        LIMIT 7
    """, (student['id'],))

    return render_template('student/dashboard.html',
                           student=student,
                           stats=stats,
                           overall_pct=overall_pct,
                           course_breakdown=course_breakdown,
                           has_low_attendance=has_low_attendance,
                           recent_logs=recent_logs,
                           min_threshold=Config.MIN_ATTENDANCE_PERCENT)

@student_bp.route('/history')
@role_required('student')
def history():
    student = get_current_student()
    course_filter = request.args.get('course_id')

    sql = """
        SELECT a.*, c.course_code, c.course_name, sess.session_date, sess.start_time
        FROM attendance_records a
        JOIN courses c ON a.course_id = c.id
        JOIN attendance_sessions sess ON a.session_id = sess.id
        WHERE a.student_id = %s
    """
    params = [student['id']]

    if course_filter:
        sql += " AND a.course_id = %s"
        params.append(course_filter)

    sql += " ORDER BY a.attendance_date DESC, a.marked_at DESC"
    all_logs = query_db(sql, params)

    enrolled_courses = query_db("""
        SELECT DISTINCT c.id, c.course_code, c.course_name
        FROM courses c
        JOIN teacher_course_assignments tca ON c.id = tca.course_id
        WHERE tca.section_id = %s
    """, (student['section_id'],))

    return render_template('student/history.html',
                           student=student,
                           records=all_logs,
                           courses=enrolled_courses,
                           selected_course=course_filter)

@student_bp.route('/profile')
@role_required('student')
def profile():
    student = get_current_student()
    return render_template('student/profile.html', student=student)
