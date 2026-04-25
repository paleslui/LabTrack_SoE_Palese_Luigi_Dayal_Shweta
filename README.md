# LabTrack — Laboratory Sample Management System

> **Course:** Software Engineering and Design Patterns — ZHAW MSc Life Sciences  
> **Team:** Palese Luigi · Dayal Shweta  
> **Stack:** Python 3.11+ · Flask · SQLite/SQLAlchemy · pytest  
> **Stages completed:** 1–10 (100 points) + post-submission enhancements (v11.0)  
> **GitHub:** https://github.com/paleslui/LabTrack_SoE_Palese_Luigi_Dayal_Shweta

---

## What is LabTrack?

LabTrack is a browser-based Laboratory Information Management System (LIMS) for tracking biological samples — blood, tissue, DNA, RNA, plasma — through their full lifecycle from collection to consumption or disposal.

It replaces spreadsheets and handwritten logs with a structured, role-aware, database-backed application that enforces lifecycle rules and maintains an immutable audit trail.

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/paleslui/LabTrack_SoE_Palese_Luigi_Dayal_Shweta.git
cd LabTrack_SoE_Palese_Luigi_Dayal_Shweta
pip3 install -r requirements.txt

# 2. Configure environment
cp .env.example .env          # edit SECRET_KEY and optional SMTP settings

# 3. Run
python3 run.py                # → http://localhost:5001

# 4. Run with HTTPS (public URL via Cloudflare tunnel)
./start_https.sh              # → https://xxx.trycloudflare.com
```

**Default accounts** (seeded automatically on first run):

| Username | Password | Role |
|---|---|---|
| alice | alice123 | Researcher |
| bob | bob123 | Lab Technician |
| carol | carol123 | Administrator |
| dave | dave123 | Viewer |

---

## Architecture

LabTrack implements a **Three-Tier Layered Architecture** combined with a **Client-Server** topology:

```
Browser (HTML/CSS/JS)
        │  HTTP/HTTPS
        ▼
┌─────────────────────────────────┐
│  Presentation Layer             │  app/routes/  (Flask Blueprints)
│  auth_routes · sample_routes   │
│  user_routes · project_routes  │
├─────────────────────────────────┤
│  Application Layer              │  services/ · patterns/
│  SampleService · UserFactory   │
│  Strategy · Adapter · Singleton│
├─────────────────────────────────┤
│  Data Layer                     │  repositories/ · database/
│  SampleRepository               │
│  UserRepository                 │
└─────────────────────────────────┘
        │  SQLAlchemy ORM
        ▼
   SQLite (labtrack.db)
