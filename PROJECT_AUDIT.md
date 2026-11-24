# PROJECT AUDIT — Smart Hospital System

**Project:** Fast Patient Check-In and Smart Appointment Routing Using Rule-Based Algorithm in Healthcare
**Location:** `c:\xampp\htdocs\project`
**Audit date:** 2026-11-04
**Phase:** 1 (source-code audit + critical security fixes + backup + schema foundation)

---

## Audit summary

| Area | Working | Partially implemented | Missing / broken |
|---|---|---|---|
| Patient registration + face enrollment | OK | | |
| Face recognition login (InsightFace/ArcFace) | OK | low-confidence gate missing | |
| Patient manual login | OK (was insecure) | | |
| Doctor login | OK (was insecure) | | |
| Patient dashboard + appointments | OK | | |
| Doctor dashboard + prescriptions | OK | | |
| Admin login + chatbot training UI | OK | | |
| AI chatbot (Groq, multilingual, voice) | OK | | |
| Departments / routing / check-in / queue / QR | | | foundation tables added, logic planned |
| Reception / department dashboards | | | missing |
| Real-time updates, waiting times, analytics | | | missing |
| Automated test suite | | smoke tests only | pytest planned |

---

## HIGHLIGHT: Security vulnerabilities (highest priority)

| # | File | Route / function | Problem | Correction | Priority | Status |
|---|---|---|---|---|---|---|
| S1 | app.py | `patient_direct()` `/patient/<id>` | Anonymous visitor could set session to ANY patient id = total auth bypass. | Require the caller to already be authenticated as that same patient. | Critical | FIXED |
| S2 | app.py | `manual_login()` `/manual-login` | Login allowed with NO password whenever patient had no stored hash (all legacy patients). | Password is now always required; accounts without a password get a clear message and must use Face Login / reception. | Critical | FIXED |
| S3 | app.py | `/api/patient/<id>` | Public API returned full medical records, phone, email, appointments for any patient id (IDOR + PHI leak). | Require the patient themselves or staff (doctor/admin); 403 otherwise. | Critical | FIXED |
| S4 | app.py | `doctor_login()` `/doctor-login` | Single shared access code allowed impersonating any doctor. | Per-doctor bcrypt passwords (`doctors.password`). Migration seeds default `doctor123`. | Critical | FIXED |
| S5 | app.py | `/find-patient`, `/find-patient/scan` | Face-search endpoint (returns records) was fully public. | Now requires staff (doctor/admin) session. Patient face login stays public. | Critical | FIXED |
| S6 | app.py | all login routes | No session regeneration => session-fixation risk. | `session.clear()` + re-init on every login; booking redirect intent preserved. | High | FIXED |
| S7 | app.py | `/logout`, `/doctor-logout`, `/admin-logout` | Only one key popped; other auth keys could persist. | `session.clear()`. | High | FIXED |
| S8 | app.py | `admin_login_page()` | Default admin/admin123 in plaintext env; no rate limit. | Rate limit + session regen added. Recommended: bcrypt `ADMIN_PASSWORD_HASH` env. | High | PARTIAL |
| S9 | app.py | all POST APIs | No CSRF token (only SameSite=Lax). | CSRF token middleware - Phase 1.1. | High | PLANNED |
| S10 | app.py | `/doctor/update-patient`, `/add-prescription`, `/doctor/patient/<id>`, `/api/records/<id>` | Any doctor can view/update ANY patient - no boundary between doctors. | Role/permission checks keyed to assigned patients. | High | PLANNED |
| S11 | app.py | `register()` | No registration rate limit; duplicate face registration is detected but API not throttled. | Rate limit + optional captcha. | Medium | PLANNED |
| S12 | config.php / config.py | API keys | Working Groq key hardcoded in `config.php` inside the repo. | Move to env vars only (.env is gitignored). | Medium | PARTIAL |
| S13 | .env | secret key | Default `change-this-to-a-random-secret-key`. | Generate a strong SECRET_KEY. | Medium | ACTION REQUIRED |
| S14 | templates + chatbot.js | chat rendering | Old bubbles used innerHTML with raw text (XSS). | New shared chatbot.js escapes HTML and only applies safe formatting. | High | FIXED |
| S15 | app.py | cookies | HttpOnly + SameSite=Lax set; Secure only when not DEBUG. | Keep Secure in production behind HTTPS; document. | Medium | DOC |

---

## Functionality issues & gaps

