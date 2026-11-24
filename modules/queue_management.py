# -*- coding: utf-8 -*-
"""Smart queue management: token generation, FIFO + priority, waiting time."""
import random
from database import (
    create_queue_token, get_token_by_code, get_active_tokens_for_department,
    get_queue_count_before, update_token_status, create_queue_event_row,
)

PREFIX_MAP = {
    'General Medicine': 'GEN', 'Cardiology': 'CARD', 'Orthopaedics': 'ORTH',
    'Paediatrics': 'PED', 'Neurology': 'NEUR', 'Dermatology': 'DERM',
    'ENT': 'ENT', 'Ophthalmology': 'OPHT', 'Emergency': 'ER',
}
CATEGORY_RANK = {
    'clinically prioritized': 0, 'priority': 0, 'followup': 1,
    'walkin': 2, 'regular': 3,
}


def dept_prefix(department_name):
    if not department_name:
        return 'GEN'
    name = str(department_name).strip()
    if name in PREFIX_MAP:
        return PREFIX_MAP[name]
    letters = ''.join(ch for ch in name if ch.isalpha())
    return (letters[:4] or 'GEN').upper()


def generate_token(department_id, department_name, patient_id, category='regular',
                   doctor_id=None, checkin_id=None, est_wait=None):
    """Create a unique department-prefixed token (retries on collision)."""
    prefix = dept_prefix(department_name)
    code = None
    for _ in range(6):
        seq = get_queue_count_before(department_id) + 1
        code = '{}-{:03d}'.format(prefix, seq)
        if not get_token_by_code(code):
            break
        code = '{}-{:03d}-{}'.format(prefix, seq, random.randint(10, 99))
        if not get_token_by_code(code):
            break
    token_id = create_queue_token(
        token_code=code, patient_id=patient_id, department_id=department_id,
        doc_id=doctor_id, checkin_id=checkin_id, category=category, est_wait=est_wait,
    )
    return get_token_by_code(code) or {'token_id': token_id, 'token_code': code}


def build_department_queue(department_id):
    """Active queue sorted by priority category then FIFO."""
    rows = get_active_tokens_for_department(department_id) or []
    for row in rows:
        row['category_rank'] = CATEGORY_RANK.get(row.get('queue_category'), 9)
    rows.sort(key=lambda r: (row_sort_key(r)))
    return rows


def row_sort_key(r):
    return (r['category_rank'], r.get('created_at') or '')


def call_next(department_id):
    """Advance to the next waiting patient; returns token row or None."""
    queue = build_department_queue(department_id)
    waiting = [r for r in queue if r.get('status') == 'waiting']
    if not waiting:
        return None
    nxt = waiting[0]
    update_token_status(nxt['token_id'], 'called', note='Next patient called')
    return get_token_by_code(nxt['token_code'])


def advance_status(token_id, status, note=''):
    update_token_status(token_id, status, note=note)
    create_queue_event_row(token_id, status, note)


def estimate_wait_min(department_id, avg_consult_min=15):
    """patients-ahead x average consultation duration (approximate)."""
    queue = get_active_tokens_for_department(department_id) or []
    ahead = len([r for r in queue if r.get('status') == 'waiting'])
    return round(ahead * avg_consult_min, 1)
