"""Tests for queue management."""
import pytest
from unittest.mock import MagicMock, patch

# Import inside tests


class TestQueueManagement:
    """Test department queue operations."""

    @patch('modules.queue_management.Database')
    def test_generate_token_creates_sequence(self, mock_db):
        """Test token generation creates department-prefixed sequence."""
        from modules import queue_management
        mock_db.return_value.fetch_one.side_effect = [
            {'max_seq': 0},  # For sequence lookup
            {'department_id': 1, 'name': 'General Medicine', 'prefix': 'GM'}
        ]
        mock_db.return_value.execute_query.return_value = 1

        token = queue_management.generate_token(
            department_id=1,
            department_name='General Medicine',
            patient_id=1,
            category='regular',
            checkin_id=1
        )

        assert token is not None
        assert 'token_code' in token
        assert token['token_code'].startswith('GM-')
        assert 'queue_number' in token
        assert token['queue_number'] == 1

    @patch('modules.queue_management.Database')
    def test_generate_token_increments_sequence(self, mock_db):
        """Test token sequence increments correctly."""
        from modules import queue_management
        mock_db.return_value.fetch_one.side_effect = [
            {'max_seq': 5},  # Existing max sequence
            {'department_id': 1, 'name': 'General Medicine', 'prefix': 'GM'}
        ]
        mock_db.return_value.execute_query.return_value = 1

        token = queue_management.generate_token(
            department_id=1,
            department_name='General Medicine',
            patient_id=1,
            category='regular',
            checkin_id=1
        )

        assert token['queue_number'] == 6

    @patch('modules.queue_management.Database')
    def test_priority_sorting(self, mock_db):
        """Test queue sorts by priority then time."""
        from modules import queue_management
        # Categories in priority order: clinically_prioritized > followup > walkin > regular
        mock_db.return_value.fetch_all.return_value = [
            {'token_id': 1, 'token_code': 'GM-R-001', 'queue_category': 'regular', 'created_at': '2025-01-01 10:00:00'},
            {'token_id': 2, 'token_code': 'GM-C-001', 'queue_category': 'clinically_prioritized', 'created_at': '2025-01-01 10:05:00'},
            {'token_id': 3, 'token_code': 'GM-F-001', 'queue_category': 'followup', 'created_at': '2025-01-01 10:03:00'},
            {'token_id': 4, 'token_code': 'GM-W-001', 'queue_category': 'walkin', 'created_at': '2025-01-01 10:02:00'},
        ]

        queue = queue_management.get_queue(1)
        # Should be ordered: clinically_prioritized, followup, walkin, regular
        categories = [item['queue_category'] for item in queue]
        assert categories == ['clinically_prioritized', 'followup', 'walkin', 'regular']

    @patch('modules.queue_management.Database')
    def test_estimate_wait_time(self, mock_db):
        """Test wait time estimation."""
        from modules import queue_management
        mock_db.return_value.fetch_one.return_value = {'count': 5}
        mock_db.return_value.fetch_all.return_value = [
            {'avg_consultation_min': 10}  # Average consultation time
        ]

        wait = queue_management.estimate_wait_min(1)
        # 5 patients * 10 min = ~50 min (with some factor)
        assert wait > 0

    @patch('modules.queue_management.Database')
    def test_call_next_token(self, mock_db):
        """Test calling next token in queue."""
        from modules import queue_management
        mock_db.return_value.execute_query.return_value = 1
        mock_db.return_value.fetch_one.return_value = {
            'token_id': 1,
            'token_code': 'GM-C-001',
            'patient_id': 1,
            'queue_category': 'clinically_prioritized'
        }

        result = queue_management.call_next(1, 1)  # dept_id=1, doctor_id=1

        assert result['success'] is True
        assert result['token']['token_code'] == 'GM-C-001'

    @patch('modules.queue_management.Database')
    def test_complete_token(self, mock_db):
        """Test marking token as completed."""
        from modules import queue_management
        mock_db.return_value.execute_query.return_value = 1

        result = queue_management.complete_token(1, 1)  # token_id=1, doctor_id=1

        assert result['success'] is True

    @patch('modules.queue_management.Database')
    def test_skip_token(self, mock_db):
        """Test skipping a token."""
        from modules import queue_management
        mock_db.return_value.execute_query.return_value = 1

        result = queue_management.skip_token(1, 1, 'Patient not present')

        assert result['success'] is True

    @patch('modules.queue_management.Database')
    def test_get_queue_stats(self, mock_db):
        """Test queue statistics."""
        from modules import queue_management
        mock_db.return_value.fetch_one.side_effect = [
            {'count': 10},  # waiting
            {'count': 2},   # in_progress
            {'count': 15},  # completed
            {'avg_wait': 25.5}  # avg wait
        ]

        stats = queue_management.get_queue_stats(1)

        assert stats['waiting'] == 10
        assert stats['in_progress'] == 2
        assert stats['completed'] == 15
        assert stats['avg_wait_min'] == 25.5