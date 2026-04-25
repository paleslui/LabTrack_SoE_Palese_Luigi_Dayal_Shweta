# LabTrack — Developer Guide

> Technical setup, testing, architecture details, and deployment.  
> For end-user instructions see [USER_GUIDE.md](USER_GUIDE.md).

---

## Requirements

- Python 3.11+
- pip3
- Git

No database server, no Docker, no Node.js required for running the app.

---

## Setup

```bash
# Clone
git clone https://github.com/paleslui/LabTrack_SoE_Palese_Luigi_Dayal_Shweta.git
cd LabTrack_SoE_Palese_Luigi_Dayal_Shweta

# Install dependencies
pip3 install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env — set a strong SECRET_KEY (required)
# Optionally configure SMTP for email notifications
```

### `.env` file

```env
# Required — generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-random-secret-key-here

# Optional — SMTP for expiry email notifications
MAIL_ENABLED=False
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your-app-password   # Gmail App Password, not login password
```

---

## Running

### Local network (HTTP)
```bash
python3 run.py
# → http://localhost:5001
# → http://<your-local-ip>:5001  (accessible on same WiFi)
```

### With HTTPS (public URL via Cloudflare Tunnel)
```bash
./start_https.sh
# Flask starts on :5001
# Cloudflare tunnel provides https://xxx.trycloudflare.com
# Share the trycloudflare.com URL — it works from anywhere
```

The tunnel URL changes each session. For a permanent URL, create a free Cloudflare account and use `cloudflared tunnel`.

---

## Default accounts

Seeded automatically on first run (into an empty database):

| Username | Password | Role |
|---|---|---|
| alice | alice123 | Researcher |
| bob | bob123 | Lab Technician |
| carol | carol123 | Administrator |
| dave | dave123 | Viewer |

Change these passwords immediately in a real deployment.

---

## Testing

```bash
# Full test suite
python3 -m pytest tests/ -v

# Quick pass/fail
python3 -m pytest tests/ -q

# Single layer
python3 -m pytest tests/test_models.py tests/test_patterns.py -v   # unit only
python3 -m pytest tests/test_routes.py -v                          # integration only
python3 -m pytest tests/test_system.py -v                          # system only
```

**All tests use in-memory SQLite** — they never touch `labtrack.db`.

| Layer | File | Tests | What is verified |
|---|---|---|---|
| Unit | test_models.py | 14 | Sample domain model, lifecycle transitions, audit log |
| Unit | test_patterns.py | 36 | Factory, Singleton, Strategy, Adapter patterns |
| Integration | test_routes.py | 30 | All API endpoints, RBAC, error codes |
| System | test_system.py | 38 | Complete user workflows, permission matrix, CSV import |
| **Total** | | **118** | |

Expected output: `118 passed`

---

## Project structure

```
app/
  app.py                  Flask factory. Registers blueprints, sets up:
                          - Rate limiting (Flask-Limiter, 5 login/min per IP)
                          - CSRF double-submit cookie verification
                          - Security headers (CSP, X-Frame-Options, etc.)
                          - Session timeout (8 hours)
                          - Calls init_db(), migrate_db(), seed_default_users()
  routes/
    auth_routes.py        Login (with account lockout), logout, /me, profile edit
    sample_routes.py      Sample CRUD, bulk ops, QR labels, attachments, reservation
    user_routes.py        User management, activity log, test email
    project_routes.py     Project CRUD

database/
  models.py               6 SQLAlchemy ORM models (see DB schema below)
  db.py                   Engine, db_session(), init_db(), migrate_db(),
                          seed_default_users(), seed_demo_samples(),
                          log_activity(), send_email()

models/                   Domain model classes (pure Python, no SQLAlchemy)
  user.py                 User (ABC) + Researcher, LabTechnician,
                          Administrator, Viewer subclasses
  sample.py               Sample, AuditEntry, SampleStatus enum,
                          ALLOWED_TRANSITIONS dict

patterns/
  user_factory.py         Factory pattern — role string → User subclass
  singleton_meta.py       Singleton metaclass (applied to repositories)
  search_strategy.py      Strategy pattern — 5 search filter algorithms
  csv_adapter.py          Adapter pattern — CSV rows → SampleService interface

repositories/             SQLAlchemy-backed data access objects
  sample_repository.py    SampleRepository (CRUD + filter queries)
  user_repository.py      UserRepository (CRUD + lookup)

services/
  sample_service.py       SampleService — orchestrates register_sample and
                          update_sample_status with RBAC permission checks

tests/
  conftest.py             Session-scoped in-memory DB, autouse reset_db fixture,
                          4 role-specific test clients, shared test data constants
```

