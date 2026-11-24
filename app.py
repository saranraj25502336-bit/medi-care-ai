# ============================================
# MAIN FLASK APPLICATION
# AI-Based Smart Patient Recognition
# and Hospital Management System
# Production Ready - AWS EC2 + Gunicorn + Nginx
import os
import json
import base64
import logging
from datetime import datetime
from functools import wraps
import bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for
)

from config import Config
from database import (
    register_patient, get_patient_by_id, get_patient_by_email,
    get_all_patients, update_face_encoding, update_patient, delete_patient,
    get_all_doctors, get_doctor_by_id, add_doctor,
    add_medical_record, get_patient_medical_records, get_all_medical_records,
    book_appointment, get_patient_appointments, get_all_appointments,
    update_appointment_status, get_appointment_by_id, get_all_face_encodings,
    add_training_data, get_all_training_data, get_training_by_id,
    update_training_data, delete_training_data,
    get_patient_password_hash, set_patient_password,
    get_doctor_password_hash, set_doctor_password
)
from face_recognition_module import FaceRecognitionSystem
from face_service import FaceService
from recognition_service import RecognitionService
from chatbot import MedicalChatbot
from notifications import NotificationService

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True

# ---------------------------------------------------------------------------
# Rate limiting — use Redis in production (memory:// only for dev)
# ---------------------------------------------------------------------------
RATE_LIMIT_STORAGE = os.environ.get('RATE_LIMIT_STORAGE_URL', 'memory://')
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=['200 per day', '50 per hour'],
    storage_uri=RATE_LIMIT_STORAGE
)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

if not Config.DEBUG:
    app.config['SESSION_COOKIE_SECURE'] = True

# ---------------------------------------------------------------------------
# Admin credentials (MUST be set via env vars — no defaults in production)
# ---------------------------------------------------------------------------
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')  # Use bcrypt hash in production

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    logger.warning('ADMIN_USERNAME or ADMIN_PASSWORD not set in environment — admin login will fail')

# ---------------------------------------------------------------------------
# Authentication decorators
# ---------------------------------------------------------------------------
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login_page'))
        return f(*args, **kwargs)
    return decorated_function


def doctor_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('doctor_id'):
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function



# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------
import re as _re

def _validate_patient_input(name, age, phone, email):
    """
    Validate patient registration / update inputs.
    Returns (is_valid: bool, error_message: str).
    """
    if not name or len(name.strip()) < 2:
        return False, 'Name must be at least 2 characters'
    try:
        age_int = int(age)
        if not (1 <= age_int <= 120):
            return False, 'Age must be between 1 and 120'
    except (ValueError, TypeError):
        return False, 'Age must be a valid number'
    if not _re.match(r'^\+?[\d\s\-]{7,15}$', str(phone)):
        return False, 'Invalid phone number format'
    if not _re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', str(email)):
        return False, 'Invalid email address'
    return True, ''

def patient_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('patient_id'):
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# Initialize modules
# ---------------------------------------------------------------------------
# Backward-compatible face system (delegates to InsightFace pipeline)
face_system = FaceRecognitionSystem()
# New InsightFace-powered services
face_service = FaceService()
recognition_service = RecognitionService()
chatbot = MedicalChatbot()
notifier = NotificationService()

# ============================================================================
# ROUTES – HOME
# ============================================================================

@app.route('/')
def index():
    """Home page."""
    doctors = get_all_doctors()
    return render_template('index.html', doctors=doctors)


