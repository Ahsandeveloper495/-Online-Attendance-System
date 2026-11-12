import datetime
from flask import Blueprint, request, jsonify, session
from routes.auth_routes import login_required
from database.db import query_db, execute_db
from ai_engine.face_detector import detector, FaceDetector
from ai_engine.face_recognizer import recognizer
from ai_engine.liveness_checker import liveness_checker
from config import Config

attendance_bp = Blueprint('attendance_api', __name__, url_prefix='/api')

@attendance_bp.route('/recognize_frame', methods=['POST'])
def recognize_frame():
    """Real-time webcam frame face recognition and automatic attendance marking."""
    data = request.get_json() or {}
    image_b64 = data.get('image')
    session_id = data.get('session_id')

    if not image_b64 or not session_id:
        return jsonify({'success': False, 'message': 'Missing image or session_id'}), 400

    # Validate active session
    active_sess = query_db("""
        SELECT sess.*, c.course_name, s.name as section_name
        FROM attendance_sessions sess
        JOIN courses c ON sess.course_id = c.id
        JOIN sections s ON sess.section_id = s.id
        WHERE sess.id = %s AND sess.is_active = 1
    """, (session_id,), one=True)

    if not active_sess:
        return jsonify({'success': False, 'message': 'Attendance session is not active or invalid.'}), 404

    # Decode frame
    frame = detector.decode_base64_frame(image_b64)
    if frame is None:
        return jsonify({'success': False, 'message': 'Invalid frame format'}), 400

    # Detect faces
    detected_faces = detector.detect_faces(frame)
    if not detected_faces:
        return jsonify({'success': True, 'status': 'NO_FACE', 'faces': []})

    results = []
    for face in detected_faces:
        box = face['box']
        roi = face['face_roi']
        eyes_count = face['eyes_count']

        # Liveness check
        liveness = liveness_checker.verify_liveness(roi, eyes_count)

        # LBPH Recognition
        prediction = recognizer.predict(roi)

        if prediction['matched'] and prediction['student_id']:
            st_id = prediction['student_id']

            # Lookup student in database
            student = query_db("""
                SELECT s.id as student_id, s.roll_number, s.section_id, u.full_name
                FROM students s
                JOIN users u ON s.user_id = u.id
                WHERE s.id = %s
            """, (st_id,), one=True)

            if student:
                # Check if student is enrolled in this session's section
                if student['section_id'] != active_sess['section_id']:
                    results.append({
                        'status': 'WRONG_SECTION',
                        'box': box,
                        'student': {
                            'roll_number': student['roll_number'],
                            'full_name': student['full_name']
                        },
                        'confidence': prediction['confidence'],
                        'message': f"Student {student['roll_number']} is not enrolled in {active_sess['section_name']}."
                    })
                    continue

                # Anti-Duplicate Check: Is this student already marked in this session?
                existing_record = query_db("""
                    SELECT id, status, marked_at FROM attendance_records
                    WHERE session_id = %s AND student_id = %s
                """, (session_id, st_id), one=True)

                if existing_record:
                    results.append({
                        'status': 'ALREADY_MARKED',
                        'box': box,
                        'student': {
                            'student_id': student['student_id'],
                            'roll_number': student['roll_number'],
                            'full_name': student['full_name']
                        },
                        'confidence': prediction['confidence'],
                        'marked_at': str(existing_record['marked_at']),
                        'message': f"{student['full_name']} ({student['roll_number']}) is already marked {existing_record['status']}."
                    })
                else:
                    # Mark Attendance Automatically in Database!
                    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    today_str = active_sess['session_date']
                    
                    rec_id = execute_db("""
                        INSERT INTO attendance_records 
                        (session_id, student_id, course_id, attendance_date, status, confidence_score, marked_by, marked_at)
                        VALUES (%s, %s, %s, %s, 'Present', %s, 'AI_FACE_RECOGNITION', %s)
                    """, (session_id, st_id, active_sess['course_id'], today_str, prediction['confidence'], now_str))

                    results.append({
                        'status': 'MARKED_PRESENT',
                        'box': box,
                        'student': {
                            'student_id': student['student_id'],
                            'roll_number': student['roll_number'],
                            'full_name': student['full_name']
                        },
                        'confidence': prediction['confidence'],
                        'marked_at': now_str,
                        'message': f"Attendance marked for {student['full_name']} ({student['roll_number']}) with {prediction['confidence']}% match!"
                    })
            else:
                results.append({
                    'status': 'UNKNOWN_FACE',
                    'box': box,
                    'confidence': prediction['confidence'],
                    'message': 'Face detected but student profile not found in database.'
                })
        else:
            results.append({
                'status': 'UNKNOWN_FACE',
                'box': box,
                'confidence': prediction['confidence'],
                'message': 'Unknown face or confidence below threshold.'
            })

    return jsonify({
        'success': True,
        'status': 'PROCESSED',
        'faces': results
    })

@attendance_bp.route('/register_face_samples', methods=['POST'])
def register_face_samples():
    """Collect webcam face frames and train LBPH model for a student."""
    data = request.get_json() or {}
    student_id = data.get('student_id')
    samples = data.get('samples', [])

    if not student_id or not samples:
        return jsonify({'success': False, 'message': 'Missing student_id or samples'}), 400

    student = query_db("""
        SELECT s.id, s.roll_number, u.full_name
        FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = %s
    """, (student_id,), one=True)

    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    # Decode frames
    frames = []
    for b64 in samples:
        img = detector.decode_base64_frame(b64)
        if img is not None:
            frames.append(img)

    if not frames:
        return jsonify({'success': False, 'message': 'No valid frames could be decoded'}), 400

    # Save samples & train
    success, saved_count, msg = recognizer.save_samples_and_train(
        student_id=student['id'],
        roll_number=student['roll_number'],
        full_name=student['full_name'],
        frames_list=frames
    )

    if success or saved_count > 0:
        # Update database record
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        execute_db("""
            UPDATE students 
            SET is_face_registered = 1, face_registered_at = %s
            WHERE id = %s
        """, (now_str, student_id))

        return jsonify({
            'success': True,
            'message': f"Successfully captured {saved_count} face samples and retrained model for {student['full_name']}!",
            'saved_count': saved_count
        })
    else:
        return jsonify({'success': False, 'message': f"Failed to train model: {msg}"}), 500

@attendance_bp.route('/manual_mark_student', methods=['POST'])
def manual_mark_student():
    """Teacher marks student directly from session console."""
    data = request.get_json() or {}
    session_id = data.get('session_id')
    student_id = data.get('student_id')
    status = data.get('status', 'Present')

    sess = query_db("SELECT * FROM attendance_sessions WHERE id = %s", (session_id,), one=True)
    if not sess:
        return jsonify({'success': False, 'message': 'Session not found'}), 404

    existing = query_db("SELECT id FROM attendance_records WHERE session_id = %s AND student_id = %s",
                        (session_id, student_id), one=True)
    
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if existing:
        execute_db("UPDATE attendance_records SET status = %s, marked_by = 'MANUAL_TEACHER' WHERE id = %s",
                   (status, existing['id']))
    else:
        execute_db("""
            INSERT INTO attendance_records (session_id, student_id, course_id, attendance_date, status, marked_by, marked_at)
            VALUES (%s, %s, %s, %s, %s, 'MANUAL_TEACHER', %s)
        """, (session_id, student_id, sess['course_id'], sess['session_date'], status, now_str))

    return jsonify({'success': True, 'message': f'Student marked {status}'})
