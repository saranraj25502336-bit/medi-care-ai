# -*- coding: utf-8 -*-
"""Appointment QR tokens: opaque random tokens; only SHA-256 hashes are stored."""
import base64
import hashlib
import io
import secrets
from datetime import datetime, timedelta
from database import create_qr_token, get_qr_by_hash, mark_qr_used, get_qrs_for_appointment


def _sha256(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def generate_token():
    return secrets.token_urlsafe(32)


def issue_for_appointment(appointment_id, appointment_date=None):
    """Create a fresh QR token for an appointment. Returns the raw token string."""
    token = generate_token()
    if appointment_date:
        try:
            expires = datetime.combine(appointment_date, datetime.min.time()) + timedelta(days=1)
        except Exception:
            expires = datetime.now() + timedelta(hours=12)
    else:
        expires = datetime.now() + timedelta(hours=12)
    create_qr_token(appointment_id, _sha256(token), expires)
    return token


def verify_token(token):
    """Validate + consume a QR token. Returns dict: {valid, reason, appointment_id}."""
    if not token:
        return {'valid': False, 'reason': 'No token provided.'}
    row = get_qr_by_hash(_sha256(str(token).strip()))
    if not row:
        return {'valid': False, 'reason': 'Invalid QR token.'}
    if row.get('is_revoked'):
        return {'valid': False, 'reason': 'This QR code has been revoked.'}
    if row.get('used_at'):
        return {'valid': False, 'reason': 'This QR code has already been used.'}
    expires = row.get('expires_at')
    if expires:
        try:
            if getattr(expires, 'tzinfo', None) is not None:
                expires = expires.replace(tzinfo=None)
        except Exception:
            pass
        if datetime.now() > expires:
            return {'valid': False, 'reason': 'This QR code has expired.'}
    mark_qr_used(row['qr_id'])
    return {'valid': True, 'reason': 'valid', 'appointment_id': row['appointment_id']}


def qr_data_uri(token):
    """PNG QR image as a data URI for embedding in pages."""
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(token)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#0f172a', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def tokens_for_appointment(appointment_id):
    """Return qr rows (hashes only) for an appointment - used for revoke/UI."""
    return get_qrs_for_appointment(appointment_id) or []
