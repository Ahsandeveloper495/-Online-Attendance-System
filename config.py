import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-attendance-fyp-secret-key-2026-secure')
    
    # Database Settings
    # Supports MySQL (default) and SQLite (automatic fallback if MySQL service is not running)
    DB_TYPE = os.environ.get('DB_TYPE', 'auto') # 'mysql', 'sqlite', or 'auto'
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'smart_attendance_db')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    
    SQLITE_PATH = os.path.join(BASE_DIR, 'database', 'smart_attendance.db')
    
    # Paths
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    DATASET_FOLDER = os.path.join(BASE_DIR, 'dataset')
    MODELS_FOLDER = os.path.join(BASE_DIR, 'models')
    
    FACE_CASCADE_PATH = os.path.join(MODELS_FOLDER, 'haarcascade_frontalface_default.xml')
    EYE_CASCADE_PATH = os.path.join(MODELS_FOLDER, 'haarcascade_eye.xml')
    TRAINED_MODEL_PATH = os.path.join(MODELS_FOLDER, 'trainer.yml')
    
    # System & Attendance Rules
    MIN_ATTENDANCE_PERCENT = 75.0
    FACE_CONFIDENCE_THRESHOLD = 75.0  # Percentage or LBPH distance equivalent
    DUPLICATE_INTERVAL_MINUTES = 60    # Cooldown window to prevent duplicate records
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # 16 MB max upload
