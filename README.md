# LabTrack — Laboratory Sample Management System

> **Course:** Software Engineering and Design Patterns — ZHAW MSc Life Sciences  
> **Stack:** Python 3.11+ · Flask · SQLite / SQLAlchemy · pytest  
> **Stages completed:** 1 – 10 (100 points)

---

## Project Overview

LabTrack is a web-based system for registering and tracking biological laboratory samples through their full lifecycle — from collection through processing, storage, and final disposal or consumption. It replaces error-prone spreadsheet tracking with a structured, role-aware, database-backed application.

---

## Repository Structure

```
labtrack/
├── app/                         # Stage 6 — Presentation layer (Flask)
│   ├── app.py                   # Application factory + Blueprint registration
│   └── routes/
│       ├── auth_routes.py       # POST /api/auth/login|logout, GET /me
│       ├── sample_routes.py     # Full CRUD + CSV import/export
│       └── user_routes.py       # Admin-only user management
│
├── database/                    # Stage 7 — Data layer (SQLAlchemy ORM)
│   ├── models.py                # UserModel, SampleModel, AuditEntryModel
│   └── db.py                    # Engine, session factory, init_db()
│
├── models/                      # Stage 3 — Domain model classes
│   ├── user.py                  # User (abstract) + 4 role subclasses
│   └── sample.py                # Sample + AuditEntry + SampleStatus enum
│
├── patterns/                    # Stage 5 — Design patterns
│   ├── user_factory.py          # Factory: role string → User subclass
│   ├── singleton_meta.py        # Singleton metaclass + wired repositories
│   ├── search_strategy.py       # Strategy: 5 filter algorithms + context
│   └── csv_adapter.py           # Adapter: CSV → SampleService interface
│
├── repositories/                # Stage 3 — Data access objects
│   ├── sample_repository.py     # CRUD + filter queries for Sample
│   └── user_repository.py       # CRUD + lookup for User
│
├── services/                    # Stage 3 — Application layer
│   └── sample_service.py        # register_sample, update_status, list_samples
│
├── tests/                       # Stages 3, 5, 10 — Test suite (85 tests)
│   ├── conftest.py              # Shared fixtures (clients, DB reset)
│   ├── test_models.py           # 13 unit tests (Stage 3)
│   ├── test_patterns.py         # 37 unit tests (Stage 5)
│   ├── test_routes.py           # 30 integration tests (Stage 10)
│   └── test_system.py           # 5 system scenario tests (Stage 10)
│
├── ML_EVALUATION.md             # Stage 8 — ML decision log
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Architecture

**Combined Layered + Client-Server** (Stage 6):

```
Browser ──HTTP/HTTPS──► Flask server
                         ├── Presentation layer  (app/routes/)
                         ├── Application layer   (services/, patterns/)
                         └── Data layer          (repositories/, database/)
                                  │
                                  └──SQL/ORM──► SQLite DB
```

---

## Design Patterns Applied (Stage 5)

| Pattern | Category | Applied to |
|---|---|---|
| Factory | Creational | `UserFactory` — role string → correct User subclass |
| Singleton | Creational | `SampleRepository`, `UserRepository` — single shared instance |
| Strategy | Behavioral | `SearchStrategy` hierarchy — swappable filter algorithms |
| Adapter | Structural | `CsvImportAdapter` — CSV format → SampleService interface |

---

## Database Schema (Stage 7)

Three tables: **USER** → **SAMPLE** (1:M) and **SAMPLE** → **AUDIT_ENTRY** (1:M), with **USER** → **AUDIT_ENTRY** (1:M) for change attribution.

---

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Start the development server
python app/app.py
# → http://localhost:5000
```

---

## Running the Tests

```bash
# Run all 85 tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=app --cov=models --cov=patterns --cov=services --cov-report=term-missing
```

**Test breakdown:**
- 13 unit tests — domain model classes (`test_models.py`)
- 37 unit tests — design pattern implementations (`test_patterns.py`)
- 30 integration tests — Flask API endpoints (`test_routes.py`)
- 5 system scenarios — end-to-end workflows (`test_system.py`)

---

## API Endpoints

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/api/auth/login` | Authenticate, start session | None |
| POST | `/api/auth/logout` | Destroy session | Session |
| GET | `/api/auth/me` | Current user profile | Session |
| GET | `/api/samples/` | List samples (filterable) | Session |
| POST | `/api/samples/` | Register new sample | Researcher/Admin |
| GET | `/api/samples/<id>` | Sample detail + audit log | Session |
| PUT | `/api/samples/<id>/status` | Update lifecycle status | Researcher/Tech/Admin |
| POST | `/api/samples/import` | Bulk CSV import | Researcher/Admin |
| GET | `/api/samples/export` | Export as CSV | Session |
| GET | `/api/users/` | List users | Admin |
| POST | `/api/users/` | Create user account | Admin |
| PUT | `/api/users/<id>` | Update user | Admin |
| DELETE | `/api/users/<id>` | Deactivate user | Admin |

---

## ML Decision (Stage 8)

ML integration was evaluated and **not included**. See `ML_EVALUATION.md` for the full assessment of 5 candidate applications and the 5-point justification.

---

## Version History

| Tag | Stage | Description |
|---|---|---|
| v1.0 | Stage 1 | Project definition |
| v3.0 | Stage 3 | Core classes + unit tests |
| v5.0 | Stage 5 | Design patterns |
| v6.0 | Stage 6 | Flask architecture |
| v7.0 | Stage 7 | SQLAlchemy models |
| v10.0 | Stage 10 | QA — final submission |