```

---

## Design Patterns (Stage 5)

| Pattern | Category | File | Purpose |
|---|---|---|---|
| **Factory** | Creational | `patterns/user_factory.py` | Instantiates correct User subclass from role string |
| **Singleton** | Creational | `patterns/singleton_meta.py` | Ensures one shared repository instance |
| **Strategy** | Behavioural | `patterns/search_strategy.py` | Pluggable search filters (type, status, location, date, user) |
| **Adapter** | Structural | `patterns/csv_adapter.py` | Translates CSV rows into SampleService interface |

---

## Repository Structure

```
LabTrack/
├── app/
│   ├── app.py                   # Flask factory — security headers, CSRF, rate limiting
│   ├── routes/
│   │   ├── auth_routes.py       # Login/logout, account lockout, profile editing
│   │   ├── sample_routes.py     # Full sample CRUD + bulk ops + labels + attachments
│   │   ├── user_routes.py       # User management + activity log
│   │   └── project_routes.py   # Project/experiment grouping
│   ├── static/uploads/          # File attachments (per sample_id folder)
│   └── templates/
│       └── index.html           # Single-file frontend (vanilla JS, DE/EN toggle)
│
├── database/
│   ├── models.py                # 6 SQLAlchemy ORM tables
│   └── db.py                    # Engine, sessions, migrations, seeding, email helper
│
├── models/
│   ├── user.py                  # User (ABC) + Researcher, LabTechnician, Administrator, Viewer
│   └── sample.py                # Sample + AuditEntry + SampleStatus + ALLOWED_TRANSITIONS
│
├── patterns/
│   ├── user_factory.py
│   ├── singleton_meta.py
│   ├── search_strategy.py
│   └── csv_adapter.py
│
├── repositories/
│   ├── sample_repository.py     # SQLAlchemy-backed CRUD for Sample
│   └── user_repository.py       # SQLAlchemy-backed CRUD for User
│
├── services/
│   └── sample_service.py        # Business logic: register_sample, update_sample_status
│
├── tests/
│   ├── conftest.py              # In-memory SQLite fixtures, 4 role clients
│   ├── test_models.py           # Domain model unit tests
│   ├── test_patterns.py         # Pattern unit tests
│   ├── test_routes.py           # Integration tests (API endpoints)
│   └── test_system.py           # System scenario tests
│
├── docs/
│   ├── USER_GUIDE.md            # End-user guide (lab staff)
│   └── DEVELOPER.md             # Developer setup, testing, deployment
│
├── ML_EVALUATION.md             # Stage 8 — ML integration assessment
├── start_https.sh               # Launch Flask + Cloudflare HTTPS tunnel
├── run.py                       # Entry point (port 5001)
├── requirements.txt
├── .env.example                 # Environment variable template
└── .gitignore
```

---

## Features

### Core (Stages 1–10)
- **RBAC** — 4 roles: Researcher, Lab Technician, Administrator, Viewer
- **Sample lifecycle** — Collected → Processing → Stored → Consumed/Discarded (all transitions reversible)
- **Immutable audit log** — every status change recorded with user and timestamp
- **Multi-field search** — filter by type, status, location, date range, submitter, project
- **CSV import/export** — bulk import with duplicate detection and per-row error reporting
- **4 UML diagrams** — use case, class, sequence, activity

### Post-submission enhancements (v11.0)
- **Expiry tracking** — colour-coded alerts (red/amber/green) on list and dashboard
- **Quantity tracking** — volume/mass/count with units
- **4-level location hierarchy** — building → room → equipment → position
- **Sample lineage** — parent/child relationships between samples
- **QR code labels** — encode a live URL; scanned label always shows current state
- **Bulk operations** — status update, delete, CSV export, label printing on selection
- **Project grouping** — tag samples to experiments or studies
- **File attachments** — PDFs, images, documents per sample
- **Sample reservation** — soft lock with expiry and note
- **User activity log** — system-level audit (admin only)
- **German/English UI toggle** — localStorage persistent
- **Email notifications** — expiry alerts via SMTP (configurable)
- **Full sample editing** — all fields except sample_id editable after registration

### Security (NFR-14 to NFR-20)
- Account lockout after 5 failed logins (15-minute lock)
- CSRF protection (double-submit cookie, `X-CSRF-Token` header)
- XSS escaping on all user-supplied DOM insertions
- MIME type validation on file uploads
- Security headers on every response (CSP, X-Frame-Options, etc.)
- Secret key loaded from `.env` — never hardcoded
- HTTPS via Cloudflare Tunnel (`./start_https.sh`)

---

## Test Suite

```bash
python3 -m pytest tests/ -v
```

| Layer | File | Count |
|---|---|---|
| Unit | test_models.py + test_patterns.py | 50 tests |
| Integration | test_routes.py | 30 tests |
| System | test_system.py | 38 tests |
| **Total** | | **118 tests** |

All tests use an in-memory SQLite database — no side effects on `labtrack.db`.

---

## API Summary

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | /api/auth/login | Authenticate | None |
| GET | /api/samples/ | List samples (filterable, paginated) | Session |
| POST | /api/samples/ | Register new sample | Researcher/Admin |
| GET | /api/samples/`<id>` | Sample detail + audit log | Session |
| PUT | /api/samples/`<id>` | Edit sample fields | Res/Tech/Admin |
| PUT | /api/samples/`<id>`/status | Update lifecycle status | Res/Tech/Admin |
| DELETE | /api/samples/`<id>` | Delete sample | Res/Tech/Admin |
| GET | /api/samples/`<id>`/label | Download QR label PNG | Session |
| GET | /view/`<id>` | Public live sample view (QR scan target) | None |
| GET | /api/projects/ | List projects | Session |
| GET | /api/users/activity-log | System activity log | Admin |

Full API: see `docs/DEVELOPER.md`

---

## Course Stage Summary

| Stage | Topic | Points |
|---|---|---|
| 1 | Project definition, target users, tech stack | 5 |
| 2 | FR-01–FR-19, NFR-01–NFR-13 | 10 |
| 3 | Core classes — models, repositories, services | 10 |
| 4 | UML diagrams (use case, class, sequence, activity) | 10 |
| 5 | Design patterns (Factory, Singleton, Strategy, Adapter) | 10 |
| 6 | Architecture (layered + client-server, REST API) | 15 |
| 7 | Data storage (SQLAlchemy, ER diagram) | 10 |
| 8 | ML evaluation (5 candidates rejected) | 10 |
| 9 | UI design (wireframes, navigation flow) | 10 |
| 10 | Quality assurance (118 tests, version control) | 10 |
| **Total** | | **100** |

---

> See `docs/USER_GUIDE.md` for end-user instructions.  
> See `docs/DEVELOPER.md` for setup, testing, and deployment details.
