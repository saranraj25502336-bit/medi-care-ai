# TESTING REPORT

## Automated test suite — `tests/test_smart_checkin.py`
Run: `python tests/test_smart_checkin.py` (also pytest-compatible)

| Test | Covers | Result |
|---|---|---|
| `test_rule_engine_routes_approved` | RULE 001 — approved appointment routes to doctor's dept | ✅ PASS |
| `test_rule_engine_blocks_rejected` | RULE 002 — cancelled/rejected blocks check-in | ✅ PASS |
| `test_rule_engine_walkin` | RULE 003 — no appointment offers walk-in flow | ✅ PASS |
| `test_rule_engine_duplicate` | RULE 008 — active check-in returns existing token | ✅ PASS |
| `test_rule_engine_urgent_priority` | RULE 007 — urgent clinical priority queue | ✅ PASS |
| `test_full_checkin_flow` | **End-to-end:** register → book → approve(+QR) → QR single-use → staff check-in → token (CARD-001) → duplicate blocked → queue list → call-next → consulting → completed → follow-up created | ✅ PASS |
| `test_unauthorized_access` | IDOR / staff / admin boundaries (403s + redirect) | ✅ PASS |

**Result: 7 / 7 PASS (0 failed)** · Test data is cleaned up after each run.

## Manual / live verification performed during development
- PHP lint: `api/chat.php`, `config.php` — no syntax errors.
- Python syntax (AST) on `app.py`, `database.py`, `chatbot.py`, all `modules/*`, `tests/*`.
- Migrations 001 + 002: idempotent, **33 statements / 0 failed** on final run.
- Live Groq chatbot: short, **bold-key-answer** replies in English and Hindi (+ earlier Tamil/Spanish).
- Security: unauth `/api/patient/<id>` → 403; unauth face-search → 403; wrong doctor password rejected;
  passwordless manual login rejected; `/patient/<id>` no longer hijacks sessions.
- All new pages render 200 under the right role: `/reception`, `/department/<id>`, `/checkin`,
  `/my-queue`, `/appointment/<id>/qr`, `/admin/departments`, `/admin/analytics`.

## Known/planned test gaps (next sprint)
- Face recognition FAR/FRR calibration on real hardware (needs camera).
- SMS/email provider failure injection tests (needs SMTP/Fast2SMS test creds).
- Concurrent check-in stress test (row-lock level).
- CSRF negative tests across every mutating endpoint.
