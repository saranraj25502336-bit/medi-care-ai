# -*- coding: utf-8 -*-
"""Centralized audit logging (writes to audit_logs)."""
import ipaddress  # noqa
from database import log_audit_row

__all__ = ['log_audit']


def log_audit(user_type=None, user_id=None, action='', entity_type=None,
              entity_id=None, details=None, request=None, conn=None):
    """Record an auditable action. Never blocks the caller (best effort)."""
    ip = ''
    if request is not None:
        ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or '')
        ip = ip.split(',')[0].strip()[:45]
    try:
        log_audit_row(
            user_type=user_type, user_id=user_id, action=action,
            entity_type=entity_type, entity_id=entity_id,
            details=details, ip_address=ip or '',
        )
    except Exception as e:  # pragma: no cover - audit must never crash the app
        print(f'[audit] failed to log {action}: {e}')
