# API DOCUMENTATION

Base: `http://localhost:5000` · Auth: Flask session cookies (HttpOnly, SameSite=Lax; Secure in prod).
JSON responses follow `{ "success": bool, "message": "..." , ... }`.
CSRF: state-changing endpoints under `/api/` require `"csrf_token"` in the JSON body
(obtained from page JS `var CSRF = {{ csrf_token|tojson }};`).

## Authentication
| Method | Route | Body | Notes |
|---|---|---|---|
| POST | `/register` | form: name, age, phone, email, password?, face_data?, face_image? | Creates patient (+ optional password/face) |
| POST | `/manual-login` | patient_id or email, password | bcrypt required; rate-limited |
| POST | `/face-login` | image (base64) | Face recognition login; session regenerated |
| POST | `/doctor-login` | doctor_id, password | per-doctor bcrypt; rate-limited |
| POST | `/admin-login` | username, password | rate-limited |
| POST | `/logout` `/doctor-logout` `/admin-logout` | — | session cleared |

## Patients / appointments / records
| Method | Route | Access |
|---|---|---|
| GET | `/api/doctors` | public |
| GET | `/api/patient/<id>` | owner patient or staff → else 403 |
| GET | `/api/records/<id>` | doctor only |
| GET | `/api/check-session` | public (own session) |
| POST | `/book-appointment` | patient (slot-conflict guarded) |
| POST | `/update-appointment-status` | doctor (validated transitions + rejection reason + QR issue) |
| GET | `/find-patient`, `/api/checkin/search` | staff |

## Check-in / QR
| Method | Route | Access | Notes |
|---|---|---|---|
| POST | `/api/checkin` | staff + CSRF | patient_id (+ method, appointment_id, walkin dept, clinical_priority, qr_token) → routing + token |
| POST | `/api/checkin/face` | staff + CSRF | base64 image → recognize → check-in |
| GET | `/api/checkin/status/<pid>` | owner/staff | |
| POST | `/api/qr/generate/<appt>` | owner/staff | issues single-use token |
| POST | `/api/qr/verify` | staff | consumes token → appointment |
| GET | `/appointment/<id>/qr` | owner/staff | QR page (fresh single-use QR) |

## Queue
| Method | Route | Access |
|---|---|---|
| GET | `/api/queue/<dept>` | staff — list + stats + est wait |
| POST | `/api/queue/<dept>/call-next` | staff + CSRF |
| POST | `/api/queue/token/<id>/status` | staff + CSRF (waiting/called/consulting/completed/skipped/cancelled) |
| GET | `/api/my-queue` | patient — own token + position + est wait |

## Admin
| Method | Route |
|---|---|
| POST | `/api/admin/departments` , `/…/<id>/update` , `/…/<id>/status` , `/…/<id>/doctors` , `/api/admin/rules` | all admin + CSRF |
| GET | `/api/analytics/summary` , `/department-workload` , `/checks` , `/appointments` , `/calls` | admin |
| GET | `/api/audit/logs` , `/api/notifications/logs` | admin |

## Other
- `POST /chatbot` , `POST /chatbot/voice` — multilingual AI assistant (+Whisper STT)
- `POST /get-selfcare-suggestions` — self-care tips
- `GET /api/realtime/events?after=<seq>&department_id=<id>` — polling event bus (staff)
