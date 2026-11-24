# -*- coding: utf-8 -*-
"""Automated tests for the Smart Check-In & Rule-Based Routing system.

Run with:  python -m pytest tests/test_smart_checkin.py -q
"""
import pytest
from unittest.mock import MagicMock, patch


class TestRoutingEngineRules:
    """Test routing engine rule evaluation."""

    def test_rule_engine_routes_approved(self):
        """Test approved appointments route to doctor's department."""
        from modules import routing_engine
        ctx = {
            'appointment': {'status': 'approved'},
            'appointment_status': 'approved',
            'doctor_available': True,
            'department_available': True,
            'doctor_department_id': 2,
            'default_department_id': 1,
            'has_active_checkin': False
        }
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = [
                {
                    'id': 1,
                    'priority': 10,
                    'conditions': '{"appointment_status": "approved", "doctor_available": true}',
                    'actions': '{"applied_rule": "RULE 001", "assigned_department_id": 2}'
                }
            ]
            d = routing_engine.evaluate(ctx)
            assert d['applied_rule'] == 'RULE 001'
            assert d['assigned_department_id'] == 2

    def test_rule_engine_blocks_rejected(self):
        """Test rejected appointments block check-in."""
        from modules import routing_engine
        ctx = {
            'appointment': {'status': 'rejected'},
            'appointment_status': 'rejected',
            'default_department_id': 1,
            'has_active_checkin': False
        }
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = [
                {
                    'id': 1,
                    'priority': 10,
                    'conditions': '{"appointment_status": "rejected"}',
                    'actions': '{"action": "block_checkin", "blocked": true}'
                }
            ]
            d = routing_engine.evaluate(ctx)
            assert d.get('action') == 'block_checkin'
            assert d.get('blocked') is True

    def test_rule_engine_walkin(self):
        """Test walk-in patients get walkin queue category."""
        from modules import routing_engine
        ctx = {
            'appointment_exists': False,
            'appointment_status': None,
            'default_department_id': 1,
            'has_active_checkin': False
        }
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = [
                {
                    'id': 1,
                    'priority': 5,
                    'conditions': '{"appointment_exists": false}',
                    'actions': '{"queue_category": "walkin"}'
                }
            ]
            d = routing_engine.evaluate(ctx)
            assert d['queue_category'] == 'walkin'

    def test_rule_engine_duplicate(self):
        """Test duplicate check-in is detected."""
        from modules import routing_engine
        ctx = {
            'has_active_checkin': True,
            'default_department_id': 1
        }
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = [
                {
                    'id': 8,
                    'priority': 1,
                    'conditions': '{"has_active_checkin": true}',
                    'actions': '{"applied_rule": "RULE 008", "duplicate": true}'
                }
            ]
            d = routing_engine.evaluate(ctx)
            assert d['applied_rule'] == 'RULE 008'

    def test_rule_engine_urgent_priority(self):
        """Test urgent clinical priority gets clinically_prioritized queue."""
        from modules import routing_engine
        ctx = {
            'appointment': {'status': 'approved'},
            'appointment_status': 'approved',
            'clinical_priority': 'urgent',
            'default_department_id': 1,
            'has_active_checkin': False
        }
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = [
                {
                    'id': 2,
                    'priority': 15,
                    'conditions': '{"clinical_priority": "urgent"}',
                    'actions': '{"queue_category": "clinically_prioritized"}'
                }
            ]
            d = routing_engine.evaluate(ctx)
            assert d['queue_category'] == 'clinically_prioritized'


