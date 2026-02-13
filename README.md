# SaaS Metering Platform (WIP)

A production-style SaaS backend starter focused on **API key management, rate limiting, quotas, usage metering, and billing-ready reporting**.

## Status (Days 1–6)

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

### Day 5 - API Key Management + dual auth
- **API Key model** - `api_keys` table with SHA-256 hashed key storage (plaintext is never persisted)
  - Stripe-style prefixed keys (`smp_live_...`) for easy identification and leak scanning
  - `key_prefix` stored for safe UI display, `key_hash` for authentication lookups
  - Soft-delete revocation (`is_active` flag) preserves audit history
  - Optional `expires_at` and auto-updated `last_used_at` fields
- **Create key** - `POST /orgs/{org_id}/api-keys` generates a key and returns the plaintext **once**
  - Only `owner` / `admin` roles can create keys (RBAC enforced)
- **List keys** - `GET /orgs/{org_id}/api-keys` returns metadata only (prefix, status, timestamps)
  - Neither the plaintext key nor the hash is ever returned on list
- **Revoke key** - `DELETE /orgs/{org_id}/api-keys/{key_id}` soft-revokes (sets `is_active=False`)
  - Revoked keys immediately stop authenticating requests
- **X-API-Key header auth** - `get_current_api_key` FastAPI dependency for external consumer auth
  - Hashes the incoming key, looks up the hash, checks active status and expiration
  - Updates `last_used_at` on each successful authentication
- **Dual authentication** - JWT for dashboard users, API keys for external API consumers
- Alembic migration for `api_keys` table (with FK cascade to `orgs`)
- Full test suite (`test_api_keys.py` - 18 tests covering create, list, revoke, and X-API-Key auth)
- **37 total tests passing** across auth, orgs, and API keys

### Day 6 - Redis + rate limiting (fixed-window)
- **Redis connection pool** in `backend/app/core/redis.py`: shared sync client with lazy init and configurable `REDIS_HOST` / `REDIS_PORT`, ready for rate limiting and future caching
- **Rate limiter** in `backend/app/core/rate_limit.py`: fixed-window (per-minute default) counter using Redis `INCR` + `EXPIRE`, key format `rl:{api_key_id}:{window_start}`, returns `RateLimitResult` for headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- **Per-org limits** stored on `Org.rate_limit_rpm` in `backend/app/models/orgs.py`
- **Tests** added in `backend/tests/test_rate_limit.py`

---

## Project Structure

```
backend/
├── alembic/              # DB migration scripts
│   └── versions/         # Auto-generated migration files
├── app/
│   ├── api/              # Route handlers
│   │   ├── auth.py       # /auth/signup, /auth/login, /auth/me
│   │   ├── orgs.py       # /orgs CRUD + member management
│   │   └── api_keys.py   # /orgs/{id}/api-keys CRUD
│   ├── core/
│   │   ├── roles.py      # RBAC helper (require_org_role)
│   │   ├── security.py   # Argon2 hashing, JWT, API key auth dependency
│   │   ├── rate_limit.py # Check and increment the rate limit counter for an API key using redis.
│   │   └── redis.py      # Operates the redis connection pool.
│   ├── db/
│   │   ├── base.py       # SQLAlchemy declarative base
│   │   ├── deps.py       # FastAPI DB session dependency
│   │   └── session.py    # Engine & SessionLocal factory
│   ├── models/
│   │   ├── user.py       # User ORM model
│   │   ├── orgs.py       # Org ORM model
│   │   ├── org_member.py # OrgMember ORM model
│   │   └── api_key.py    # ApiKey ORM model (SHA-256 hashed keys)
│   ├── schemas/
│   │   ├── auth.py       # SignupIn, TokenOut, UserOut
│   │   ├── orgs.py       # OrgCreateIn, OrgOut, OrgMemberAddIn, OrgMemberOut
│   │   └── api_keys.py   # ApiKeyCreateIn, ApiKeyCreateOut, ApiKeyOut
│   ├── services/
│   │   ├── users.py      # create_user, get_user_by_email
│   │   ├── orgs.py       # create_org, list_user_orgs, add_member_by_email
│   │   └── api_keys.py   # create, list, revoke, hash, lookup by hash
│   └── main.py           # FastAPI app + router wiring
├── tests/
│   ├── conftest.py       # Fixtures (in-memory SQLite, TestClient, auth helpers)
│   ├── test_auth.py      # Auth endpoint tests (8 tests)
│   ├── test_orgs.py      # Org endpoint + RBAC tests (11 tests)
│   ├── test_api_keys.py  # API key CRUD + X-API-Key auth tests (18 tests)
│   └── test_rate_limit.py # Tests for the sliding-window rate limiter (6 tests)
├── Dockerfile
└── pyproject.toml
```

---

## API Endpoints

| Method | Path                                | Auth    | Description                             |
|--------|-------------------------------------|---------|-----------------------------------------|
| GET    | `/health`                           | No      | Health check                            |
| POST   | `/auth/signup`                      | No      | Register a new user                     |
| POST   | `/auth/login`                       | No      | Login → JWT access token                |
| GET    | `/auth/me`                          | JWT     | Current user profile                    |
| POST   | `/orgs`                             | JWT     | Create an organization                  |
| GET    | `/orgs`                             | JWT     | List user's organizations               |
| POST   | `/orgs/{org_id}/members`            | JWT     | Add/update a member (owner/admin)       |
| POST   | `/orgs/{org_id}/api-keys`           | JWT     | Generate API key (owner/admin)          |
| GET    | `/orgs/{org_id}/api-keys`           | JWT     | List API keys (prefix only, no secrets) |
| DELETE | `/orgs/{org_id}/api-keys/{key_id}`  | JWT     | Revoke (soft-delete) an API key         |

---

## Tech Stack
- **Backend:** FastAPI (Python 3.11+)
- **DB:** PostgreSQL 16
- **Cache:** Redis 7
- **ORM:** SQLAlchemy 2.0
- **Migrations:** Alembic
- **Auth:** Argon2 password hashing + JWT (python-jose) + SHA-256 API keys
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
