"""Tests for routing engine."""
import pytest
from unittest.mock import MagicMock, patch

# Import inside tests


class TestRoutingEngine:
    """Test rule-based routing."""

    def test_evaluate_default_fallback(self):
        """Test default fallback when no rules match."""
        from modules import routing_engine
        context = {
            'patient_id': 1,
            'appointment_exists': False,
            'clinical_priority': 'normal',
            'doctor_available': True,
            'department_available': True
        }
        # Should use default routing when no DB rules
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = []
            decision = routing_engine.evaluate(context)
            assert decision['blocked'] is False
            assert 'assigned_department_id' in decision
            assert 'queue_category' in decision

    def test_evaluate_appointment_priority(self):
        """Test appointment gets priority over walk-in."""
        from modules import routing_engine
        context = {
            'patient_id': 1,
            'appointment_exists': True,
            'appointment_status': 'scheduled',
            'appointment_type': 'regular',
            'doctor_available': True,
            'department_available': True,
            'clinical_priority': 'normal'
        }
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = []
            decision = routing_engine.evaluate(context)
            assert decision['queue_category'] in ('regular', 'followup', 'clinically_prioritized')

    def test_evaluate_clinical_priority(self):
        """Test clinically prioritized patients get higher queue category."""
        from modules import routing_engine
        context = {
            'patient_id': 1,
            'appointment_exists': False,
            'clinical_priority': 'emergency',
            'doctor_available': True,
            'department_available': True
        }
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = []
            decision = routing_engine.evaluate(context)
            assert decision['queue_category'] == 'clinically_prioritized'

    def test_evaluate_doctor_unavailable_fallback(self):
        """Test fallback when doctor unavailable."""
        from modules import routing_engine
        context = {
            'patient_id': 1,
            'appointment_exists': True,
            'appointment_status': 'scheduled',
            'doctor_available': False,
            'department_available': True
        }
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = []
            decision = routing_engine.evaluate(context)
            # Should still route but maybe to different doctor/dept
            assert 'assigned_department_id' in decision

    def test_evaluate_department_unavailable(self):
        """Test handling when department unavailable."""
        from modules import routing_engine
        context = {
            'patient_id': 1,
            'appointment_exists': False,
            'clinical_priority': 'normal',
            'doctor_available': True,
            'department_available': False
        }
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = []
            decision = routing_engine.evaluate(context)
            # Should fallback to default department
            assert 'assigned_department_id' in decision

    def test_record_routing_decision(self):
        """Test routing decision is recorded."""
        from modules import routing_engine
        context = {'patient_id': 1}
        decision = {'assigned_department_id': 1, 'queue_category': 'regular'}
        with patch('modules.routing_engine.Database') as mock_db:
            mock_db.return_value.execute_query.return_value = 1
            routing_engine.record(1, decision, None, 'reception')
            mock_db.return_value.execute_query.assert_called()


class TestRoutingRules:
    """Test custom routing rules from database."""

    def test_rule_matching(self):
        """Test rule conditions are evaluated correctly."""
        from modules import routing_engine
        # Rules are JSON conditions like:
        # {"clinical_priority": "emergency"} -> {"queue_category": "clinically_prioritized"}
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = [
                {
                    'id': 1,
                    'priority': 10,
                    'conditions': '{"clinical_priority": "emergency"}',
                    'actions': '{"queue_category": "clinically_prioritized"}'
                }
            ]
            context = {
                'patient_id': 1,
                'clinical_priority': 'emergency',
                'doctor_available': True,
                'department_available': True
            }
            decision = routing_engine.evaluate(context)
            assert decision['queue_category'] == 'clinically_prioritized'

    def test_rule_priority_order(self):
        """Test higher priority rules win."""
        from modules import routing_engine
        with patch('modules.routing_engine.get_routing_rules') as mock_rules:
            mock_rules.return_value = [
                {
                    'id': 1,
                    'priority': 5,
                    'conditions': '{}',
                    'actions': '{"queue_category": "regular"}'
                },
                {
                    'id': 2,
                    'priority': 10,
                    'conditions': '{"clinical_priority": "urgent"}',
                    'actions': '{"queue_category": "clinically_prioritized"}'
                }
            ]
            context = {
                'patient_id': 1,
                'clinical_priority': 'urgent',
                'doctor_available': True,
                'department_available': True
            }
            decision = routing_engine.evaluate(context)
            assert decision['queue_category'] == 'clinically_prioritized'