---

## Database schema

6 tables. `migrate_db()` runs at startup and adds missing columns to existing databases — no data loss on upgrade.

### samples
| Column | Type | Notes |
|---|---|---|
| sample_id | VARCHAR(20) PK | LT-YYYY-NNNN format |
| sample_type | VARCHAR(100) | |
| source_organism | VARCHAR(200) | |
| collection_date | DATE | |
| storage_location | VARCHAR(200) | Legacy free-text field |
| notes | TEXT | |
| status | VARCHAR(50) | Collected/Processing/Stored/Consumed/Discarded |
| created_by | INTEGER FK→users | |
| created_at / updated_at | DATETIME | |
| expiry_date | DATE | Optional |
| quantity | FLOAT | Optional |
| quantity_unit | VARCHAR(20) | ml/ul/mg/ug/ng/units |
| location_building | VARCHAR(100) | Level 1 of structured location |
| location_room | VARCHAR(100) | Level 2 |
| location_equipment | VARCHAR(100) | Level 3 |
| location_position | VARCHAR(50) | Level 4 |
| parent_sample_id | VARCHAR(20) FK→samples | Lineage |
| project_id | INTEGER FK→projects | |
| reserved_by | INTEGER FK→users | |
| reserved_until | DATETIME | |
| reservation_note | VARCHAR(200) | |

### users
| Column | Type | Notes |
|---|---|---|
| user_id | INTEGER PK | |
| username | VARCHAR(100) UNIQUE | |
| email | VARCHAR(200) | |
| password_hash | TEXT | bcrypt only |
| role | VARCHAR(20) | researcher/technician/admin/viewer |
| is_active | BOOLEAN | False = soft-deleted |
| created_at | DATETIME | |
| failed_login_attempts | INTEGER | Resets on success |
| locked_until | DATETIME | NULL if not locked |

### audit_entries
Append-only. One row per status change on any sample.

### projects
`project_id, name, description, created_by, created_at`

### attachments
`attachment_id, sample_id, filename, original_name, file_size, mime_type, uploaded_by, uploaded_at`

Files stored in `app/static/uploads/<sample_id>/`.

### activity_log
`log_id, user_id, username (denormalised), action, detail, ip_address, timestamp`

---

## Full REST API reference

### Auth
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | /api/auth/login | None | Authenticate. Returns role, user_id, username |
| POST | /api/auth/logout | Session | Destroy session |
| GET | /api/auth/me | Session | Current user info |
| PUT | /api/auth/profile | Session | Update own email/password |

### Samples
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /api/samples/ | Session | List (filter: type, status, location, date_from, date_to, submitted_by, project_id, reserved_only) |
| POST | /api/samples/ | Res/Admin | Register new sample |
| GET | /api/samples/`<id>` | Session | Detail + audit log |
| PUT | /api/samples/`<id>` | Res/Tech/Admin | Edit all fields except sample_id |
| DELETE | /api/samples/`<id>` | Res/Tech/Admin | Permanently delete |
| PUT | /api/samples/`<id>`/status | Res/Tech/Admin | Update lifecycle status |
| PATCH | /api/samples/`<id>`/notes | Res/Tech/Admin | Update notes only |
| GET | /api/samples/`<id>`/children | Session | List derived samples |
| GET | /api/samples/export | Session | Export CSV (respects active filters) |
| GET | /api/samples/audit-export | Session | Export audit CSV (?sample_id=X or all) |
| POST | /api/samples/import | Res/Admin | Bulk CSV import (multipart, field: file) |
| PUT | /api/samples/bulk-status | Res/Tech/Admin | { sample_ids, status } |
| POST | /api/samples/bulk-export | Session | { sample_ids } → CSV |
| DELETE | /api/samples/bulk-delete | Res/Tech/Admin | { sample_ids } |
| GET | /api/samples/`<id>`/label | Session | PNG label with live-URL QR code |
| POST | /api/samples/bulk-labels | Session | { sample_ids } → PNG label sheet |
| POST | /api/samples/`<id>`/reserve | Res/Tech/Admin | { until, note } |
| DELETE | /api/samples/`<id>`/reserve | Session | Cancel reservation (reserver or admin) |
| POST | /api/samples/`<id>`/attachments | Res/Tech/Admin | Upload file (multipart, field: file) |
| GET | /api/samples/`<id>`/attachments | Session | List attachments |
| GET | /api/samples/`<id>`/attachments/`<n>` | Session | Download attachment |
| DELETE | /api/samples/`<id>`/attachments/`<n>` | Res/Tech/Admin | Delete attachment |

