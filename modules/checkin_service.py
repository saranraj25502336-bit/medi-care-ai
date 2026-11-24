# -*- coding: utf-8 -*-
"""Check-in orchestration: identify -> verify -> record -> route -> token."""
from datetime import datetime

from database import (
    get_patient_by_id, get_appointment_by_id, get_doctor_by_id,
    get_doctor_department_for_doctor, get_default_department_id,
    is_department_available, create_checkin, update_checkin_token,
    get_active_checkin, get_active_token_for_patient,
    get_department_by_id,
)
from modules import routing_engine, queue_management


def _doctor_available(doctor, appointment):
    """Doctor availability check (basic for now; schedules in doctor_schedules)."""
    if doctor is None:
        return True
    if doctor.get('is_active') is not None and int(doctor.get('is_active') or 1) == 0:
        return False
    return True


def _department_available(dept_id):
    if not dept_id:
        return True
    info = is_department_available(dept_id)
    return bool(info and info.get('available'))


def process_checkin(patient_id, method='manual', appointment_id=None,
                    walkin_department_id=None, clinical_priority='normal',
                    recorded_by='reception'):
    """Full check-in pipeline. Returns a result dict."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        return {'success': False, 'message': 'Patient not found.'}

    # 1) Duplicate prevention (active check-in today)
    existing = get_active_checkin(patient_id)
    if existing:
        token = get_active_token_for_patient(patient_id)
        decision = routing_engine.evaluate({
            'has_active_checkin': True, 'patient_id': patient_id,
            'existing_token_category': (token or {}).get('queue_category', 'regular'),
        })
        routing_engine.record(patient_id, decision, existing.get('appointment_id'), recorded_by)
        return {
            'success': True, 'duplicate': True, 'checkin': existing,
            'token': token, 'decision': decision,
            'message': 'You already have an active check-in for today.',
        }

    # 2) Gather routing context
    appointment = None
    if appointment_id:
        appointment = get_appointment_by_id(appointment_id)

    context_appointment = appointment
    doctor = None
    if appointment and appointment.get('doctor_id'):
        doctor = get_doctor_by_id(appointment['doctor_id'])
    doctor_dept = None
    if doctor:
        doctor_dept = get_doctor_department_for_doctor(doctor['doctor_id'])
    default_dept = get_default_department_id()

    dept_id_for_check = None
    if appointment and doctor_dept and doctor_dept.get('department_id'):
        dept_id_for_check = doctor_dept['department_id']
    elif walkin_department_id:
        dept_id_for_check = int(walkin_department_id)
    else:
        dept_id_for_check = default_dept

    clinical = clinical_priority or 'normal'
    context = {
        'patient_id': patient_id,
        'appointment': context_appointment,
        'appointment_exists': bool(appointment),
        'appointment_status': (appointment or {}).get('status'),
        'appointment_type': (appointment or {}).get('appointment_type') or 'regular',
        'doctor_available': _doctor_available(doctor, appointment),
        'department_available': _department_available(dept_id_for_check),
        'doctor_department_id': doctor_dept['department_id'] if doctor_dept else None,
        'default_department_id': default_dept,
        'clinical_priority': clinical,
        'has_active_checkin': False,
    }

    decision = routing_engine.evaluate(context)

    # 2a) Blocked check-in (cancelled/rejected appointment or similar)
    if decision.get('blocked'):
        reason = (appointment or {}).get('rejection_reason') or decision.get('decision_reason')
        routing_engine.record(patient_id, decision, appointment_id, recorded_by)
        return {
            'success': False, 'blocked': True, 'decision': decision,
            'reason': reason,
            'message': f"Check-in blocked: {reason}",
        }

    # 3) Record check-in
    checkin_id = create_checkin(
        patient_id=patient_id,
        appointment_id=appointment_id,
        method=method,
        clinical_priority=clinical,
    )
    if not checkin_id:
        return {'success': False, 'message': 'Check-in could not be recorded. Please try again.'}

    routing_engine.record(patient_id, decision, appointment_id, recorded_by)

    # 4) Generate queue token
    dept_id = decision.get('assigned_department_id') or default_dept
    dept = get_department_by_id(dept_id) if dept_id else None
    est_wait = queue_management.estimate_wait_min(dept_id) if dept_id else 0

    token = queue_management.generate_token(
        department_id=dept_id,
        department_name=(dept or {}).get('name', 'General Medicine'),
        patient_id=patient_id,
        category=decision.get('queue_category', 'regular'),
        doctor_id=(appointment or {}).get('doctor_id') if appointment else None,
        checkin_id=checkin_id,
        est_wait=est_wait,
    )
    if token:
        update_checkin_token(checkin_id, token.get('token_code') if isinstance(token, dict) else token)

    # Link department on the check-in row for reporting
    try:
        from database import Database
        Database().execute_query(
            'UPDATE checkins SET assigned_department_id = %s WHERE checkin_id = %s',
            (dept_id, checkin_id),
        )
    except Exception:
        pass

    result = {
        'success': True,
        'duplicate': False,
        'checkin_id': checkin_id,
        'decision': decision,
        'department': (dept or {}).get('name'),
        'department_id': dept_id,
        'token': token,
        'est_wait_min': est_wait,
    }
    return result


def doctor_can_treat_patient(doctor_id, patient_id):
    """True if the doctor may treat this patient: assigned via appointment/follow-up/
    record, OR patient has a today check-in routed to a department the doctor works in."""
    from database import (doctor_can_access_patient, get_active_checkin,
                          get_departments_for_doctor)
    if doctor_can_access_patient(doctor_id, patient_id):
        return True
    try:
        checkin = get_active_checkin(patient_id)
        if not checkin or not checkin.get('assigned_department_id'):
            return False
        depts = get_departments_for_doctor(doctor_id) or []
        return any(d.get('department_id') == checkin['assigned_department_id'] for d in depts)
    except Exception:
        return False