# ============================================================================
# ROUTES – PATIENT REGISTRATION
# ============================================================================

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def register():
    """Patient registration page."""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            age = request.form.get('age', '').strip()
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()

            if not all([name, age, phone, email]):
                return jsonify({'success': False, 'message': 'All fields are required'})

            valid, err = _validate_patient_input(name, age, phone, email)
            if not valid:
                return jsonify({'success': False, 'message': err})

            existing = get_patient_by_email(email)
            if existing:
                return jsonify({'success': False, 'message': 'A patient with this email already exists'})

            patient_id = register_patient(name, int(age), phone, email)

            if not patient_id:
                return jsonify({'success': False, 'message': 'Registration failed. Please try again.'})

            # Hash and store password if provided
            raw_password = request.form.get('password', '').strip()
            if raw_password:
                pw_hash = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                set_patient_password(patient_id, pw_hash)

            # Handle face encoding from webcam (InsightFace ArcFace)
            face_data = request.form.get('face_data')
            face_image_data = request.form.get('face_image')

            if face_data:
                try:
                    # Use the new InsightFace-powered face service
                    # with duplicate face registration detection
                    face_result = face_service.register_patient_face(
                        patient_id=patient_id,
                        base64_string=face_data,
                        face_image=face_image_data,
                        check_duplicate=True
                    )
                    if not face_result['success']:
                        logger.warning('Face registration warning: %s',
                                       face_result['message'])
                except Exception as e:
                    logger.warning('Face encoding save error: %s', e)

            return jsonify({
                'success': True,
                'message': 'Patient registered successfully!',
                'patient_id': patient_id
            })

        except Exception as e:
            logger.exception('Registration error')
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})

    return render_template('register.html')


# ============================================================================
# ROUTES – FACE RECOGNITION LOGIN
# ============================================================================

@app.route('/face-login', methods=['POST'])
@limiter.limit("15 per minute")
def face_login():
    """Authenticate patient using face recognition (InsightFace + Cosine Similarity)."""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'success': False, 'message': 'No image data received'})

        # Use the new InsightFace-powered recognition service
        result = recognition_service.recognize_from_base64(data['image'])

        if result.success:
            # Regenerate session to avoid fixation; preserve booking redirect intent
            redirect_pending = session.get('redirect_to_appointments')
            session.clear()
            if redirect_pending:
                session['redirect_to_appointments'] = True
            session['patient_id'] = result.patient_id
            session['patient_name'] = result.patient_name
            return jsonify({
                'success': True,
                'patient_id': result.patient_id,
                'name': result.patient_name,
                'confidence': result.confidence,
                'recognition_time': result.recognition_time
            })
        else:
            return jsonify({
                'success': False,
                'message': result.message or 'Face not recognized. Please register first or try again.'
            })

    except Exception as e:
        logger.exception('Face login error')
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


# ============================================================================
# ROUTES – FACE CHECK-IN (KIOSK)
# ============================================================================

@app.route('/api/checkin/face', methods=['POST'])
@limiter.limit("30 per minute")
def checkin_face():
    """Face recognition check-in for kiosk."""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'success': False, 'message': 'No image data'})

        # Use recognition service to identify patient
        result = recognition_service.recognize_from_base64(data['image'])

        if not result.success:
            return jsonify({'success': False, 'message': result.message or 'Face not recognized'})

        # Process check-in for recognized patient
        from modules.checkin_service import process_checkin
        checkin_result = process_checkin(
            patient_id=result.patient_id,
            method='face',
            appointment_id=data.get('appointment_id'),
            recorded_by='kiosk'
        )

        return jsonify(checkin_result)

    except Exception as e:
        logger.exception('Face check-in error')
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


# ============================================================================
# ROUTES – MANUAL LOGIN
# ============================================================================