class TestQRService:
    """Test QR token service."""

    @patch('modules.qr_service.Database')
    def test_issue_and_verify_token(self, mock_db):
        """Test QR token issuance and verification (single-use)."""
        from modules import qr_service
        import time

        mock_db.return_value.execute_query.return_value = 1
        mock_db.return_value.fetch_one.return_value = {
            'token_id': 1,
            'token_hash': 'fakehash',
            'expires_at': '2099-12-31 23:59:59',
            'appointment_id': 1,
            'used': 0
        }

        # Issue token
        token = qr_service.issue_for_appointment(1, '2025-12-31')
        assert token is not None

        # Verify token first time - valid
        mock_db.return_value.fetch_one.return_value = {
            'token_id': 1,
            'token_hash': 'fakehash',
            'expires_at': '2099-12-31 23:59:59',
            'appointment_id': 1,
            'used': 0
        }
        mock_db.return_value.execute_query.return_value = 1
        v = qr_service.verify_token(token)
        assert v['valid'] is True
        assert v['appointment_id'] == 1

        # Verify token second time - invalid (single use)
        mock_db.return_value.fetch_one.return_value = {
            'token_id': 1,
            'token_hash': 'fakehash',
            'expires_at': '2099-12-31 23:59:59',
            'appointment_id': 1,
            'used': 1
        }
        v2 = qr_service.verify_token(token)
        assert v2['valid'] is False


class TestFullCheckinFlow:
    """Integration test for full check-in flow."""

    @patch('modules.checkin_service.process_checkin')
    @patch('modules.routing_engine.evaluate')
    @patch('modules.routing_engine.record')
    @patch('modules.queue_management.generate_token')
    @patch('database.create_checkin')
    @patch('database.get_active_checkin')
    @patch('database.get_patient_by_id')
    def test_full_checkin_flow_mocked(self, mock_get_patient, mock_active_checkin,
                                      mock_create_checkin, mock_gen_token,
                                      mock_record, mock_evaluate, mock_process):
        """Test full check-in flow with mocked dependencies."""
        from modules import checkin_service

        # Setup mocks
        mock_get_patient.return_value = {'patient_id': 1, 'full_name': 'Test Patient'}
        mock_active_checkin.return_value = None
        mock_evaluate.return_value = {
            'blocked': False,
            'assigned_department_id': 1,
            'queue_category': 'regular',
            'decision_reason': 'Test'
        }
        mock_create_checkin.return_value = 1
        mock_gen_token.return_value = {
            'token_code': 'GM-R-001',
            'queue_number': 1,
            'token_id': 1
        }

        result = checkin_service.process_checkin(
            patient_id=1,
            method='qr',
            appointment_id=1,
            walkin_department_id=None,
            clinical_priority='normal',
            recorded_by='reception'
        )

        assert result['success'] is True
        assert result['token']['token_code'] == 'GM-R-001'
        assert result['checkin_id'] == 1

    def test_duplicate_checkin_prevented(self):
        """Test duplicate check-in is prevented."""
        from modules import checkin_service

        with patch('modules.checkin_service.get_patient_by_id') as mock_get_patient:
            with patch('modules.checkin_service.get_active_checkin') as mock_active:
                mock_get_patient.return_value = {'patient_id': 1, 'full_name': 'Test'}
                mock_active.return_value = {'checkin_id': 1, 'appointment_id': None}

                with patch('modules.routing_engine.evaluate') as mock_eval:
                    mock_eval.return_value = {'blocked': False}
                    with patch('modules.routing_engine.record') as mock_record:
                        result = checkin_service.process_checkin(patient_id=1)

                        assert result['success'] is True
                        assert result['duplicate'] is True


class TestUnauthorizedAccess:
    """Test unauthorized access prevention."""

    def test_patient_api_requires_auth(self, client):
        """Test patient API requires authentication."""
        resp = client.get('/api/patient/1')
        assert resp.status_code in (401, 403, 302)

    def test_queue_api_requires_auth(self, client):
        """Test queue API requires authentication."""
        resp = client.get('/api/queue/1')
        assert resp.status_code in (401, 403, 302)

    def test_admin_analytics_requires_admin(self, client):
        """Test admin analytics requires admin login."""
        resp = client.get('/admin/analytics')
        assert resp.status_code in (302, 401, 403)

    def test_doctor_routes_require_doctor(self, client):
        """Test doctor routes require doctor login."""
        resp = client.get('/doctor')
        assert resp.status_code in (302, 401, 403)