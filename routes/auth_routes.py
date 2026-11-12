from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from database.db import query_db, execute_db

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'warning')
                return redirect(url_for('auth.login'))
            user_role = session.get('role')
            if user_role not in roles:
                flash('Access denied: You do not have permission to view this resource.', 'danger')
                if user_role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                elif user_role == 'teacher':
                    return redirect(url_for('teacher.dashboard'))
                elif user_role == 'student':
                    return redirect(url_for('student.dashboard'))
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'teacher':
            return redirect(url_for('teacher.dashboard'))
        elif role == 'student':
            return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role_selected = request.form.get('role_hint', '').strip()

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('auth/login.html')

        user = query_db("SELECT * FROM users WHERE username = %s AND is_active = 1", (username,), one=True)
        
        if user and check_password_hash(user['password_hash'], password):
            # Check role if specified
            if role_selected and user['role'] != role_selected:
                flash(f"Invalid account for role '{role_selected}'. This user is registered as a {user['role'].title()}.", 'warning')
                return render_template('auth/login.html')

            # Populate session
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            session['email'] = user['email']

            # If teacher, get teacher_id
            if user['role'] == 'teacher':
                t_record = query_db("SELECT id FROM teachers WHERE user_id = %s", (user['id'],), one=True)
                session['teacher_id'] = t_record['id'] if t_record else None
                flash(f"Welcome back, {user['full_name']}!", 'success')
                return redirect(url_for('teacher.dashboard'))

            # If student, get student_id and roll_number
            elif user['role'] == 'student':
                s_record = query_db("SELECT id, roll_number FROM students WHERE user_id = %s", (user['id'],), one=True)
                session['student_id'] = s_record['id'] if s_record else None
                session['roll_number'] = s_record['roll_number'] if s_record else None
                flash(f"Welcome back, {user['full_name']}!", 'success')
                return redirect(url_for('student.dashboard'))

            else:  # Admin
                flash(f"Welcome back, Administrator!", 'success')
                return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if not new_pw or new_pw != confirm_pw:
        flash('New passwords do not match or cannot be empty.', 'danger')
        return redirect(request.referrer or url_for('auth.login'))

    user = query_db("SELECT password_hash FROM users WHERE id = %s", (session['user_id'],), one=True)
    if user and check_password_hash(user['password_hash'], current_pw):
        hashed = generate_password_hash(new_pw)
        execute_db("UPDATE users SET password_hash = %s WHERE id = %s", (hashed, session['user_id']))
        flash('Password successfully updated!', 'success')
    else:
        flash('Incorrect current password.', 'danger')

    return redirect(request.referrer or url_for('auth.login'))
