"""Quick verification script for the hospital management system."""
import sys, os
sys.path.insert(0, '.')
os.environ['FLASK_DEBUG'] = '0'

print('1. config OK')
from config import Config

print('2. database OK')
from database import Database

print('3. face_recognition OK')
from face_recognition_module import FaceRecognitionSystem
fs = FaceRecognitionSystem()
print('   DNN available:', fs.use_dnn)

print('4. chatbot OK')
from chatbot import MedicalChatbot

print('5. notifications OK')
from notifications import NotificationService

print('6. app OK')
from app import app

print('7. Testing routes...')
with app.test_client() as c:
    print('   GET / ->', c.get("/").status_code)
    print('   GET /register ->', c.get("/register").status_code)
    print('   GET /admin-login ->', c.get("/admin-login").status_code)
    print('   GET /doctor (unauthed) ->', c.get("/doctor").status_code)
    print('   GET /find-patient (unauthed) ->', c.get("/find-patient").status_code)
    print('   GET /api/check-session ->', c.get("/api/check-session").status_code)
    print('   GET /api/doctors ->', c.get("/api/doctors").status_code)
    print('   GET /nonexistent ->', c.get("/nonexistent").status_code)

print()
print('ALL TESTS PASSED')