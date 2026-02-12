# SaaS Metering Platform (WIP)

A production-style SaaS backend starter focused on **API key management, rate limiting, quotas, usage metering, and billing-ready reporting**.

## Status (Days 1–4)

### Day 1 - Containerized dev stack
- Docker Compose stack running:
  - FastAPI API service
  - PostgreSQL 16
  - Redis 7
- Health endpoint available:
  - `GET /health` -> `{ "status": "ok" }`

### Day 2 - Database + migrations
- Added SQLAlchemy base/session structure (`app/db/base.py`, `session.py`, `deps.py`)
- Initialized Alembic for **versioned schema migrations**
- Created `User` model and generated the first migration (`users` table)
- Applied migrations to Postgres via `alembic upgrade head`

### Day 3 - Auth (signup, login, JWT)
- **Signup** - `POST /auth/signup` creates a user with Argon2 password hashing
  - Email normalization (lowercase + trim)
  - Pydantic validation (valid email, password 10 - 128 chars)
  - Duplicate-email rejection (400)
- **Login** - `POST /auth/login` (OAuth2 password form) returns a signed JWT
  - Configurable secret, algorithm, and expiration via env vars
  - Production-safe guard: rejects weak/default `JWT_SECRET` when `APP_ENV=production`
- **Me** - `GET /auth/me` returns the current user from the Bearer token
  - Token decode + user lookup; 401 on missing/invalid/expired token
- Full test suite (`test_auth.py` - 8 tests covering happy paths & edge cases)

### Day 4 - Multi-tenant organizations + RBAC
- **Org model** - `orgs` table with id, name, created_at
- **OrgMember model** - `org_members` join table with role (`owner` / `admin` / `member`) and unique constraint on (org_id, user_id)
- Alembic migration for `orgs` + `org_members` tables (with FK cascades)
- **Create org** - `POST /orgs` creates an org and auto-assigns the creator as `owner`
- **List orgs** - `GET /orgs` returns only the orgs the authenticated user belongs to (newest first)
- **Add member** - `POST /orgs/{org_id}/members` adds (or re-roles) a user by email
- **Role-based access control (RBAC):**
  - Only `owner` / `admin` can add members
  - Only `owner` can grant or revoke the `owner` role
  - Cannot demote the last owner (prevents orphaned orgs)
  - `member` role is denied from adding others (403)
- Reusable `require_org_role()` guard in `app/core/roles.py`
- Full test suite (`test_orgs.py` - 11 tests covering CRUD, visibility isolation, and role enforcement)

---

## Project Structure

```
backend/
├── alembic/              # DB migration scripts
│   └── versions/         # Auto-generated migration files
├── app/
│   ├── api/              # Route handlers
│   │   ├── auth.py       # /auth/signup, /auth/login, /auth/me
│   │   └── orgs.py       # /orgs CRUD + member management
│   ├── core/
│   │   ├── roles.py      # RBAC helper (require_org_role)
│   │   └── security.py   # Argon2 hashing, JWT create/decode
│   ├── db/
│   │   ├── base.py       # SQLAlchemy declarative base
│   │   ├── deps.py       # FastAPI DB session dependency
│   │   └── session.py    # Engine & SessionLocal factory
│   ├── models/
│   │   ├── user.py       # User ORM model
│   │   ├── orgs.py       # Org ORM model
│   │   └── org_member.py # OrgMember ORM model
│   ├── schemas/
│   │   ├── auth.py       # SignupIn, TokenOut, UserOut
│   │   └── orgs.py       # OrgCreateIn, OrgOut, OrgMemberAddIn, OrgMemberOut
│   ├── services/
│   │   ├── users.py      # create_user, get_user_by_email
│   │   └── orgs.py       # create_org, list_user_orgs, add_member_by_email
│   └── main.py           # FastAPI app + router wiring
├── tests/
│   ├── conftest.py       # Fixtures (in-memory SQLite, TestClient, auth helpers)
│   ├── test_auth.py      # Auth endpoint tests
│   └── test_orgs.py      # Org endpoint + RBAC tests
├── Dockerfile
└── pyproject.toml
```

---

## API Endpoints

| Method | Path                        | Auth | Description                          |
|--------|-----------------------------|------|--------------------------------------|
| GET    | `/health`                   | No   | Health check                         |
| POST   | `/auth/signup`              | No   | Register a new user                  |
| POST   | `/auth/login`               | No   | Login → JWT access token             |
| GET    | `/auth/me`                  | Yes  | Current user profile                 |
| POST   | `/orgs`                     | Yes  | Create an organization               |
| GET    | `/orgs`                     | Yes  | List users organizations            |
| POST   | `/orgs/{org_id}/members`    | Yes  | Add/update a member (owner/admin)    |

---

## Tech Stack
- **Backend:** FastAPI (Python 3.11+)
- **DB:** PostgreSQL 16
- **Cache:** Redis 7
- **ORM:** SQLAlchemy 2.0
- **Migrations:** Alembic
- **Auth:** Argon2 password hashing + JWT (python-jose)
- **Validation:** Pydantic v2
- **Testing:** pytest + FastAPI TestClient (in-memory SQLite)
- **Local orchestration:** Docker Compose

---

## Local Development

### Prerequisites
- Docker Desktop running
- Docker Compose available (`docker compose`)

### Environment
This project uses a root `.env` file with:
- `APP_ENV`
- `POSTGRES_DB`
- `POSTGRES_HOST`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT`
- `POSTGRES_USER`
- `REDIS_HOST`
- `REDIS_PORT`
- `JWT_SECRET` (must be set to a strong value in production)
- `JWT_ALGORITHM` (default: `HS256`)
- `JWT_EXPIRES_MINUTES` (default: `60`)

### Start the stack
```bash
docker compose up --build
```

### Run tests
```bash
cd backend
pip install -e ".[test]"
pytest
```

### Makefile shortcuts
```bash
make up      # docker compose up --build
make down    # docker compose down -v
make logs    # docker compose logs -f api
```
