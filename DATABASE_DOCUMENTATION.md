# DATABASE DOCUMENTATION

## Connection
- Engine: MySQL / MariaDB 10.4+ (XAMPP `hospital_management`)
- Host/port/user/password from `.env` (see `config.py`, `Config`)

## Tables

### Core (existing, preserved)
| Table | Purpose |
|---|---|
| `patients` | Patient profile + password bcrypt hash + face encoding. Extended with dob/gender/address/blood_group/emergency_contact/account_status/consent (`migrations/001`) |
| `doctors` | Doctor profile + per-doctor bcrypt `password` + `is_active` |
| `medical_records` | Symptoms, diagnosis, prescription, doctor notes |
| `appointments` | Booking; status ENUM extended to `pending/approved/rejected/completed/cancelled/rescheduled`; `rejection_reason`, `rescheduled_from`, `appointment_type` (`migrations/002`) |
| `chatbot_training` | Keyword→answer training data (admin-managed) |
| `notifications` | Notification log (legacy) |

### New (migrations/001 + 002)
| Table | Purpose |
|---|---|
| `departments` | Configurable departments (name, hours, capacity) |
| `doctor_departments` | Many-to-many doctor ↔ department |
| `doctor_schedules` | Weekly availability per doctor |
| `checkins` | Check-in records: method(face/qr/manual), status, dept, token link, clinical priority |
| `routing_rules` | Configurable rules (RULE 001–010) with JSON condition/action + priority + toggle |
| `routing_logs` | Every routing decision (rule, dept, category, reason, actor) |
| `queue_tokens` | Dept-prefixed tokens; `is_active` generated column enforces ONE active token per patient per dept |
| `queue_events` | Token lifecycle events (called/consulting/completed/...) |
| `appointment_qr_tokens` | SHA-256 hash of single-use QR token + expiry/used/revoked |
| `patient_followups` | Chronic follow-up scheduling |
| `audit_logs` | Immutable audit trail (user, action, entity, IP) |
| `notification_delivery_logs` | Delivery status for email/SMS per message |

## Migrations
```
migrations/001_smart_hospital_core.sql   # security columns + smart tables + departments + rules
migrations/002_routing_runtime.sql       # appointment status enum + checkin token/priority + followup index
python migrations/run_migrations.py      # apply all .sql + seed doctor bcrypt passwords
```
All statements are idempotent.

## Integrity rules
- `patients.phone` and `patients.email` UNIQUE.
- `queue_tokens` UNIQUE `(patient_id, department_id, is_active)` prevents a second active token for the same patient+department.
- Routing/queue critical writes are immediate-commit; the app performs an app-level duplicate-checkin guard *plus* the DB guard.
- FKs use `ON DELETE CASCADE` on patients (legacy). A retention/soft-delete policy is planned — do not rely on cascade for retention.

## Backup & restore
```
# Backup
mysqldump -u root --add-drop-table --routines --single-transaction hospital_management > backup.sql
# Restore
mysql -u root < backup.sql
```
Existing backups: `database_backups/hospital_management_2026-11-04.sql`
