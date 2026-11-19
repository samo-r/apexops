# ApexOps

> A multi-tenant business management backend — organizations, users, roles, and task assignments with strict per-tenant data isolation.

**Stack:** Python 3.14 · FastAPI · MongoDB · Beanie ODM · JWT (HS256) · bcrypt · pytest

---

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [How It Works](#how-it-works)
4. [Technology Stack](#technology-stack)
5. [Project Structure](#project-structure)
6. [Data Models](#data-models)
7. [API Reference](#api-reference)
8. [Configuration](#configuration)
9. [Installation](#installation)
10. [Running the App](#running-the-app)
11. [Running Tests](#running-tests)
12. [Security](#security)
13. [Future Improvements](#future-improvements)

---

## Overview

ApexOps is a RESTful API backend built around organizational tenancy. Every authenticated user belongs to one organization. Their JWT carries that organization's `org_id`, and every database query is scoped to it — one tenant can never touch another's data.

Roles are named sets of permission strings (e.g. `users:create`, `tasks:assign`). These permissions are embedded in the JWT at login, and each route checks for the specific one it needs before the handler runs.

---

## Key Features

- **Multi-tenant isolation** — all queries are scoped to the JWT's `org_id`
- **JWT authentication** — HS256 tokens with typed, validated claims
- **Permission-based access** — each route enforces a named permission string
- **Salary masking** — salary returns `$•••••` unless the caller holds `salary:read_raw`
- **Fully async** — FastAPI + Motor, non-blocking MongoDB I/O throughout
- **Health probes** — `/health` (liveness) and `/ready` (MongoDB ping)
- **No-DB test suite** — all tests run with mocks, no live MongoDB needed

---

## How It Works

### Request lifecycle

```
Client Request
     │
     ▼
 Bearer token extracted (OAuth2PasswordBearer)
     │
     ▼
 JWT decoded + validated → JWTPayload
 (sub, org_id, role, permissions, exp all required)
     │
     ├─ user not found or inactive → 401
     │
     ▼
 require_permission("resource:action")
     │
     ├─ permission missing → 403
     │
     ▼
 Route handler
     │
     ▼
 DB query scoped to org_id from JWT
     │
     ├─ resource belongs to different org → 404
     │
     ▼
 Response (salary masked if no salary:read_raw)
```

### Tenant isolation

Every user and assignment query applies two filters: the resource ID and the `org_id` from the JWT. A resource that exists but belongs to a different organization returns `404`, not `403` — this prevents one tenant from confirming the existence of another's records.

### Salary masking

The salary field is stored as a `float` in MongoDB but is always serialized as a `str` in API responses. `format_salary()` checks for `salary:read_raw` in the JWT's permission list and returns either `$1,234.56` or `$•••••`. The raw float never reaches Pydantic's serializer.

---

## Technology Stack

| Package | Version |
|---|---|
| FastAPI | 0.141.1 |
| Uvicorn | 0.52.4 |
| Beanie (ODM) | 2.0.0 |
| Motor | 3.7.1 |
| PyMongo | 4.17.0 |
| PyJWT | 2.13.0 |
| passlib\[bcrypt\] | 1.7.4 |
| bcrypt | <5 |
| pydantic-settings | 2.15.0 |
| python-multipart | — |
| pytest | 9.0.2 |

---

## Project Structure

```
apexops/
├── backend/
│   ├── app/
│   │   ├── main.py                  # App factory, lifespan, router mounts
│   │   ├── core/
│   │   │   ├── config.py            # pydantic-settings, SecretStr, lru_cache
│   │   │   └── security.py          # JWT creation, bcrypt hash/verify
│   │   ├── models/
│   │   │   └── models.py            # Beanie documents + MongoDB indexes
│   │   ├── schemas/
│   │   │   ├── auth.py              # JWTPayload, TokenResponse
│   │   │   ├── organizations.py
│   │   │   ├── roles.py
│   │   │   ├── tasks.py
│   │   │   └── users.py             # format_salary(), masked response models
│   │   ├── api/v1/
│   │   │   ├── auth.py
│   │   │   ├── organizations.py
│   │   │   ├── roles.py
│   │   │   ├── tasks.py
│   │   │   ├── users.py
│   │   │   └── helpers.py           # parse_object_id, get_role_or_404, etc.
│   │   └── dependencies/
│   │       └── auth.py              # get_current_token_payload, require_permission
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_rbac_tenant.py
│   │   ├── test_masking.py
│   │   ├── test_models.py
│   │   ├── test_crud.py
│   │   └── test_health.py
│   ├── .env.example
│   └── requirements.txt
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

## Data Models

Four Beanie documents backed by MongoDB. All collection names and indexes are defined in `backend/app/models/models.py`.

```
Organization ──< User >── Role
                 │
                 └──< Assignment (assignee + assigner) >
```

### Organization · `organisations`

| Field | Type | Constraint |
|---|---|---|
| `_id` | ObjectId | |
| `name` | str | unique |
| `location` | str | |
| `email` | str | |

### Role · `roles`

> **Note:** Roles are currently global — not scoped per organization. See [Future Improvements](#future-improvements).

| Field | Type | Constraint |
|---|---|---|
| `_id` | ObjectId | |
| `name` | str | unique |
| `permissions` | List[str] | e.g. `["users:read", "tasks:assign"]` |

### User · `users`

| Field | Type | Constraint |
|---|---|---|
| `_id` | ObjectId | |
| `name` | str | |
| `dob` | str | |
| `email` | str | unique |
| `pwd_hash` | str | bcrypt |
| `salary` | float \| None | always masked in responses |
| `is_active` | bool | false → rejected at login and token check |
| `org_id` | ObjectId | indexed · tenant key |
| `org` | Link[Organization] | |
| `roles` | Link[Role] | |

### Assignment · `assignments`

| Field | Type | Constraint |
|---|---|---|
| `_id` | ObjectId | |
| `task` | str | |
| `status` | str | default `"pending"` |
| `org_id` | ObjectId | indexed · tenant key |
| `assignee_id` | Link[User] | |
| `assigner_id` | Link[User] | |
| `created_at` | datetime | UTC, set at insert |

---

## API Reference

All routes except `/health` and `/ready` require `Authorization: Bearer <token>`.

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/login` | Exchange email + password for a JWT |

### Organizations

| Method | Path | Permission |
|---|---|---|
| `POST` | `/api/v1/organizations` | `organizations:create` |
| `GET` | `/api/v1/organizations` | `organizations:read` |
| `GET` | `/api/v1/organizations/{org_id}` | `organizations:read` |
| `PATCH` | `/api/v1/organizations/{org_id}` | `organizations:update` |
| `DELETE` | `/api/v1/organizations/{org_id}` | `organizations:delete` |

### Roles

| Method | Path | Permission |
|---|---|---|
| `POST` | `/api/v1/roles` | `roles:create` |
| `GET` | `/api/v1/roles` | `roles:read` |
| `GET` | `/api/v1/roles/{role_id}` | `roles:read` |
| `PATCH` | `/api/v1/roles/{role_id}` | `roles:update` |
| `DELETE` | `/api/v1/roles/{role_id}` | `roles:delete` |

### Users

| Method | Path | Permission |
|---|---|---|
| `POST` | `/api/v1/users` | `users:create` |
| `GET` | `/api/v1/users` | `users:read` |
| `GET` | `/api/v1/users/{user_id}` | `users:read` |
| `PATCH` | `/api/v1/users/{user_id}` | `users:update` |
| `DELETE` | `/api/v1/users/{user_id}` | `users:delete` |

> `GET /users/{user_id}` returns `salary: "$•••••"` unless the caller's JWT includes `salary:read_raw`.

### Tasks

| Method | Path | Permission |
|---|---|---|
| `POST` | `/api/v1/tasks` | `tasks:assign` |
| `GET` | `/api/v1/tasks` | `tasks:read` |
| `GET` | `/api/v1/tasks/{task_id}` | `tasks:read` |
| `PATCH` | `/api/v1/tasks/{task_id}` | `tasks:update` |
| `DELETE` | `/api/v1/tasks/{task_id}` | `tasks:delete` |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness — always returns `{"status": "healthy"}` |
| `GET` | `/ready` | Readiness — pings MongoDB; `503` if unavailable |

> Interactive Swagger docs: `http://localhost:8000/docs`

---

## Configuration

Copy the example file and fill in `SECRET_KEY`:

```bash
cp backend/.env.example backend/.env
```

| Variable | Default | Required |
|---|---|---|
| `SECRET_KEY` | — | ✅ Long random string (see below) |
| `MONGO_URI` | `mongodb://localhost:27017` | |
| `MONGO_DATABASE` | `apexops_db` | |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | |

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> Never commit `.env`. It is gitignored. Only `.env.example` belongs in version control.

---

## Installation

**Prerequisites:** Python 3.12+, MongoDB (local or remote URI).

```bash
# 1. Clone
git clone <repository-url>
cd apexops/backend

# 2. Virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Dependencies
pip install -r requirements.txt

# 4. Environment
cp .env.example .env
# Set SECRET_KEY in .env
```

---

## Running the App

```bash
cd backend
uvicorn app.main:app --reload
```

| URL | Purpose |
|---|---|
| `http://localhost:8000` | API root |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/health` | Liveness probe |
| `http://localhost:8000/ready` | Readiness probe |

---

## Running Tests

No live database needed — all tests use `AsyncMock` and monkeypatching.

```bash
cd backend
pytest
```

| Suite | Covers |
|---|---|
| `test_auth.py` | Login, inactive users, JWT validation, expired/tampered tokens, bcrypt round-trip |
| `test_rbac_tenant.py` | Permission enforcement, cross-tenant 404, invalid ObjectId handling |
| `test_masking.py` | Salary masking with/without `salary:read_raw`, null salary |
| `test_models.py` | Field-level validation on Beanie documents |
| `test_crud.py` | CRUD coverage for core domain objects |
| `test_health.py` | Liveness/readiness probes, MongoDB-unavailable path |

---

## Security

| Concern | Implementation |
|---|---|
| Secret key | Loaded as `SecretStr` — never printed in logs or tracebacks |
| Passwords | bcrypt via passlib; hashing runs in a threadpool (non-blocking) |
| Token claims | `sub`, `org_id`, `role`, `permissions`, `exp` all required; missing → `401` |
| Deactivated users | Subject re-verified against the database on every request |
| Cross-tenant access | Returns `404` (not `403`) to avoid confirming other orgs exist |
| Salary field | Serialized as `str` in all schemas; raw float never reaches the response |
| Environment secrets | `.env` is gitignored; only `.env.example` is committed |

---

## Future Improvements

| Priority | Improvement |
|---|---|
| 🔴 High | **Per-organization roles** — `Role` has no `org_id`, making roles visible across all tenants. This is a data isolation gap and will be addressed as a priority. |
| 🟡 Medium | **Email validation** — `User.email` and `Organization.email` are plain strings. Pydantic's `EmailStr` will be added to enforce format at the API boundary. |
| 🟡 Medium | **Structured date of birth** — `User.dob` is a plain string. Will migrate to `datetime.date` or a regex-annotated field. |
| 🟢 Low | **Assignment status enum** — `Assignment.status` is a free-form string. A `StrEnum` (`pending`, `in_progress`, `done`, `cancelled`) will replace it. |
