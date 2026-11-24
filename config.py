# ============================================
# CONFIGURATION
# All sensitive values come from environment variables
# ============================================

import os
from dotenv import load_dotenv

# Load .env file for local development
load_dotenv()


class Config:
    """Application configuration — all secrets from environment."""

    # Flask
    _secret_key = os.environ.get('SECRET_KEY')
    if not _secret_key:
        raise RuntimeError('SECRET_KEY must be set in environment — no default allowed')
    SECRET_KEY = _secret_key
    DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', 5000))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # MySQL
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_NAME = os.environ.get('DB_NAME', 'hospital_management')
    DB_POOL_SIZE = int(os.environ.get('DB_POOL_SIZE', 5))

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    FACE_ENCODINGS_FOLDER = os.path.join(BASE_DIR, 'face_encodings')

    # Allowed uploads
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

    # AI Chatbot API keys
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')

    # Doctor / Staff access
    DOCTOR_ACCESS_CODE = os.environ.get('DOCTOR_ACCESS_CODE', 'DocSecure@2026')

    # Email (Gmail SMTP)
    EMAIL_ENABLED = os.environ.get('EMAIL_ENABLED', '0') == '1'
    EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS', '')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')

    # SMS (Fast2SMS)
    SMS_ENABLED = os.environ.get('SMS_ENABLED', '0') == '1'
    SMS_API_KEY = os.environ.get('SMS_API_KEY', '')
    SMS_SENDER_ID = os.environ.get('SMS_SENDER_ID', 'HOSPMG')

    # Face recognition (InsightFace + ArcFace)
    FACE_RECOGNITION_TOLERANCE = float(os.environ.get('FACE_TOLERANCE', '0.5'))
    FACE_RECOGNITION_MODEL = os.environ.get('FACE_MODEL', 'buffalo_s')
    FACE_DETECTION_SIZE = (640, 640)
    FACE_MIN_DETECTION_CONFIDENCE = float(os.environ.get('FACE_MIN_CONFIDENCE', '0.15'))
    CAMERA_INDEX = int(os.environ.get('CAMERA_INDEX', '0'))
    FACE_PROVIDERS = os.environ.get('FACE_PROVIDERS', 'CUDAExecutionProvider,CPUExecutionProvider').split(',')

    # InsightFace model storage
    INSIGHTFACE_HOME = os.path.join(BASE_DIR, 'face_encodings', 'insightface')
    INSIGHTFACE_MODELS_DIR = os.path.join(INSIGHTFACE_HOME, 'models')

    # Ensure upload directories exist
    @classmethod
    def ensure_dirs(cls):
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(cls.FACE_ENCODINGS_FOLDER, exist_ok=True)
        os.makedirs(cls.INSIGHTFACE_MODELS_DIR, exist_ok=True)


Config.ensure_dirs()