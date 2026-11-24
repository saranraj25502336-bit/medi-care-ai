"""Pytest configuration and fixtures for Smart Hospital tests."""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set required env vars BEFORE any imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing-only-32chars!!')
os.environ.setdefault('ADMIN_USERNAME', 'testadmin')
os.environ.setdefault('ADMIN_PASSWORD', 'testpass123')
os.environ.setdefault('RATE_LIMIT_STORAGE_URL', 'memory://')
os.environ.setdefault('FLASK_DEBUG', '1')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_USER', 'test')
os.environ.setdefault('DB_PASSWORD', 'test')
os.environ.setdefault('DB_NAME', 'test_hospital')
os.environ.setdefault('GROQ_API_KEY', '')
os.environ.setdefault('FACE_TOLERANCE', '0.5')
os.environ.setdefault('FACE_MODEL', 'buffalo_l')


@pytest.fixture(scope='session', autouse=True)
def patch_database():
    """Patch database initialization to avoid connection attempts during import."""
    with patch('database._pool', None):
        with patch('database._get_pool') as mock_get_pool:
            mock_get_pool.return_value = MagicMock()
            yield


@pytest.fixture(scope='session')
def app():
    """Create Flask app for testing."""
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    return flask_app


@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def mock_db():
    """Mock database for unit tests."""
    with patch('database.Database') as mock:
        db_instance = MagicMock()
        mock.return_value = db_instance
        yield db_instance


@pytest.fixture(scope='function')
def mock_face_service():
    """Mock face recognition service."""
    with patch('face_service.FaceService') as mock:
        yield mock


@pytest.fixture(scope='function')
def sample_patient():
    """Sample patient data for tests."""
    return {
        'patient_id': 1,
        'full_name': 'Test Patient',
        'email': 'test@example.com',
        'phone': '9876543210',
        'date_of_birth': '1990-01-01',
        'gender': 'Male',
        'address': '123 Test St',
        'blood_group': 'O+',
        'face_embedding': None
    }


@pytest.fixture(scope='function')
def sample_doctor():
    """Sample doctor data for tests."""
    return {
        'doctor_id': 1,
        'full_name': 'Dr. Test Doctor',
        'email': 'doctor@test.com',
        'phone': '9876543211',
        'specialization': 'General Medicine',
        'department_id': 1,
        'is_active': 1
    }


@pytest.fixture(scope='function')
def sample_appointment():
    """Sample appointment data for tests."""
    return {
        'appointment_id': 1,
        'patient_id': 1,
        'doctor_id': 1,
        'appointment_date': '2025-01-15',
        'appointment_time': '10:00:00',
        'status': 'scheduled',
        'appointment_type': 'regular'
    }

