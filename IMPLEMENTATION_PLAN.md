# IMPLEMENTATION PLAN — Smart Patient Check-In & Rule-Based Appointment Routing

**Project:** Fast Patient Check-In and Smart Appointment Routing Using Rule-Based Algorithm in Healthcare
**Updated:** 2026-11-04

Execution is incremental: each phase ends with tests, DB-compat verification and this plan being updated.

---

## PHASE 1 — Audit + backup + critical security fixes  ✅ (in progress)
- [x] Full source-code audit -> `PROJECT_AUDIT.md`
- [x] Database backup -> `database_backups/hospital_management_2026-11-04.sql`
- [x] Fix unauthenticated session hijack (`/patient/<id>`)
- [x] Fix passwordless manual login
- [x] Fix public patient-record API (IDOR/PHI)
- [x] Replace shared doctor access code with per-doctor bcrypt passwords
- [x] Protect face-search endpoints (`/find-patient*`)
- [x] Session regeneration on all logins + full logout clears
- [x] Chatbot: short, simple, perfect answers with **bold** key answer (all languages)
- [ ] CSRF token middleware (Phase 1.1)
- [ ] Security headers + strong secret key + rate limits on register
- [ ] Admin password hash (bcrypt) support

## PHASE 2 — Database migrations + department management
- [x] `migrations/001_smart_hospital_core.sql` applied (departments, doctor-departments/schedules, checkins, routing_rules/logs, queue_tokens/events, QR tokens, followups, audit_logs, notification_logs)
- [ ] `migrations/run_migrations.py` hardened (done) + versioned migration doc
- [ ] Department CRUD APIs + admin UI (add/edit/deactivate/assign doctors/schedules)
- [ ] Appointment status ENUM extension (`cancelled`, `rescheduled`) + `rejection_reason`
- [ ] Replace DELETE CASCADE with soft-delete/retention policy
- [ ] Insert data-audit helper (wraps `audit_logs`)

## PHASE 3 — Appointment validation + patient check-in
- [ ] Appointment booking rules (doctor/date/time/capacity/duplicates) with transactions
- [ ] Status-transition validation (pending -> approved/rejected -> completed/cancelled)
- [ ] `checkins` module: face / QR / manual check-in flow, duplicate check-in prevention
- [ ] Check-in confirmation page + QR token generation on approval
- [ ] Authorize doctor access to assigned patients only (`/api/records`, `/doctor/patient`)

## PHASE 4 — QR verification + face recognition hardening
- [ ] `appointment_qr_tokens`: opaque random tokens, SHA-256 hash storage, expiry, revocation, single-use
- [ ] QR generation (qrcode lib) + QR scan page (camera JS) at reception
- [ ] Face: quality validation, duplicate-enrollment detection audit, low-confidence fallback to QR/manual
- [ ] Manual identity verification fallback UI

## PHASE 5 — Rule-based routing engine (`modules/routing_engine.py`)
- [x] Routing rules table + RULE 001-010 seeds
- [ ] Engine: evaluate appointment status/date/doctor/department/followup/walkin/priority
- [ ] `routing_logs` recording for every decision
- [ ] Admin UI to enable/disable/configure rules + conflict validation
- [ ] Emergency handling: never auto-diagnose; staff escalation only

## PHASE 6 — Queue management + waiting-time estimation
- [ ] `modules/queue_management.py`: token generation (dept prefix CARD-001 etc.), categories, FIFO + priority
- [ ] Token lifecycle state machine + queue_events log + recall/skip/cancel
- [ ] Duplicate active-token guard (DB unique constraint exists)
- [ ] Estimated waiting time = patients-ahead x avg duration (doctor-aware), clearly approximate
- [ ] Record actual wait times for future accuracy

## PHASE 7 — Reception + department dashboards
- [ ] Reception: today's appointments, check-in by face/QR/manual, routing result, token info, patient search
- [ ] Department: current token, waiting/called/consulting/completed, call next, start/complete, skip/recall
- [ ] Manual routing override with mandatory reason + audit log
- [ ] Real-time updates (Flask-SocketIO) with authorized channels + polling fallback

