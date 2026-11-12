import os
from flask import Flask, render_template, redirect, url_for, session
from config import Config
from database.db import close_db, get_db_mode
from database.init_db import init_db

# Blueprints
from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
from routes.teacher_routes import teacher_bp
from routes.student_routes import student_bp
from routes.attendance_routes import attendance_bp
from routes.report_routes import report_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure required folders exist
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.DATASET_FOLDER, exist_ok=True)
    os.makedirs(Config.MODELS_FOLDER, exist_ok=True)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(report_bp)

    # Register database teardown
    app.teardown_appcontext(close_db)

    # Global template context processor
    @app.context_processor
    def inject_global_vars():
        return {
            'app_title': 'Smart Attendance AI',
            'current_user': session.get('username'),
            'current_role': session.get('role'),
            'current_full_name': session.get('full_name'),
            'db_mode': get_db_mode().upper() if get_db_mode() else 'SQLITE'
        }

    # Root redirect
    @app.route('/')
    def index():
        if 'user_id' in session:
            role = session.get('role')
            if role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif role == 'teacher':
                return redirect(url_for('teacher.dashboard'))
            elif role == 'student':
                return redirect(url_for('student.dashboard'))
        return redirect(url_for('auth.login'))

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', error_code=404, error_message="Page Not Found"), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template('base.html', error_code=500, error_message="Internal Server Error"), 500

    return app

app = create_app()

if __name__ == '__main__':
    # Initialize DB if not initialized
    if not os.path.exists(Config.SQLITE_PATH) and get_db_mode() == 'sqlite':
        init_db()
    
    print("\n" + "=" * 60)
    print(" AI-BASED SMART ATTENDANCE SYSTEM - FYP")
    print(" Server starting on: http://127.0.0.1:5000")
    print("=" * 60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
