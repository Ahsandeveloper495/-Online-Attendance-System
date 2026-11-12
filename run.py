import os
import sys
from app import create_app
from database.init_db import init_db
from config import Config
from database.db import get_db_mode

def main():
    print("\n" + "="*65)
    print("      AI-BASED SMART ATTENDANCE SYSTEM (FYP)")
    print("      OpenCV + LBPH Face Recognition + Flask + MySQL/SQLite")
    print("="*65)

    # Check if database file exists or initialize
    db_mode = get_db_mode()
    print(f"[*] Active Database Mode: {db_mode.upper()}")
    
    if db_mode == 'sqlite' and not os.path.exists(Config.SQLITE_PATH):
        print("[*] Initializing local database and seeding demo records...")
        init_db()

    app = create_app()

    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    
    print(f"\n[+] Application accessible at: http://{host}:{port}")
    print("[+] Test Credentials:")
    print("    - Admin:   username: 'admin'     password: 'admin123'")
    print("    - Teacher: username: 'teacher1'  password: 'teacher123'")
    print("    - Student: username: 'student1'  password: 'student123'")
    print("="*65 + "\n")
    
    app.run(host=host, port=port, debug=True)

if __name__ == '__main__':
    main()
