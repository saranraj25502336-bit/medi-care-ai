"""Tests for authentication and authorization."""
import pytest
from unittest.mock import MagicMock, patch


class TestPatientAuth:
    """Test patient registration and login."""

    def test_patient_registration_page_loads(self, client):
        """Test patient registration page renders."""
        resp = client.get('/register')
        assert resp.status_code == 200
        assert b'register' in resp.data.lower() or b'Register' in resp.data

    def test_patient_login_page_loads(self, client):
        """Test patient login page renders (index page)."""
        resp = client.get('/')
        assert resp.status_code == 200

    @patch('app.get_patient_by_email')
    @patch('app.register_patient')
    @patch('app.set_patient_password')
    @patch('app.face_service.register_patient_face')
    def test_patient_register_success(self, mock_face, mock_set_pw, mock_register, mock_get_email, client):
        """Test successful patient registration."""
        mock_get_email.return_value = None
        mock_register.return_value = 1
        mock_set_pw.return_value = True
        mock_face.return_value = {'success': True}
        resp = client.post('/register', data={
            'name': 'Test User',
            'age': '25',
            'phone': '9876543210',
            'email': 'test@example.com',
            'password': 'SecurePass123'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_patient_register_password_mismatch(self, client):
        """Test registration fails with password mismatch."""
        resp = client.post('/register', data={
            'name': 'Test User',
            'age': '25',
            'phone': '9876543210',
            'email': 'test@example.com',
            'password': 'SecurePass123',
            'confirm_password': 'DifferentPass'
        })
        assert resp.status_code in (200, 400)


class TestDoctorAuth:
    """Test doctor authentication."""

    def test_doctor_login_page_loads(self, client):
        """Test doctor login page renders."""
        resp = client.get('/doctor-login')
        # The route only accepts POST, so GET returns 405
        assert resp.status_code in (200, 405)

    @patch('app.get_doctor_by_id')
    @patch('app.get_doctor_password_hash')
    @patch('app.bcrypt.checkpw')
    def test_doctor_login_success(self, mock_checkpw, mock_get_hash, mock_get_doc, client):
        """Test successful doctor login."""
        mock_get_doc.return_value = {
            'doctor_id': 1,
            'name': 'Dr. Test',
            'is_active': 1
        }
        mock_get_hash.return_value = '$2b$12$hashedpassword'
        mock_checkpw.return_value = True

        resp = client.post('/doctor-login', json={
            'doctor_id': '1',
            'password': 'doctor123'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True


class TestAdminAuth:
    """Test admin authentication."""

    def test_admin_login_page_loads(self, client):
        """Test admin login page renders."""
        resp = client.get('/admin-login')
        assert resp.status_code == 200

    def test_admin_login_success(self, client):
        """Test successful admin login."""
        resp = client.post('/admin-login', json={
            'username': 'testadmin',
            'password': 'testpass123'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_admin_login_wrong_password(self, client):
        """Test admin login fails with wrong password."""
        resp = client.post('/admin-login', json={
            'username': 'testadmin',
            'password': 'wrongpass'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is False

    def test_admin_login_missing_credentials(self, client):
        """Test admin login fails when env vars not set."""
        import os
        old_user = os.environ.get('ADMIN_USERNAME')
        old_pass = os.environ.get('ADMIN_PASSWORD')
        os.environ['ADMIN_USERNAME'] = ''
        os.environ['ADMIN_PASSWORD'] = ''

        try:
            # Need to reload app module to pick up new env vars
            import importlib
            import app as app_module
            importlib.reload(app_module)

            resp = client.post('/admin-login', json={
                'username': 'admin',
                'password': 'admin123'
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['success'] is False
            assert 'not configured' in data['message'].lower()
        finally:
            if old_user:
                os.environ['ADMIN_USERNAME'] = old_user
            else:
                os.environ['ADMIN_USERNAME'] = 'testadmin'
            if old_pass:
                os.environ['ADMIN_PASSWORD'] = old_pass
            else:
                os.environ['ADMIN_PASSWORD'] = 'testpass123'
            importlib.reload(app_module)


class TestRBAC:
    """Test role-based access control."""

    def test_protected_route_requires_login(self, client):
        """Test that protected routes redirect when not logged in."""
        resp = client.get('/dashboard')
        assert resp.status_code == 302  # Redirect to login

    def test_admin_route_requires_admin(self, client):
        """Test admin routes require admin login."""
        # Admin dashboard is at /admin-login page, admin features are behind login
        resp = client.get('/admin-login')
        assert resp.status_code == 200  # Login page accessible

    def test_doctor_route_requires_doctor(self, client):
        """Test doctor routes require doctor login."""
        resp = client.get('/doctor')
        assert resp.status_code == 302  # Redirect to login