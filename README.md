# MediCare AI Hospital — Smart Patient Check-In & Rule-Based Appointment Routing

**Fast Patient Check-In and Smart Appointment Routing Using Rule-Based Algorithm in Healthcare**

A Flask + MySQL + InsightFace hospital management system with:
- Patient registration, biometric (face) enrollment and login
- Doctor / Admin dashboards, appointments, prescriptions, medical records
- **New:** Multilingual AI chatbot (Groq + Whisper voice, short bold answers)
- **New:** Smart patient check-in (Face / QR / Manual)
- **New:** Configurable rule-based routing engine (10 rules, admin toggleable)
- **New:** Department-wise smart queue with tokens (GEN-001, CARD-001, ...)
- **New:** Reception, Department, Admin Analytics and Patient live-queue pages
- **New:** Appointment QR tokens (single-use, hashed at rest), follow-ups, audit logs

## Quick start (XAMPP / local)

```bash
# 1. Database
mysql -u root < database.sql                 # schema + sample doctors
python migrations/run_migrations.py          # new tables, rules, doctor passwords

# 2. Install
pip install -r requirements.txt

# 3. Configure secrets -> copy .env.example to .env and fill in
#    (especially GROQ_API_KEY, SECRET_KEY, ADMIN_USERNAME/ADMIN_PASSWORD)

# 4. Run
python app.py
```

Default logins (CHANGE THEM in production):
| Role | Login | Password |
|---|---|---|
| Doctor | doctor_id 1 | doctor123 (per-doctor bcrypt) |
| Admin | admin | admin123 (env-based) |
| Patient | via registration | set during registration |

## Key pages
| URL | Who | Purpose |
|---|---|---|
| `/` | public | Home + login overlays |
| `/register` | public | Patient registration + face enrollment |
| `/checkin` | staff | Face / QR / manual check-in kiosk |
| `/reception` | staff | Reception dashboard (search, check-in, routing, alerts) |
| `/department/<id>` | staff | Department queue console (call-next, consult, complete) |
| `/my-queue` | patient | Live queue tracking (own token only) |
| `/admin/departments` | admin | Department CRUD + doctor assignment + rule toggles |
| `/admin/analytics` | admin | Chart.js analytics from real DB data |
| `/appointment/<id>/qr` | patient/staff | Single-use check-in QR |

## New end-to-end acceptance flow (verified by tests)
Patient arrival → identified by face/QR/manual → appointment verified → check-in recorded
→ rule engine routes to department → queue token generated → department dashboard shows patient
→ doctor calls next → consultation → completed → queue advances. All decisions audited.

Run tests: `python tests/test_smart_checkin.py`

See also: `PROJECT_AUDIT.md`, `IMPLEMENTATION_PLAN.md`, `DATABASE_DOCUMENTATION.md`,
`API_DOCUMENTATION.md`, `SECURITY_DOCUMENTATION.md`, `TESTING_REPORT.md`, `DEPLOYMENT_GUIDE.md`.