## PHASE 8 — Doctor dashboard + chronic follow-up
- [ ] Assigned queue, current patient, upcoming appointments, check-in time, appointment type
- [ ] Authorized medical history + previous prescriptions + allergies
- [ ] Consultation notes + prescription + follow-up scheduling (`patient_followups`)
- [ ] Follow-up reminders and retrieval of previous records for returning patients
- [ ] Never auto-prescribe from history

## PHASE 9 — Notifications + real-time + live queue tracking
- [ ] Notification templates (English + Tamil) for confirmation/rejection/reminder/token/called/follow-up
- [ ] `notification_delivery_logs` + background retry; never block check-in on SMS failure
- [ ] Real-time events: patient_checked_in, patient_routed, token_generated/called, consultation_started/completed, queue_updated, department_status_changed
- [ ] Patient live queue page (own token only, no other patients' data)

## PHASE 10 — Analytics + multilingual UI + offline fallback
- [ ] Chart.js dashboards from real DB data (dept workload, daily check-ins, weekly trends, wait times)
- [ ] Language selector (English/Tamil) for interface labels + notifications
- [ ] Controlled offline manual check-in with safe sync + duplicate prevention
- [ ] Workload monitoring + capacity alerts
- [ ] Accessibility + mobile responsiveness

## PHASE 11 — Security + automated testing + performance
- [ ] CSRF middleware, security headers, rate limits, IDOR tests
- [ ] pytest suite: registration/dup/face/QR expiry/reuse/check-in/duplicate/simultaneous/token-unique/unauthorised access/notification-failure/database recovery
- [ ] Load check on check-in/token concurrency
- [ ] Recognition FAR/FRR measurement procedure

## PHASE 12 — Documentation + deployment
- [ ] README, DATABASE_DOCUMENTATION, API_DOCUMENTATION, SECURITY_DOCUMENTATION
- [ ] Update SETUP_INSTRUCTIONS + DEPLOYMENT_GUIDE + TESTING_REPORT
- [ ] `.env.example` (no real secrets)
- [ ] MySQL backup/restore + biometric template backup + retention policy
- [ ] Gunicorn + Nginx + HTTPS deployment checklist

---

## Definitions of Done
- Every route is wired to a real backend + DB action (no fake buttons).
- Every sensitive endpoint requires authorization.
- Routing/queue decisions are auditable in `audit_logs`/`routing_logs`.
- The phase acceptance scenario (returning patient face/QR -> check-in -> route -> token -> department -> doctor -> consult -> complete -> queue advance) runs end-to-end.

---

## PHASE STATUS (updated at end of build sprint)

| Phase | Scope | Status |
|---|---|---|
| 1 | Audit, backup, critical security fixes, chatbot style | ✅ complete |
| 2 | Migration 001/002, departments CRUD + admin UI, audit log | ✅ complete |
| 3 | Appointment validation (transitions, conflict, rejection reason), check-in records + duplicate guard | ✅ complete |
| 4 | QR tokens (single-use, hashed, expiry/revoke), face check-in kiosk, low-confidence fallback | ✅ complete |
| 5 | `modules/routing_engine.py` + RULE 001-010, configurable/toggleable, `routing_logs` | ✅ complete |
| 6 | `modules/queue_management.py` + dept tokens + FIFO/priority + lifecycle + est. wait | ✅ complete |
| 7 | Reception + Department dashboards (polling realtime, bad-min fallback) | ✅ complete |
| 8 | Doctor dashboards + chronic follow-up scheduling API | ⚠️ partial (API + queue; doctor UI polish next) |
| 9 | Notifications (check-in/token/called/followup + delivery logs), realtime event bus, live my-queue page | ✅ complete |
| 10 | Admin analytics (Chart.js, real DB data), language selector base, offline note | ⚠️ partial (multi-language UI next) |
| 11 | Security (CSRF, headers, rate limits), pytest-style suite (`tests/test_smart_checkin.py` 7/7) | ✅ complete |
| 12 | Documentation (README, DATABASE, API, SECURITY, TESTING, DEPLOYMENT, .env.example) | ✅ complete |
