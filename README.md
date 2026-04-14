# LabTrack — Laboratory Sample Management System

> **Course:** Software Engineering and Design Patterns — ZHAW MSc Life Sciences  
> **Stage:** 3 — Core Classes and Responsibilities  
> **Stack:** Python 3.11+ · Flask (Stage 6+) · SQLite/SQLAlchemy (Stage 7+)

---

## Project Overview

LabTrack is a web-based system for registering and tracking biological laboratory samples across their full lifecycle — from collection through processing, storage, and final disposal or consumption. It replaces error-prone spreadsheet tracking with a structured, role-aware, database-backed application.

---

## Repository Structure

```
labtrack/
├── models/
│   ├── user.py              # User base class + role subclasses (Researcher, Technician, Admin, Viewer)
│   └── sample.py            # Sample entity + AuditEntry (lifecycle tracking)
├── repositories/
│   ├── sample_repository.py # CRUD and query operations for Sample objects
│   └── user_repository.py   # CRUD and lookup for User objects
├── services/
│   └── sample_service.py    # Business logic: register samples, update status, list/filter
├── tests/
│   └── test_models.py       # Unit and integration tests
└── README.md
```

> **Note:** The Flask app entry point (`app.py`) and database configuration will be added in Stage 6 (architecture) and Stage 7 (data storage).

---

## Class Overview

### `models/user.py`

| Class | Type | Description |
|---|---|---|
| `User` | Abstract base | Common user attributes and abstract permission methods |
| `Researcher` | Concrete (inherits `User`) | Can register samples and import CSV |
| `LabTechnician` | Concrete (inherits `User`) | Can update sample status only |
| `Administrator` | Concrete (inherits `User`) | Full access including user management |
| `Viewer` | Concrete (inherits `User`) | Read-only, no write permissions |

**Key attributes:** `_user_id`, `_username`, `_email`, `_password_hash`, `_role`, `_is_active`  
**Key methods:** `can_register_sample()`, `can_update_status()`, `can_manage_users()`, `can_import_csv()` *(all abstract → polymorphism)*

---

### `models/sample.py`

| Class | Type | Description |
|---|---|---|
| `SampleStatus` | Enum | Lifecycle states: Collected → Processing → Stored → Consumed/Discarded |
| `Sample` | Concrete | Central domain entity; enforces lifecycle transitions |
| `AuditEntry` | Concrete (composed by `Sample`) | Immutable record of one status change |

**Key attributes:** `_sample_id`, `_sample_type`, `_source_organism`, `_status`, `_audit_log`  
**Key methods:** `update_status(new_status, changed_by_id)` — validates transitions and appends to audit log

---

### `repositories/`

| Class | Responsibility |
|---|---|
| `SampleRepository` | CRUD + filter queries for `Sample` objects (in-memory → SQLAlchemy in Stage 7) |
| `UserRepository` | CRUD + lookup by username or role for `User` objects |

---

### `services/sample_service.py`

| Class | Responsibility |
|---|---|
| `SampleService` | Orchestrates `register_sample()`, `update_sample_status()`, `list_samples()` — checks permissions before delegating to repositories |

---

## Class Relationships

```
User (abstract)
├── Researcher        ──inheritance──►  User
├── LabTechnician     ──inheritance──►  User
├── Administrator     ──inheritance──►  User
└── Viewer            ──inheritance──►  User

Sample ──composition──► AuditEntry   (AuditEntry cannot exist without Sample)

SampleRepository ──aggregation──► Sample   (manages, does not own)
UserRepository   ──aggregation──► User

SampleService ──dependency──► SampleRepository
SampleService ──dependency──► UserRepository
```

---

## OOD Principles Applied

| Principle | Where |
|---|---|
| **Encapsulation** | All attributes are private (`_name`); access via getters/setters with validation |
| **Inheritance** | `Researcher`, `LabTechnician`, `Administrator`, `Viewer` all extend `User` |
| **Polymorphism** | Permission methods (`can_register_sample()` etc.) are abstract in `User` and overridden in each subclass |
| **Abstraction** | `User` is an ABC — it cannot be instantiated directly |
| **Composition** | `Sample` owns its `AuditEntry` list; entries are created internally and never exposed directly |

---

## Running the Tests

```bash
# Install pytest if needed
pip install pytest

# From the project root
pytest labtrack/tests/ -v
```

---

## Upcoming Stages

| Stage | What will be added |
|---|---|
| 4 | UML diagrams (Use Case, Class, Sequence, Activity) added to SRS |
| 5 | Design patterns applied: Factory (UserFactory), Singleton (repositories), Strategy (search), Adapter (CSV import) |
| 6 | Flask app entry point, REST API routes, architecture diagram |
| 7 | SQLAlchemy ORM models, ER diagram, database migration |
| 8 | ML integration evaluation |
| 9 | Frontend templates and navigation flow |
| 10 | QA strategy, unit/integration test suite, maintenance plan |
