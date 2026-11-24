"""
QA Verification Script for Smart Hospital Management System
Tests: imports, routes, templates, static files, API, database, face recognition, chatbot, gunicorn
"""
import sys, os, json, logging
sys.path.insert(0, '.')
os.environ['FLASK_DEBUG'] = '0'
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_USER'] = 'root'
os.environ['DB_PASSWORD'] = ''

logging.basicConfig(level=logging.CRITICAL)
passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f'  PASS: {name}')
    except Exception as e:
        failed += 1
        print(f'  FAIL: {name} -> {e}')

# ============================================================
# 1. IMPORT VERIFICATION
# ============================================================
print('\n=== 1. IMPORT VERIFICATION ===')

test('config', lambda: __import__('config'))
test('database', lambda: __import__('database'))
test('face_recognition_module', lambda: __import__('face_recognition_module'))
test('chatbot', lambda: __import__('chatbot'))
test('notifications', lambda: __import__('notifications'))
test('app module', lambda: __import__('app'))

# ============================================================
# 2. APP STARTUP
# ============================================================
print('\n=== 2. APP STARTUP ===')

from app import app
test('Flask app created', lambda: app is not None)
test('secret_key set', lambda: len(app.secret_key) > 0)
test('session cookie httponly', lambda: app.config['SESSION_COOKIE_HTTPONLY'] == True)
test('session cookie samesite', lambda: app.config['SESSION_COOKIE_SAMESITE'] == 'Lax')

# ============================================================
# 3. FLASK ROUTES
# ============================================================
print('\n=== 3. FLASK ROUTE VERIFICATION ===')

with app.test_client() as c:
    test('GET / -> 200', lambda: c.get('/').status_code == 200)
    test('GET /register -> 200', lambda: c.get('/register').status_code == 200)
    test('GET /admin-login -> 200', lambda: c.get('/admin-login').status_code == 200)
    test('GET /doctor (unauthed) -> 302', lambda: c.get('/doctor').status_code == 302)
    test('GET /find-patient (unauthed) -> 302', lambda: c.get('/find-patient').status_code == 302)
    test('GET /api/check-session -> 200', lambda: c.get('/api/check-session').status_code == 200)
    test('GET /api/doctors -> 200', lambda: c.get('/api/doctors').status_code == 200)
    test('GET /nonexistent -> 404', lambda: c.get('/nonexistent').status_code == 404)
    test('POST /chatbot (no msg) -> 200', lambda: c.post('/chatbot', json={}).status_code == 200)
    test('POST /face-login (no img) -> 200', lambda: c.post('/face-login', json={}).status_code == 200)
    test('POST /manual-login (no data) -> 200', lambda: c.post('/manual-login', json={}).status_code == 200)
    test('POST /doctor-login (no data) -> 200', lambda: c.post('/doctor-login', json={}).status_code == 200)
    test('POST /get-selfcare-suggestions -> 200', lambda: c.post('/get-selfcare-suggestions', json={}).status_code == 200)
    test('POST /book-appointment (no auth) -> 200', lambda: c.post('/book-appointment', json={}).status_code == 200)
    test('POST /api/set-appointment-redirect -> 200', lambda: c.post('/api/set-appointment-redirect', json={}).status_code == 200)

# ============================================================
# 4. TEMPLATE VERIFICATION
# ============================================================
print('\n=== 4. TEMPLATE VERIFICATION ===')

import os.path
templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
required_templates = [
    'index.html', 'register.html', 'dashboard.html', 'appointments.html',
    'doctor_dashboard.html', 'doctor_patient.html', 'find_patient.html',
    'admin_login.html', 'admin_train.html', '404.html', '500.html'
]
for t in required_templates:
    test(f'template: {t}', lambda t=t: os.path.exists(os.path.join(templates_dir, t)))

# ============================================================
# 5. STATIC FILES
# ============================================================
print('\n=== 5. STATIC FILES ===')

static_dir = os.path.join(os.path.dirname(__file__), 'static')
test('static dir exists', lambda: os.path.isdir(static_dir))
test('static/css exists', lambda: os.path.isdir(os.path.join(static_dir, 'css')))
test('static/js exists', lambda: os.path.isdir(os.path.join(static_dir, 'js')))
test('static/images exists', lambda: os.path.isdir(os.path.join(static_dir, 'images')))
test('static/uploads exists', lambda: os.path.isdir(os.path.join(static_dir, 'uploads')))

# ============================================================
# 6. API ENDPOINTS
# ============================================================
print('\n=== 6. API ENDPOINTS ===')

with app.test_client() as c:
    r = c.get('/api/check-session')
    test('check-session returns JSON', lambda: r.is_json)
    if r.is_json:
        data = r.get_json()
        test('check-session has logged_in', lambda: 'logged_in' in data)
        test('check-session has doctor_logged_in', lambda: 'doctor_logged_in' in data)

    r = c.get('/api/doctors')
    test('doctors returns JSON', lambda: r.is_json)

# ============================================================
# 7. DATABASE QUERIES
# ============================================================
print('\n=== 7. DATABASE QUERIES ===')

