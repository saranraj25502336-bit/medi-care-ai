"""Tests for check-in service."""
import pytest
from unittest.mock import MagicMock, patch
from modules.checkin_service import process_checkin, doctor_can_treat_patient


class TestCheckinService:
    """Test check-in orchestration."""

    @patch('modules.checkin_service.get_patient_by_id')
    def test_checkin_patient_not_found(self, mock_get_patient):
        """Test check-in fails for non-existent patient."""
        mock_get_patient.return_value = None
        result = process_checkin(patient_id=999)
        assert result['success'] is False
        assert 'not found' in result['message'].lower()

    @patch('modules.checkin_service.get_patient_by_id')
    @patch('modules.checkin_service.get_active_checkin')
    def test_checkin_duplicate_prevention(self, mock_active, mock_get_patient):
        """Test duplicate check-in prevention."""
        mock_get_patient.return_value = {'patient_id': 1, 'full_name': 'Test'}
        mock_active.return_value = {'checkin_id': 1, 'appointment_id': None}

        with patch('modules.checkin_service.get_active_token_for_patient') as mock_token:
            mock_token.return_value = {'queue_category': 'regular'}
            with patch('modules.routing_engine.evaluate') as mock_eval:
                mock_eval.return_value = {'blocked': False}
                with patch('modules.routing_engine.record') as mock_record:
                    result = process_checkin(patient_id=1)
                    assert result['success'] is True
                    assert result['duplicate'] is True

    @patch('modules.checkin_service.get_patient_by_id')
    @patch('modules.checkin_service.get_active_checkin')
    @patch('modules.checkin_service.get_appointment_by_id')
    @patch('modules.checkin_service.get_doctor_by_id')
    @patch('modules.checkin_service.get_doctor_department_for_doctor')
    @patch('modules.checkin_service.get_default_department_id')
    @patch('modules.checkin_service.is_department_available')
    @patch('modules.checkin_service.routing_engine.evaluate')
    @patch('modules.checkin_service.routing_engine.record')
    @patch('modules.checkin_service.create_checkin')
    @patch('modules.checkin_service.get_department_by_id')
    @patch('modules.checkin_service.queue_management.estimate_wait_min')
    @patch('modules.checkin_service.queue_management.generate_token')
    @patch('modules.checkin_service.update_checkin_token')
    def test_checkin_new_appointment_flow(self, mock_update_token, mock_gen_token,
                                          mock_est_wait, mock_get_dept, mock_create_checkin,
                                          mock_record, mock_eval, mock_dept_avail,
                                          mock_default_dept, mock_doc_dept, mock_get_doc,
                                          mock_get_appt, mock_active, mock_get_patient):
        """Test full check-in flow for appointment patient."""
        mock_get_patient.return_value = {'patient_id': 1, 'full_name': 'Test Patient'}
        mock_active.return_value = None
        mock_get_appt.return_value = {
            'appointment_id': 1,
            'doctor_id': 1,
            'status': 'scheduled',
            'appointment_type': 'regular'
        }
        mock_get_doc.return_value = {'doctor_id': 1, 'is_active': 1}
        mock_doc_dept.return_value = {'department_id': 1}
        mock_default_dept.return_value = 1
        mock_dept_avail.return_value = {'available': True}
        mock_eval.return_value = {
            'blocked': False,
            'assigned_department_id': 1,
            'queue_category': 'regular',
            'decision_reason': 'Appointment with available doctor'
        }
        mock_create_checkin.return_value = 1
        mock_get_dept.return_value = {'name': 'General Medicine'}
        mock_est_wait.return_value = 15
        mock_gen_token.return_value = {'token_code': 'GM-R-001', 'queue_number': 1}

        result = process_checkin(patient_id=1, method='manual', appointment_id=1)

        assert result['success'] is True
        assert result['duplicate'] is False
        assert result['checkin_id'] == 1
        assert result['token']['token_code'] == 'GM-R-001'
        assert result['est_wait_min'] == 15

    @patch('modules.checkin_service.get_patient_by_id')
    @patch('modules.checkin_service.get_active_checkin')
    @patch('modules.checkin_service.routing_engine.evaluate')
    @patch('modules.checkin_service.routing_engine.record')
    def test_checkin_blocked_appointment(self, mock_record, mock_eval, mock_active, mock_get_patient):
        """Test check-in blocked for cancelled appointment."""
        mock_get_patient.return_value = {'patient_id': 1}
        mock_active.return_value = None
        mock_eval.return_value = {
            'blocked': True,
            'decision_reason': 'Appointment cancelled'
        }

        result = process_checkin(patient_id=1, appointment_id=1)

        assert result['success'] is False
        assert result['blocked'] is True
        assert 'cancelled' in result['reason'].lower()


class TestDoctorCanTreatPatient:
    """Test doctor access control."""

    @patch('database.doctor_can_access_patient')
    def test_doctor_treats_assigned_patient(self, mock_can_access):
        """Test doctor can treat assigned patient."""
        mock_can_access.return_value = True
        assert doctor_can_treat_patient(1, 1) is True

    @patch('database.doctor_can_access_patient')
    @patch('database.get_active_checkin')
    @patch('database.get_departments_for_doctor')
    def test_doctor_treats_checked_in_patient_same_dept(self, mock_get_depts, mock_active, mock_can_access):
        """Test doctor can treat checked-in patient in same department."""
        mock_can_access.return_value = False
        mock_active.return_value = {'assigned_department_id': 1}
        mock_get_depts.return_value = [{'department_id': 1}, {'department_id': 2}]

        assert doctor_can_treat_patient(1, 1) is True

    @patch('database.doctor_can_access_patient')
    @patch('database.get_active_checkin')
    @patch('database.get_departments_for_doctor')
    def test_doctor_cannot_treat_other_dept(self, mock_get_depts, mock_active, mock_can_access):
        """Test doctor cannot treat patient in different department."""
        mock_can_access.return_value = False
        mock_active.return_value = {'assigned_department_id': 3}
        mock_get_depts.return_value = [{'department_id': 1}, {'department_id': 2}]

        assert doctor_can_treat_patient(1, 1) is False