| # | File | Route / function | Problem | Correction | Priority | Status |
|---|---|---|---|---|---|---|
| F1 | app.py | `face_login()` | Recognition confidence not gated: low-confidence matches still log in. | When confidence < threshold => "Patient not verified", offer QR/manual verify. Calibrate threshold empirically (measure FAR/FRR). | High | PLANNED |
| F2 | app.py | `/book-appointment` | No doctor-availability / slot-capacity / duplicate-booking checks. | Validate schedule, capacity, conflicts; DB constraints + transaction. | High | PLANNED |
| F3 | database | `appointments` | Status ENUM lacks `cancelled`; no `rescheduled`/`followup` handling. | Extend ENUM via migration (backward compatible). | High | PLANNED |
| F4 | database.py | `_create_tables` | Auto-schema unaware of new Phase-1 tables. | Migrations are the source of truth; optionally mirror later. | Medium | PLANNED |
| F5 | database.py | `medical_records` | `doctor_name` free string, no `doctor_id` FK. | Add `doctor_id` FK in later migration; keep legacy column. | Medium | PLANNED |
| F6 | database.py | FK delete policies | `ON DELETE CASCADE` on patients wipes history + appointments. | `SET NULL` / soft-delete + audit retention policy. | Medium | PLANNED |
| F7 | app.py | `update_appointment_status` | No status-transition validation or rejection reason. | Allowed-transition map + `rejection_reason` column. | High | PLANNED |
| F8 | chatbot.py | `_get_openrouter_response` | Uses `mistralai/mistral-7b-instruct` (may be dead). Main Groq path is fixed/current. | Refresh free OpenRouter model list. | Low | PLANNED |
| F9 | notifications.py | email/SMS | Stub/opt-in only; no delivery queue, retries, logs. | Wire `notification_delivery_logs` + background retry + Ta/En templates. | Medium | PLANNED |
| F10 | qa_verify.py | smoke checks | Not a pytest suite. | Build pytest suite with fixture DB + mocks for SMS/AI. | High | PLANNED |
| F11 | app.py / admin | analytics | No real Chart.js analytics. | Real DB aggregates: department workload, daily check-ins, wait times. | Medium | PLANNED |
| F12 | database.py | concurrency | No transaction helper; concurrent check-ins/tokens can race. | Transaction helpers + row locks for tokens/check-ins. | High | PLANNED |

---

## New modules (foundation added, logic planned)

| Module | Files / tables | Status |
|---|---|---|
| Department management | `departments` + `doctor_departments` + `doctor_schedules` | Tables + seeds OK | API/UI Phase 2 |
| Smart check-in (face / QR / manual) | `checkins` | Table OK | Logic Phase 3-4 |
| Appointment QR tokens | `appointment_qr_tokens` | Table OK | Logic Phase 4 |
| Rule-based routing engine | `modules/routing_engine.py` + `routing_rules`/`routing_logs` | Tables + RULE 001-010 seeds OK | Engine Phase 5 |
| Queue management + tokens | `modules/queue_management.py` + `queue_tokens`/`queue_events` | Tables OK (dup-active guard) | Engine Phase 6 |
| Reception dashboard | routes + template | Phase 7 |
| Department dashboard | routes + template | Phase 7 |
| Doctor dashboard upgrades | follow-ups, queue, history | Phase 8 |
| Real-time updates | Flask-SocketIO + event bus | Phase 9 |
| Waiting-time estimation | service module | Phase 6/9 |
| Audit logging | `audit_logs` | Table OK | Wiring Phase 2+ |
| Notification delivery logs | `notification_delivery_logs` | Table OK | Wiring Phase 9 |

---

## Already working (preserved & verified)

- Patient registration (+ optional password + face enrollment).
- Face login (InsightFace/ArcFace ensemble + cosine similarity + confidence).
- Manual login (now password-required) and patient/doctor/admin roles.
- Patient dashboard, appointment booking/list, doctor dashboards, prescriptions.
- Admin login + chatbot-training management.
- Groq multilingual chatbot with voice input (WebSpeech + Whisper) and TTS output - now answers shortly, simply, with a **bold** key answer.
- Self-care suggestion API, notification stubs, DB connection pooling.

---

## Backup and migration status

- OK Backup: `database_backups/hospital_management_2026-11-04.sql` (80 KB)
- OK Migration applied: `migrations/001_smart_hospital_core.sql` (23 statements, 0 failed)
  - Security/profile columns on `patients` + `doctors`.
  - New tables: `departments`, `doctor_departments`, `doctor_schedules`, `checkins`,
    `routing_rules`, `routing_logs`, `queue_tokens` (+ unique active-token guard),
    `queue_events`, `appointment_qr_tokens`, `patient_followups`, `audit_logs`,
    `notification_delivery_logs`.
  - Seeded 8 departments, doctor-department links, routing rules **RULE 001-010**.
- OK Per-doctor bcrypt passwords seeded (default `doctor123` - change these).

## External credentials / hardware still required

- Groq API key (working key in `config.php` / `.env`).
- SMTP + Fast2SMS credentials for real notifications (optional, disabled by default).
- Camera for face enrollment / recognition (test on real device).
- HTTPS certificate for production.
