# -*- coding: utf-8 -*-
"""Lightweight CSRF protection + security headers."""
import secrets
from functools import wraps
from flask import session, jsonify, request


def generate_csrf_token():
    """Create (or reuse) a per-session CSRF token."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_urlsafe(32)
    return session['_csrf_token']


def get_csrf_token():
    return session.get('_csrf_token', '')


def csrf_required(f):
    """Decorator for state-changing endpoints: token must be in JSON or header."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        token = get_csrf_token()
        if not token:
            return jsonify({'success': False, 'message': 'CSRF token missing. Login again.'}), 403
        sent = (request.get_json(silent=True) or {}).get('csrf_token') or \
               request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        if not sent or sent != token:
            return jsonify({'success': False, 'message': 'CSRF validation failed. Refresh and retry.'}), 403
        return f(*args, **kwargs)

    return wrapper


def add_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'same-origin')
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; style-src 'self' 'unsafe-inline' "
        "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com "
        "https://cdn.jsdelivr.net; img-src 'self' data: blob: https:; "
        "connect-src 'self' https:; media-src 'self' blob:;"
    )
    return response