### Projects
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /api/projects/ | Session | List all projects |
| POST | /api/projects/ | Res/Admin | Create project { name, description } |
| DELETE | /api/projects/`<id>` | Admin | Delete project |

### Users
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /api/users/ | Admin | List all users |
| POST | /api/users/ | Admin | Create user { username, email, password, role } |
| GET | /api/users/`<id>` | Admin | Get user |
| PUT | /api/users/`<id>` | Admin | Update { email, role, is_active } |
| DELETE | /api/users/`<id>` | Admin | Deactivate (soft-delete) |
| GET | /api/users/activity-log | Admin | System activity log (?limit, ?username, ?action) |
| GET | /api/users/activity-log/export | Admin | Export activity log as CSV |
| POST | /api/users/send-test-email | Admin | Send SMTP test email to self |

### Public (no login)
| Method | Endpoint | Description |
|---|---|---|
| GET | /view/`<id>` | Live sample view — linked from QR labels. Auto-refreshes every 60s |

---

## Security

| Measure | NFR | Implementation |
|---|---|---|
| bcrypt password hashing | NFR-02 | Work factor ≥12. Plaintext never stored |
| Account lockout | NFR-14 | 5 failures → 15 min lock. `failed_login_attempts` + `locked_until` on users |
| Rate limiting | NFR-03 | Flask-Limiter: 5 login/min per IP, 300 general/min |
| Session timeout | NFR-03 | `PERMANENT_SESSION_LIFETIME = 8h` |
| Secure cookies | NFR-03 | HttpOnly, SameSite=Lax, Secure (when HTTPS) |
| Secret key | NFR-19 | From `.env` via python-dotenv. Never hardcoded |
| CSRF | NFR-15 | Double-submit cookie (`csrf_token`). `X-CSRF-Token` header on all mutations |
| XSS | NFR-17 | `esc()` helper escapes all user data before `innerHTML` |
| MIME validation | NFR-16 | File bytes checked for ELF, PE, PHP, shell, HTML signatures |
| Security headers | NFR-18 | `X-Frame-Options`, `X-Content-Type-Options`, `CSP`, `Referrer-Policy`, `Permissions-Policy` |
| HTTPS | NFR-20 | Cloudflare Tunnel via `./start_https.sh` |
| SQL injection | NFR-07 | SQLAlchemy ORM only — no raw SQL |

---

## Adding a new feature

1. **DB column:** Add to `database/models.py`. Add migration entry in `database/db.py` `migrate_db()`.
2. **Domain model:** Add field to `models/sample.py` or `models/user.py` — `__init__`, getter, `to_dict()`.
3. **Repository:** Add to `_to_domain()`, `create()`, `update()` in `repositories/sample_repository.py`.
4. **Service:** Add parameter to `services/sample_service.py` `register_sample()` if needed.
5. **Route:** Add endpoint or parameter in `app/routes/sample_routes.py`.
6. **Frontend:** Update `app/templates/index.html` — HTML + JS.
7. **Test:** Add integration test in `tests/test_routes.py`.

---

## Email notifications setup (optional)

Set in `.env`:
```env
MAIL_ENABLED=True
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your-16-char-app-password
```

For Gmail, create an App Password: Google Account → Security → 2-Step Verification → App Passwords.

The scheduler checks for expiring samples every 24 hours and emails the registering researcher:
- **7 days before expiry** — warning
- **On the expiry day** — alert

Test it: Admin panel → "Send test email to myself".

---

## Swapping to PostgreSQL

Change one line in `database/db.py`:
```python
# Before
DATABASE_URI = os.environ.get("DATABASE_URI", "sqlite:///labtrack.db")

# After
DATABASE_URI = os.environ.get("DATABASE_URI", "postgresql://user:pass@localhost/labtrack")
```

Then install: `pip3 install psycopg2-binary`

No application code changes required (NFR-11).

---

## Common issues

**Port 5001 already in use**
```bash
lsof -ti:5001 | xargs kill -9
```

**`labtrack.db` is empty after restart**
The DB persists between restarts. If you see empty data, check that the DB file exists and `init_db()` ran without errors.

**CSRF token error on API call**
The `X-CSRF-Token` header must match the `csrf_token` cookie. In the frontend this is handled automatically by the `api()` function. For external API clients (curl, Postman), first GET any page to receive the cookie, then include it in subsequent requests.

**File upload rejected**
Check the file extension is in the allowed list (pdf, png, jpg, jpeg, gif, doc, docx, xlsx, csv, txt) and the file is under 5MB. Executable files (even renamed) are rejected by MIME validation.