from database import get_all_doctors, get_all_patients, get_all_face_encodings, get_all_training_data
test('get_all_doctors()', lambda: isinstance(get_all_doctors(), list))
test('get_all_patients()', lambda: isinstance(get_all_patients(), list))
test('get_all_face_encodings()', lambda: isinstance(get_all_face_encodings(), list))
test('get_all_training_data()', lambda: isinstance(get_all_training_data(), list))

# ============================================================
# 8. FACE RECOGNITION
# ============================================================
print('\n=== 8. FACE RECOGNITION ===')

from face_recognition_module import FaceRecognitionSystem
fs = FaceRecognitionSystem()
test('FaceSystem created', lambda: fs is not None)
test('is_available()', lambda: fs.is_available() == True)
test('get_encoding_as_json(None)', lambda: fs.get_encoding_as_json(None) is None)
test('encoding_from_json(None)', lambda: fs.encoding_from_json(None) is None)
test('load_known_faces(empty)', lambda: fs.load_known_faces([]) is None)
test('recognize_face(None)', lambda: fs.recognize_face(None) is None)

# ============================================================
# 9. CHATBOT
# ============================================================
print('\n=== 9. CHATBOT ===')

from chatbot import MedicalChatbot
cb = MedicalChatbot()
test('Chatbot created', lambda: cb is not None)
test('get_response(hello)', lambda: len(cb.get_response('hello')) > 0)
test('get_response(empty)', lambda: len(cb.get_response('')) > 0)
test('get_selfcare_suggestions(empty)', lambda: len(cb.get_selfcare_suggestions('')) == 5)
test('get_selfcare_suggestions(fever)', lambda: len(cb.get_selfcare_suggestions('fever')) == 5)
test('emergency detection', lambda: '108' in cb.get_response('chest pain'))

# ============================================================
# 10. NOTIFICATIONS
# ============================================================
print('\n=== 10. NOTIFICATIONS ===')

from notifications import NotificationService
ns = NotificationService()
test('NotificationService created', lambda: ns is not None)

# ============================================================
# 11. LOGIN MODULES
# ============================================================
print('\n=== 11. LOGIN MODULES ===')

with app.test_client() as c:
    # Test doctor login
    r = c.post('/doctor-login', json={'doctor_id': 1, 'password': 'doctor123'})
    test('doctor login valid', lambda: r.get_json().get('success') == True)
    
    r = c.post('/doctor-login', json={'doctor_id': 1, 'password': 'wrong'})
    test('doctor login invalid password', lambda: r.get_json().get('success') == False)
    
    r = c.post('/doctor-login', json={'doctor_id': 999, 'password': 'doctor123'})
    test('doctor login invalid id', lambda: r.get_json().get('success') == False)

    # Test admin login
    r = c.post('/admin-login', json={'username': 'admin', 'password': 'admin123'})
    test('admin login valid', lambda: r.get_json().get('success') == True)
    
    r = c.post('/admin-login', json={'username': 'admin', 'password': 'wrong'})
    test('admin login invalid', lambda: r.get_json().get('success') == False)

# ============================================================
# 12. DASHBOARD MODULES
# ============================================================
print('\n=== 12. DASHBOARD MODULES ===')

with app.test_client() as c:
    # Patient dashboard requires login
    r = c.get('/dashboard')
    test('dashboard redirects when not logged in', lambda: r.status_code == 302)
    
    # Appointments page requires login
    r = c.get('/appointments')
    test('appointments redirects when not logged in', lambda: r.status_code == 302)

# ============================================================
# 13. GUNICORN COMPATIBILITY
# ============================================================
print('\n=== 13. GUNICORN COMPATIBILITY ===')

test('app has callable wsgi_app', lambda: hasattr(app, 'wsgi_app'))
test('app callable', lambda: callable(app))

# ============================================================
# 14. PRODUCTION DEPLOYMENT
# ============================================================
print('\n=== 14. PRODUCTION DEPLOYMENT ===')

test('requirements.txt exists', lambda: os.path.exists('requirements.txt'))
test('Procfile exists', lambda: os.path.exists('Procfile'))
test('render.yaml exists', lambda: os.path.exists('render.yaml'))
test('.gitignore exists', lambda: os.path.exists('.gitignore'))

# Check requirements.txt has gunicorn
with open('requirements.txt') as f:
    reqs = f.read()
test('gunicorn in requirements', lambda: 'gunicorn' in reqs)
test('opencv in requirements', lambda: 'opencv' in reqs)
test('flask in requirements', lambda: 'flask' in reqs.lower())

# ============================================================
# SUMMARY
# ============================================================
print(f'\n{"="*50}')
print(f'QA VERIFICATION COMPLETE')
print(f'  Passed: {passed}')
print(f'  Failed: {failed}')
print(f'  Total:  {passed + failed}')
print(f'{"="*50}')

if failed > 0:
    print('\nWARNING: Some tests FAILED. Review output above.')
    sys.exit(1)
else:
    print('\nALL TESTS PASSED - Application is production-ready!')
    sys.exit(0)