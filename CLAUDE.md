# ApexOps — CLAUDE.md

## Project overview

Multi-tenant business management backend. FastAPI + MongoDB (Beanie ODM). JWT-based auth with permission-string RBAC. All work lives under `backend/`.

## Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env       # then fill in SECRET_KEY
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Running the server

```bash
cd backend
uvicorn app.main:app --reload
```

API available at http://localhost:8000  
Interactive docs at http://localhost:8000/docs

## Running tests

```bash
cd backend
pytest
```

Tests use monkeypatching and AsyncMock — no live database required.

## Project structure

```
backend/
  app/
    main.py              # FastAPI app, lifespan, router mounts
    core/
      config.py          # pydantic-settings, reads from .env
      security.py        # JWT creation, bcrypt hashing/verification
    models/
      models.py          # Beanie documents: Organization, Role, User, Assignment
    schemas/             # Pydantic request/response schemas per resource
    api/v1/              # Route handlers: auth, organizations, roles, users, tasks
    dependencies/
      auth.py            # JWT decode, require_permission(), get_user_in_tenant()
  tests/                 # pytest suites (no live DB needed)
  .env.example           # environment variable template
  requirements.txt
```

## Key conventions

- Every data query is scoped to `org_id` from the JWT — never query without it.
- `require_permission("resource:action")` is the standard route dependency.
- Salary is always serialized as `str` in responses; raw value only with `salary:read_raw` in the JWT.
- Password updates go through `hash_password()` in a threadpool — never store plain text.
- Settings are accessed via `get_settings()` (lru_cached); never import config values directly.

## Known issues / future work

See README.md for the full list of pending improvements.
