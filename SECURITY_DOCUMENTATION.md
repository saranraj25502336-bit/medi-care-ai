# SECURITY DOCUMENTATION

## What was fixed (Phase 1)
| # | Finding | Fix |
|---|---|---|
| S1 | `/patient/<id>` allowed anyone to adopt a patient session | Owner-only now |
| S2 | Manual login allowed **passwordless** login when no hash existed | Password always required |
| S3 | `/api/patient/<id>` publicly leaked medical records (IDOR) | Own-patient or staff only (403) |
| S4 | Shared doctor access code | Per-doctor **bcrypt** passwords |
| S5 | Public face-search endpoints | Staff login required |
| S6 | Session fixation | `session.clear()` + regen on every login |
| S7 | Partial logout | Full session clear |

## Controls in place
- **Passwords** — bcrypt hashes for patients and doctors. No plaintext stored.
- **Sessions** — HttpOnly + SameSite=Lax cookies; `Secure` when `DEBUG=0`.
- **CSRF** — per-session token required on all new state-changing `/api/*` endpoints (see `modules/security.py`).
- **Rate limiting** — flask-limiter: manual-login/doctor-login/admin-login 10/min, face-login 15/min,
  chatbot 30/min, voice 20/min.
- **Authorization** — patient records owner/staff gated; staff dashboards require doctor-or-admin session;
  admin routes require admin session; routing/queue APIs require staff; analyses require admin.
- **SQL injection** — all DB access uses parameterized queries.
- **XSS** — chatbot bubbles and new templates escape user input; CSP + nosniff headers set globally.
- **Biometric data** — face embeddings remain in `patients.face_encoding` (encrypt at-rest in production);
  unknown/low-confidence matches are rejected; QR/manual fallback always available.
- **Correct routing** — the rule engine is deterministic (no LLM decisions); emergencies escalate to staff/108.
- **Audit trail** — `audit_logs` records check-ins, approvals, and admin actions with actor + IP.

## Still recommended (documented in PROJECT_AUDIT.md)
1. Set strong `SECRET_KEY` and change default admin password (`admin123`).
2. Change every doctor's default password `doctor123`.
3. Store admin password as a bcrypt hash in env (`ADMIN_PASSWORD_HASH`) instead of plaintext.
4. Move the Groq key out of `config.php` into environment only.
5. Enable HTTPS (see DEPLOYMENT_GUIDE.md) so `Secure` cookies apply.
6. Encrypt face templates at rest and enforce biometric consent capture during enrollment.
7. Add CAPTCHA/rate-limit on public registration.
8. Add per-patient doctor authorization boundaries (doctor ↔ assigned patients) — currently any logged-in
   doctor can view any patient via `/doctor/patient/<id>` and `/api/records/<id>`.
