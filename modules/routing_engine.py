# -*- coding: utf-8 -*-
"""Rule-based routing engine (deterministic - never delegated to an LLM).

Reads configurable rules from MySQL `routing_rules`, matches them against a
check-in context, produces a decision, and records it in `routing_logs`.
"""
import json
from database import get_routing_rules, create_routing_log


def evaluate_condition(condition, context):
    """All keys in `condition` must match `context`."""
    for key, expected in condition.items():
        actual = context.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif isinstance(expected, bool):
            if bool(actual) != expected:
                return False
        else:
            if actual != expected:
                return False
    return True


def _apply_action(action, context, rule):
    act = action.get('action', 'reception_intervention')
    dept_id = (
        action.get('department_id')
        or context.get('doctor_department_id')
        or context.get('default_department_id')
    )
    queue = action.get('queue', 'regular')

    decision = {
        'applied_rule': rule.get('rule_code'),
        'rule_id': rule.get('rule_id'),
        'action': act,
        'blocked': act in ('block_checkin', 'reception_intervention'),
        'assigned_department_id': dept_id,
        'queue_category': queue,
        'decision_reason': rule.get('description') or rule.get('name', ''),
    }
    if act == 'route_to_department' and context.get('doctor_department_id'):
        decision['assigned_department_id'] = context['doctor_department_id']
    if act == 'immediate_assessment':
        decision['queue_category'] = 'clinically prioritized'
        decision['emergency_hint'] = True
    if act == 'return_existing_token':
        decision['queue_category'] = context.get('existing_token_category') or 'regular'
    return decision


def evaluate(context):
    """Return a routing decision dict. Never raises."""
    context.setdefault('has_active_checkin', False)
    context.setdefault('appointment_exists', bool(context.get('appointment')))
    context.setdefault('appointment_status', None)
    context.setdefault('appointment_type', 'regular')
    context.setdefault('doctor_available', True)
    context.setdefault('department_available', True)
    context.setdefault('clinical_priority', 'normal')
    context.setdefault('default_department_id', None)

    # RULE 008 - an existing active check-in always wins (prevents duplicates)
    if context.get('has_active_checkin'):
        rule = {'rule_code': 'RULE 008', 'rule_id': None,
                'name': 'Active check-in prevents duplication'}
        return _apply_action({'action': 'return_existing_token'}, context, rule)

    rules = get_routing_rules() or []
    rules.sort(key=lambda r: (r.get('priority') or 100, r.get('rule_id') or 0))
    for rule in rules:
        try:
            condition = json.loads(rule.get('condition_json') or '{}')
        except Exception:
            condition = {}
        if not evaluate_condition(condition, context):
            continue
        try:
            action = json.loads(rule.get('action_json') or '{}')
        except Exception:
            action = {}
        return _apply_action(action, context, rule)

    return {
        'applied_rule': None, 'rule_id': None, 'action': 'reception_intervention',
        'blocked': True, 'assigned_department_id': context.get('default_department_id'),
        'queue_category': 'regular',
        'decision_reason': 'No routing rule matched - forwarded to reception.',
    }


def record(patient_id, decision, appointment_id=None, recorded_by=None):
    """Persist a routing decision to routing_logs (best effort)."""
    try:
        create_routing_log(
            patient_id=patient_id,
            appointment_id=appointment_id,
            rule_id=decision.get('rule_id'),
            department_id=decision.get('assigned_department_id'),
            queue_category=decision.get('queue_category', 'regular'),
            reason=decision.get('decision_reason', ''),
            recorded_by=recorded_by,
        )
    except Exception as e:  # pragma: no cover
        print(f'[routing] log write failed: {e}')
    return decision