@app.route('/manual-login', methods=['POST'])
@limiter.limit("10 per minute")
def manual_login():
    """Login using Patient ID or Email (password always required)."""
    try:
        data = request.get_json() or {}
        patient_id = data.get('patient_id')
        email = data.get('email')
        raw_password = (data.get('password') or '').strip()

        patient = None
        if patient_id:
            try:
                patient = get_patient_by_id(int(patient_id))
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Invalid Patient ID'})
        elif email:
            patient = get_patient_by_email(email)

        if not patient:
            return jsonify({'success': False, 'message': 'Patient not found. Please register first.'})

        # Password is always required for manual login (no silent bypass)
        stored_hash = get_patient_password_hash(patient['patient_id'])
        if not stored_hash:
            return jsonify({
                'success': False,
                'message': 'No password set for this account. Please use Face Login or ask reception to set a password.'
            })
        if not raw_password:
            return jsonify({'success': False, 'message': 'Password required.'})
        try:
            if not bcrypt.checkpw(raw_password.encode('utf-8'), stored_hash.encode('utf-8')):
                return jsonify({'success': False, 'message': 'Incorrect password.'})
        except Exception:
            return jsonify({'success': False, 'message': 'Password verification error. Please contact support.'})

        # Regenerate session to prevent fixation; preserve booking redirect intent
        redirect_pending = session.get('redirect_to_appointments')
        session.clear()
        if redirect_pending:
            session['redirect_to_appointments'] = True
        session['patient_id'] = patient['patient_id']
        session['patient_name'] = patient['name']
        return jsonify({
            'success': True,
            'patient_id': patient['patient_id'],
            'name': patient['name']
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


# ============================================================================
# ROUTES – PATIENT DASHBOARD
# ============================================================================

@app.route('/dashboard')
@patient_login_required
def dashboard():
    """Patient dashboard."""
    patient_id = session['patient_id']
    patient = get_patient_by_id(patient_id)
    if not patient:
        session.clear()
        return redirect(url_for('index'))

    medical_records = get_patient_medical_records(patient_id)
    appointments = get_patient_appointments(patient_id)
    doctors = get_all_doctors()

    return render_template('dashboard.html',
                           patient=patient,
                           medical_records=medical_records,
                           appointments=appointments,
                           doctors=doctors)


# ============================================================================
# ROUTES – DOCTOR LOGIN
# ============================================================================

@app.route('/doctor-login', methods=['POST'])
@limiter.limit("10 per minute")
def doctor_login():
    """Authenticate doctor using their individual bcrypt password."""
    try:
        data = request.get_json() or {}
        doctor_id = data.get('doctor_id')
        password = (data.get('password') or '').strip()

        if not doctor_id or not password:
            return jsonify({'success': False, 'message': 'Doctor ID and password are required.'})

        try:
            doctor = get_doctor_by_id(int(doctor_id))
        except (ValueError, TypeError):
            doctor = None

        if not doctor:
            return jsonify({'success': False, 'message': 'Doctor not found.'})
        if doctor.get('is_active', 1) == 0:
            return jsonify({'success': False, 'message': 'This doctor account is deactivated.'})

        # Per-doctor bcrypt password (migration seeds a default hash per doctor)
        stored_hash = get_doctor_password_hash(int(doctor_id))
        if not stored_hash:
            return jsonify({
                'success': False,
                'message': 'No password configured for this doctor account. Please ask the administrator to set one.'
            })
        try:
            if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                return jsonify({'success': False, 'message': 'Invalid password.'})
        except Exception:
            return jsonify({'success': False, 'message': 'Password verification error. Please contact support.'})

        session.clear()
        session['doctor_id'] = doctor['doctor_id']
        session['doctor_name'] = doctor['name']
        return jsonify({
            'success': True,
            'doctor_id': doctor['doctor_id'],
            'name': doctor['name']
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


# ============================================================================
# ROUTES – DOCTOR DASHBOARD
# ============================================================================

@app.route('/doctor')
@doctor_login_required
def doctor_dashboard():
    """Doctor dashboard."""
    doctors = get_all_doctors()
    patients = get_all_patients()
    records = get_all_medical_records()
    appointments = get_all_appointments()

    return render_template('doctor_dashboard.html',
                           doctors=doctors,
                           patients=patients,
                           records=records,
                           appointments=appointments)


@app.route('/doctor/patient/<int:patient_id>')
@doctor_login_required
def doctor_patient_view(patient_id):
    """Doctor view specific patient."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        return redirect(url_for('doctor_dashboard'))
    records = get_patient_medical_records(patient_id)
    return render_template('doctor_patient.html',
                           patient=patient,
                           records=records)


# ============================================================================
# ROUTES – PRESCRIPTIONS
# ============================================================================

@app.route('/add-prescription', methods=['POST'])
@doctor_login_required
def add_prescription():
    """Add a prescription."""
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        symptoms = data.get('symptoms', '')
        diagnosis = data.get('diagnosis', '')
        prescription = data.get('prescription', '')
        doctor_name = data.get('doctor_name', 'Dr. Unknown')
        doctor_notes = data.get('doctor_notes', '')

        if not patient_id:
            return jsonify({'success': False, 'message': 'Patient ID is required'})

        record_id = add_medical_record(patient_id, symptoms, diagnosis, prescription, doctor_name, doctor_notes)
        if not record_id:
            return jsonify({'success': False, 'message': 'Failed to add prescription'})

        try:
            notifier.send_prescription_notification(patient_id, {
                'doctor_name': doctor_name,
                'diagnosis': diagnosis,
                'prescription': prescription
            })
        except Exception as e:
            logger.warning('Notification error: %s', e)

        return jsonify({'success': True, 'message': 'Prescription added successfully!', 'record_id': record_id})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


# ============================================================================
# ROUTES – APPOINTMENTS
# ============================================================================

@app.route('/appointments')
@patient_login_required
def appointments_page():
    """Appointments page."""
    patient_id = session['patient_id']
    patient = get_patient_by_id(patient_id)
    doctors = get_all_doctors()
    appointments = get_patient_appointments(patient_id)

    today = datetime.now().strftime('%Y-%m-%d')
    upcoming = [a for a in appointments if a.get('appointment_date', '') >= today]
    past = [a for a in appointments if a.get('appointment_date', '') < today]

    doctors_json = {}
    for d in doctors:
        doctors_json[str(d['doctor_id'])] = {'name': d['name'], 'specialization': d['specialization']}

    return render_template('appointments.html',
                           patient=patient,
                           doctors=doctors,
                           appointments=appointments,
                           upcoming_appointments=upcoming,
                           past_appointments=past,
                           current_date=today,
                           min_date=today,
                           doctors_json=json.dumps(doctors_json))


@app.route('/book-appointment', methods=['POST'])
def book_appointment_route():
    """Book a new appointment."""
    try:
        data = request.get_json()
        patient_id = session.get('patient_id')
        if not patient_id:
            return jsonify({'success': False, 'message': 'Please login first'})

        doctor_id = data.get('doctor_id')
        appointment_date = data.get('appointment_date')
        appointment_time = data.get('appointment_time')
        symptoms = data.get('symptoms', '')

        if not all([doctor_id, appointment_date, appointment_time]):
            return jsonify({'success': False, 'message': 'All fields are required'})

        appointment_id = book_appointment(patient_id, doctor_id, appointment_date, appointment_time, symptoms)
        if not appointment_id:
            return jsonify({'success': False, 'message': 'Failed to book appointment'})

        try:
            doctor = get_doctor_by_id(doctor_id)
            notifier.send_appointment_confirmation(patient_id, {
                'doctor_name': doctor['name'] if doctor else 'Doctor',
                'appointment_date': appointment_date,
                'appointment_time': appointment_time
            })
        except Exception as e:
            logger.warning('Notification error: %s', e)

        return jsonify({'success': True, 'message': 'Appointment booked successfully!', 'appointment_id': appointment_id})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/update-appointment-status', methods=['POST'])
@doctor_login_required
def update_appointment_status_route():
    """Update appointment status."""
    try:
        data = request.get_json()
        appointment_id = data.get('appointment_id')
        status = data.get('status')

        if not all([appointment_id, status]):
            return jsonify({'success': False, 'message': 'Missing required fields'})
        if status not in ('approved', 'rejected'):
            return jsonify({'success': False, 'message': 'Invalid status'})

        update_appointment_status(appointment_id, status)

        try:
            appointment = get_appointment_by_id(appointment_id)
            if appointment:
                notifier.send_appointment_status_update(appointment)
        except Exception as e:
            logger.warning('Notification error: %s', e)

        return jsonify({'success': True, 'message': f'Appointment {status} successfully!'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


# ============================================================================
# ROUTES – AI SELF-CARE SUGGESTIONS
# ============================================================================

@app.route('/get-selfcare-suggestions', methods=['POST'])
def get_selfcare_suggestions():
    """Generate self-care suggestions."""
    try:
        data = request.get_json()
        symptoms = (data.get('symptoms') or '').strip()

        if not symptoms:
            return jsonify({'success': True, 'suggestions': [
                "Stay hydrated and get plenty of rest.",
                "Monitor your temperature regularly.",
                "Avoid strenuous activities until your appointment.",
                "Note down any new symptoms that may appear.",
                "Keep your appointment confirmation handy."
            ]})

        suggestions = chatbot.get_selfcare_suggestions(symptoms)
        return jsonify({'success': True, 'suggestions': suggestions})

    except Exception as e:
        logger.warning('Self-care suggestions error: %s', e)
        return jsonify({'success': True, 'suggestions': [
            "Stay hydrated and get plenty of rest.",
            "Monitor your symptoms and note any changes.",
            "Avoid self-medication until consulting the doctor.",
            "Keep your appointment time and bring relevant medical records.",
            "In case of emergency, visit the nearest emergency room."
        ]})


# ============================================================================
# ROUTES – CHATBOT
# ============================================================================

@app.route('/chatbot', methods=['POST'])
@limiter.limit("30 per minute")
def chatbot_route():
    """Chatbot API endpoint."""
    try:
        data = request.get_json() or {}
        user_message = (data.get('message') or '').strip()
        language = data.get('language')
        if not user_message:
            return jsonify({'success': False, 'message': 'No message provided'})

        response = chatbot.get_response(user_message, language)
        return jsonify({'success': True, 'response': response})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/chatbot/voice', methods=['POST'])
@limiter.limit("20 per minute")
def chatbot_voice_route():
    """Chatbot voice endpoint: server-side speech-to-text + AI response."""
    try:
        data = request.get_json() or {}
        audio_b64 = data.get('audio') or data.get('audio_base64')
        mime_type = data.get('mime_type') or 'audio/webm'
        language = data.get('language')

        if not audio_b64:
            return jsonify({'success': False, 'message': 'No audio received'})

        audio_bytes = base64.b64decode(audio_b64)
        transcript = chatbot.transcribe_audio(audio_bytes, mime_type)
        if not transcript:
            return jsonify({'success': False, 'message': "Sorry, I couldn't understand the audio. Please try again."})

        response = chatbot.get_response(transcript, language)
        return jsonify({'success': True, 'response': response, 'transcript': transcript})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


# ============================================================================
# ROUTES – LOGOUT
# ============================================================================

@app.route('/logout')
def logout():
    """Logout patient."""
    session.clear()
    return redirect(url_for('index'))


@app.route('/doctor-logout')
def doctor_logout():
    """Logout doctor."""
    session.clear()
    return redirect(url_for('index'))


# ============================================================================
# ROUTES – PATIENT DIRECT
# ============================================================================

@app.route('/patient/<int:patient_id>')
def patient_direct(patient_id):
    """Direct patient redirect — only for an authenticated patient viewing themselves."""
    if session.get('patient_id') != patient_id:
        return redirect(url_for('index'))
    patient = get_patient_by_id(patient_id)
    if patient:
        session['patient_name'] = patient['name']
    return redirect(url_for('dashboard'))


# ============================================================================
# ROUTES – API
# ============================================================================

@app.route('/api/patients')
@doctor_login_required
def api_patients():
    """Get all patients (doctor only)."""
    return jsonify(get_all_patients())


@app.route('/api/doctors')
def api_doctors():
    """Get all doctors."""
    return jsonify(get_all_doctors())


@app.route('/api/records/<int:patient_id>')
@doctor_login_required
def api_records(patient_id):
    """Get patient records (doctor only)."""
    return jsonify(get_patient_medical_records(patient_id))


@app.route('/api/patient/<int:patient_id>')
def api_patient_details(patient_id):
    """Get patient details and records (own-patient or staff only)."""
    # Check authorization: patient can only access their own data, staff can access any
    patient_id_session = session.get('patient_id')
    doctor_id_session = session.get('doctor_id')
    admin_logged_in = session.get('admin_logged_in')

    # Allow if: patient accessing own data, or staff (doctor/admin) logged in
    if not (patient_id_session == patient_id or doctor_id_session or admin_logged_in):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    patient = get_patient_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'message': 'Patient not found'})
    records = get_patient_medical_records(patient_id)
    appointments = get_patient_appointments(patient_id)
    return jsonify({
        'success': True,
        'patient': {
            'patient_id': patient['patient_id'],
            'name': patient['name'],
            'age': patient['age'],
            'phone': patient['phone'],
            'email': patient['email'],
            'registration_date': str(patient.get('registration_date', ''))
        },
        'medical_records': records,
        'appointments': appointments
    })


@app.route('/api/check-session')
def api_check_session():
    """Check current session."""
    return jsonify({
        'logged_in': session.get('patient_id') is not None,
        'patient_id': session.get('patient_id'),
        'patient_name': session.get('patient_name'),
        'doctor_logged_in': session.get('doctor_id') is not None,
        'doctor_id': session.get('doctor_id'),
        'doctor_name': session.get('doctor_name')
    })


@app.route('/api/set-appointment-redirect', methods=['POST'])
def api_set_appointment_redirect():
    """Set redirect flag."""
    session['redirect_to_appointments'] = True
    return jsonify({'success': True})


# ============================================================================
# ROUTES – ADMIN LOGIN
# ============================================================================

@app.route('/admin-login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def admin_login_page():
    """Admin login."""
    if request.method == 'POST':
        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

        if not ADMIN_USERNAME or not ADMIN_PASSWORD:
            return jsonify({'success': False, 'message': 'Admin credentials not configured'})

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return jsonify({'success': True, 'message': 'Login successful!'})
        return jsonify({'success': False, 'message': 'Invalid username or password'})

    return render_template('admin_login.html')


@app.route('/admin-logout')
def admin_logout():
    """Admin logout."""
    session.clear()
    return redirect(url_for('admin_login_page'))


# ============================================================================
# ROUTES – CHATBOT TRAINING (Admin-protected)
# ============================================================================

@app.route('/admin/add-doctor', methods=['POST'])
@admin_login_required
def admin_add_doctor():
    """Add a doctor."""
    try:
        data = request.get_json()
        name = (data.get('name') or '').strip()
        specialization = (data.get('specialization') or '').strip()
        if not name or not specialization:
            return jsonify({'success': False, 'message': 'Doctor name and specialization are required'})

        doctor_id = add_doctor(name, specialization,
                               (data.get('email') or '').strip() or None,
                               (data.get('phone') or '').strip() or None)
        if doctor_id:
            return jsonify({'success': True, 'message': 'Doctor added!', 'doctor_id': doctor_id})
        return jsonify({'success': False, 'message': 'Failed to add doctor'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/admin/train')
@admin_login_required
def admin_train():
    """Admin training panel."""
    try:
        training_data = get_all_training_data()
        doctors = get_all_doctors()
        return render_template('admin_train.html', training_data=training_data, doctors=doctors)
    except Exception as e:
        logger.error('Loading training data: %s', e)
        return render_template('admin_train.html', training_data=[])


@app.route('/admin/train/save', methods=['POST'])
@admin_login_required
def save_training():
    """Save training data."""
    try:
        data = request.get_json()
        training_id = data.get('id')
        keywords = (data.get('keywords') or '').strip()
        answer = (data.get('answer') or '').strip()
        question = (data.get('question') or '').strip()
        category = data.get('category', 'general')
        urgency = data.get('urgency', 'low')

        if not keywords or not answer:
            return jsonify({'success': False, 'message': 'Keywords and answer are required'})

        if training_id:
            update_training_data(training_id, keywords, answer, question, category, urgency)
            return jsonify({'success': True, 'message': 'Training data updated!'})
        else:
            tid = add_training_data(keywords, answer, question, category, urgency)
            return jsonify({'success': True, 'message': 'Training data added!'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/admin/train/get/<int:training_id>')
@admin_login_required
def get_training(training_id):
    """Get single training record."""
    try:
        data = get_training_by_id(training_id)
        if data:
            return jsonify({'success': True, 'data': data})
        return jsonify({'success': False, 'message': 'Not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/admin/train/delete/<int:training_id>', methods=['DELETE'])
@admin_login_required
def delete_training(training_id):
    """Delete training record."""
    try:
        if delete_training_data(training_id):
            return jsonify({'success': True, 'message': 'Deleted'})
        return jsonify({'success': False, 'message': 'Failed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/admin/train/export')
@admin_login_required
def export_training():
    """Export training data."""
    try:
        return jsonify(get_all_training_data())
    except Exception:
        return jsonify([])


@app.route('/admin/train/import', methods=['POST'])
@admin_login_required
def import_training():
    """Import training data."""
    try:
        data = request.get_json()
        count = 0
        for item in data.get('data', []):
            add_training_data(
                keywords=item.get('keywords', ''),
                answer=item.get('answer', ''),
                question=item.get('question', ''),
                category=item.get('category', 'general'),
                urgency=item.get('urgency', 'low')
            )
            count += 1
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ============================================================================
# ROUTES – PATIENT MANAGEMENT (Admin)
# ============================================================================

@app.route('/admin/add-patient', methods=['POST'])
@admin_login_required
def admin_add_patient():
    """Admin add patient."""
    try:
        data = request.get_json()
        name = (data.get('name') or '').strip()
        age = data.get('age')
        phone = (data.get('phone') or '').strip()
        email = (data.get('email') or '').strip()
        if not all([name, age, phone, email]):
            return jsonify({'success': False, 'message': 'All fields are required'})

        if get_patient_by_email(email):
            return jsonify({'success': False, 'message': 'Email already exists'})

        patient_id = register_patient(name, int(age), phone, email)
        if patient_id:
            return jsonify({'success': True, 'message': 'Patient added!', 'patient_id': patient_id})
        return jsonify({'success': False, 'message': 'Failed'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/admin/delete-patient', methods=['POST'])
@admin_login_required
def admin_delete_patient():
    """Admin delete patient."""
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        if not patient_id:
            return jsonify({'success': False, 'message': 'Patient ID is required'})
        if delete_patient(patient_id):
            return jsonify({'success': True, 'message': 'Deleted!'})
        return jsonify({'success': False, 'message': 'Failed'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/doctor/update-patient', methods=['POST'])
@doctor_login_required
def doctor_update_patient():
    """Doctor update patient."""
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        name = (data.get('name') or '').strip()
        age = data.get('age')
        phone = (data.get('phone') or '').strip()
        email = (data.get('email') or '').strip()
        if not all([patient_id, name, age, phone, email]):
            return jsonify({'success': False, 'message': 'All fields are required'})

        if update_patient(patient_id, name, int(age), phone, email):
            return jsonify({'success': True, 'message': 'Updated!'})
        return jsonify({'success': False, 'message': 'Failed'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


# ============================================================================
# ROUTES – FIND PATIENT (Staff/Doctor only)
# ============================================================================

@app.route('/find-patient')
def find_patient_page():
    """Find patient by face scan."""
    return render_template('find_patient.html')


@app.route('/find-patient/scan', methods=['POST'])
@limiter.limit("15 per minute")
def find_patient_scan():
    """Scan face for patient lookup (InsightFace + Cosine Similarity)."""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'success': False, 'message': 'No image data'})

        # Use the new InsightFace-powered recognition service
        result = recognition_service.recognize_from_base64(data['image'])

        if result.success:
            patient = get_patient_by_id(result.patient_id)
            if not patient:
                return jsonify({'success': False, 'message': 'Patient not found'})

            medical_records = get_patient_medical_records(result.patient_id)
            appointments = get_patient_appointments(result.patient_id)

            # Convert datetimes to strings safely
            for rec in (medical_records or []):
                for key in ('visit_date', 'registration_date', 'created_at'):
                    val = rec.get(key)
                    if val and not isinstance(val, str) and hasattr(val, 'strftime'):
                        rec[key] = val.strftime('%Y-%m-%d %H:%M:%S')

            return jsonify({
                'success': True,
                'patient': {
                    'patient_id': patient['patient_id'],
                    'name': patient['name'],
                    'age': patient['age'],
                    'phone': patient['phone'],
                    'email': patient['email'],
                    'registration_date': str(patient.get('registration_date', ''))
                },
                'medical_records': medical_records,
                'appointments': appointments,
                'confidence': result.confidence,
                'recognition_time': result.recognition_time
            })
        else:
            return jsonify({'success': False, 'message': result.message or 'Face not recognized.'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/healthz')
def healthz():
    """Health check endpoint for load balancers / orchestration."""
    try:
        from database import Database
        db = Database()
        db.execute_query('SELECT 1')
        db.close()
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        logger.error('Health check failed: %s', e)
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    try:
        patients_data = get_all_face_encodings()
        face_system.load_known_faces(patients_data)
        logger.info('Loaded %d face encodings at startup', len(patients_data))
    except Exception as e:
        logger.warning('Could not load face encodings at startup: %s', e)

    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )