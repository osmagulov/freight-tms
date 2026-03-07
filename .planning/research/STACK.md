# Stack: Freight TMS MVP

**Project:** Freight TMS — Telegram bot (drivers) + FastAPI backend + web dashboard (dispatcher/director)
**Researched:** 2026-03-08
**Overall confidence:** HIGH — all versions verified via PyPI, all library choices verified via official docs or multiple credible sources

---

## Decided (Constraints)

These are non-negotiable per project constraints. Research confirms they are sound choices:

| Technology | Version | Why Decided |
|------------|---------|-------------|
| Python | 3.12+ | All libraries require 3.10+; 3.12 is current stable, best async performance |
| python-telegram-bot | 22.6 | Constraint — team already uses it. Latest stable (Jan 24 2026). |
| FastAPI | 0.135.1 | Constraint — team familiar. Latest stable (Mar 1 2026). |
| PostgreSQL | 16 | Constraint — relational DB required for 100+ drivers, complex reporting |
| Railway | — | Constraint — already used for existing bot. Supports Dockerfile + PostgreSQL service |

---

## Recommended Libraries

### Bot Layer: python-telegram-bot + FSM

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `python-telegram-bot` | 22.6 | Core Telegram bot framework | Constraint. Built-in `ConversationHandler` handles FSM dialogs natively — entry_points + states dict = multi-step dialogs without external FSM library |
| `httpx` | 0.28.1 | Async HTTP client for bot→API calls | python-telegram-bot v22 is fully async; httpx is the standard async HTTP client. Use to call FastAPI endpoints from bot handlers |

**FSM note:** Do NOT add a separate FSM library (transitions, aiogram-style FSM, etc.). `ConversationHandler` with `states` dict is the built-in PTB mechanism. It supports persistence (save state to DB), timeouts, and nested conversations. This covers all driver dialog flows.

**Webhook vs polling:**
- **Development:** Long polling (no infrastructure needed)
- **Production on Railway:** Webhook mode. Railway provides HTTPS URL automatically. Webhook handles 100+ concurrent drivers without polling overhead. Set via `Application.run_webhook()`.

### Database Layer: SQLAlchemy 2.0 + asyncpg

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `SQLAlchemy` | 2.0.48 | Async ORM + query builder | Industry standard for FastAPI async. SQLAlchemy 2.0 has first-class async support via `AsyncSession`. Prevents event loop blocking. |
| `asyncpg` | 0.31.0 | Async PostgreSQL driver | Fastest Python PostgreSQL driver. Required by SQLAlchemy's async engine (`postgresql+asyncpg://`). C implementation, designed for asyncio. |
| `alembic` | 1.18.4 | Database migrations | Standard companion to SQLAlchemy. Schema versioning via `alembic upgrade head`. Critical for Railway deploys where DB must evolve without data loss. |

**Connection string pattern for Railway:**
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
```
Railway exposes `DATABASE_URL` env var automatically when PostgreSQL service is added.

### FastAPI Backend

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `fastapi` | 0.135.1 | REST API framework | Constraint. Native async, auto OpenAPI docs, Pydantic integration. |
| `uvicorn` | 0.41.0 | ASGI server | Standard ASGI server for FastAPI. Use `uvicorn[standard]` for WebSocket support and performance extras. For Railway: `CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `pydantic` | 2.12.5 | Request/response validation + settings | FastAPI depends on it. Pydantic v2 (via `pydantic-settings`) handles env var loading for Railway config — reads `DATABASE_URL`, `BOT_TOKEN`, `R2_*` from environment. |
| `pydantic-settings` | 2.x | Environment variable config | Use `BaseSettings` class with `model_config = SettingsConfigDict(env_file=".env")`. Single source of truth for all config. |
| `python-multipart` | 0.0.22 | File upload parsing | Required by FastAPI for `UploadFile` form fields. Needed for web dashboard photo upload endpoint. |
| `python-jose[cryptography]` | 3.5.0 | JWT token generation/validation | Dashboard auth: dispatcher and director login via session token. `python-jose` is maintained and current (May 2025). |
| `pwdlib[bcrypt]` | 0.3.0 | Password hashing | Replaces unmaintained `passlib` (last release 2020, broken in Python 3.13). FastAPI official docs now recommend `pwdlib`. `pwdlib[bcrypt]` installs bcrypt hasher. |

**Auth approach for web dashboard:**
Simple JWT-based auth. Dispatcher and director login with username + password. FastAPI returns Bearer token. Token stores role (`dispatcher` / `director`). Route guards check role from token. No OAuth, no social login — internal tool only.

### Web Dashboard: FastAPI + Jinja2 + HTMX

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `jinja2` | 3.1.6 | Server-side HTML templating | FastAPI `Jinja2Templates` renders dashboard HTML server-side. No separate React/Vue app. Zero frontend build pipeline. |
| `htmx` | 2.x (CDN) | Dynamic UI without JavaScript | Load via CDN in base template. HTMX handles partial page updates (expense list refresh, alert feed) via `hx-get`/`hx-post` attributes. Eliminates need for a frontend framework. |
| `leaflet.js` | 1.x (CDN) | Interactive truck location map | Load via CDN. Free, open-source. Renders truck positions from `/api/trucks/locations` JSON endpoint. No API key required for OpenStreetMap tiles. |

**Why not React/Vue:** This is an internal ops dashboard used by 2-5 dispatchers and 1 director. Server-rendered HTML with HTMX delivers sub-50ms updates. No build pipeline, no Node.js toolchain, no separate deployment. FastAPI serves both the API and the dashboard from one process.

### File/Photo Storage: Cloudflare R2

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `boto3` | 1.42.63 | S3-compatible client | R2 implements full S3v4 API. boto3 works with R2 by setting `endpoint_url`. |

**Storage solution:** Cloudflare R2

- **Free tier:** 10 GB storage + 10M read ops/month — sufficient for MVP phase (fuel receipt photos ~100KB each, 100 drivers × 10 receipts/day × 30 days = ~3 GB/month)
- **Zero egress fees:** Unlike AWS S3, R2 charges no egress. Critical because photos are viewed frequently by dispatchers
- **S3 API compatible:** `boto3` connects with `endpoint_url = 'https://<account-id>.r2.cloudflarestorage.com'`
- **Pattern:** Bot downloads photo from Telegram (`file.download_as_bytearray()`), backend uploads to R2, stores R2 object key in PostgreSQL

**NOT MinIO self-hosted:** MinIO requires a separate server to manage. R2 is zero-ops, which fits Railway + MVP constraints.

**Photo flow:**
```
Driver sends photo → PTB downloads from Telegram servers →
FastAPI endpoint receives bytes → boto3 uploads to R2 →
R2 object key stored in expenses.receipt_photo_key (PostgreSQL) →
Dashboard generates presigned URL from key → Dispatcher sees photo
```

### Background Tasks: APScheduler (AsyncIOScheduler)

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `APScheduler` | 3.11.2 | Anomaly detection scheduler | Runs periodic fuel anomaly check as async job inside FastAPI process |

**Why not Celery + Redis:**
- Celery requires a Redis broker service — extra Railway service, extra cost, extra operational overhead
- Our anomaly detection is a simple SQL query that runs every N minutes: compare actual vs norm consumption, flag if >10% deviation
- This is a lightweight, predictable task — not CPU-intensive, not long-running
- `APScheduler`'s `AsyncIOScheduler` runs inside the FastAPI event loop, no additional infrastructure

**Why not FastAPI `BackgroundTasks`:**
- `BackgroundTasks` fires once per request. Anomaly detection must run on a schedule, not triggered by incoming requests

**Pattern:**
```python
# In FastAPI lifespan startup
scheduler = AsyncIOScheduler()
scheduler.add_job(check_fuel_anomalies, "interval", hours=1)
scheduler.start()
```

**Notification channel:** When anomaly detected, use `python-telegram-bot` to push alert to director's Telegram chat (already in use for existing fuel bot). No separate notification infrastructure needed.

---

## Integration Architecture

```
[Telegram Servers]
       |
       | (webhook POST / polling)
       v
[python-telegram-bot v22.6]  ←→  [httpx 0.28.1]
   ConversationHandler FSM                |
   Photo download: get_file()             |
   Location: Message.location            |
                                          v
                              [FastAPI 0.135.1 + uvicorn 0.41.0]
                                          |
                          +--------------+----------------+
                          |              |                |
                          v              v                v
                   [SQLAlchemy 2.0   [Jinja2 +      [APScheduler
                    + asyncpg 0.31]   HTMX + Leaflet]  Scheduler]
                          |              |                |
                          v              |                v
                  [PostgreSQL 16]    [Web Browser]  [R2/boto3 + PTB alert]
                  (Railway service)  (Dispatcher/
                                      Director)
                                          |
                                          v
                                 [Cloudflare R2]
                                 (receipt photos,
                                  CMR documents)
```

**Two services on Railway:**
1. **Bot + API service:** Single Python process runs both FastAPI (with uvicorn) and PTB webhook handler. PTB's `Application` can run alongside FastAPI via shared event loop or as separate startup tasks in `lifespan`.
2. **PostgreSQL service:** Railway one-click PostgreSQL. Connect via `DATABASE_URL` env var.

**Note on bot + API co-location:** PTB v22 supports webhook mode where Telegram POSTs updates to a FastAPI endpoint (`/webhook`). FastAPI receives the update and passes it to PTB's `Application`. This means one Railway service handles everything — no separate bot process.

---

## Storage Solution

**Primary:** Cloudflare R2 (object storage for photos and documents)
- Fuel receipt photos (mandatory per expense submission)
- Fine ticket photos
- CMR waybill scans
- Repair invoice photos

**In PostgreSQL:** Store only the R2 object key (`expenses.receipt_key = "receipts/2026/03/driver_42_fuel_1234.jpg"`). Never store file bytes in PostgreSQL. Generate presigned URLs (1-hour expiry) when dashboard requests a photo.

**File naming convention:** `{category}/{year}/{month}/{driver_id}_{expense_id}.{ext}`

**File size limits:** Telegram enforces 20MB max photo size. Compress to max 2MB before R2 upload using Python `Pillow` (add `Pillow>=11.0.0` to requirements).

---

## Full Requirements File

```
# Core framework
fastapi==0.135.1
uvicorn[standard]==0.41.0
python-multipart==0.0.22

# Bot
python-telegram-bot==22.6
httpx==0.28.1

# Database
sqlalchemy==2.0.48
asyncpg==0.31.0
alembic==1.18.4

# Validation + config
pydantic==2.12.5
pydantic-settings==2.8.x

# Auth
python-jose[cryptography]==3.5.0
pwdlib[bcrypt]==0.3.0

# Templating (dashboard)
jinja2==3.1.6

# Storage
boto3==1.42.63

# Background scheduling
APScheduler==3.11.2

# Image processing
Pillow>=11.0.0
```

---

## Railway Deployment Constraints

- **One Dockerfile per service** — Railway auto-detects and builds. Use `python:3.12-slim` base image.
- **Port:** Railway sets `$PORT` env var. Uvicorn must bind to `0.0.0.0:$PORT`.
- **Environment variables:** Set in Railway dashboard: `DATABASE_URL` (auto-set by PostgreSQL service), `BOT_TOKEN`, `CF_R2_ENDPOINT`, `CF_R2_ACCESS_KEY`, `CF_R2_SECRET_KEY`, `CF_R2_BUCKET`, `JWT_SECRET`.
- **Migrations:** Run `alembic upgrade head` as Railway's deploy command before starting uvicorn, or use a separate Railway "one-off job" in deploy hooks.
- **Redis:** NOT required. APScheduler runs in-process. This saves ~$5-10/month vs adding Railway Redis.
- **No persistent local disk:** Railway containers are ephemeral. All files must go to R2, never to local filesystem.

---

## What NOT to Add (MVP Scope)

| What | Why Not | If Needed Later |
|------|---------|-----------------|
| Celery + Redis | APScheduler handles anomaly alerts in-process. Redis adds infra cost and ops complexity | Add if anomaly checks become long-running or fan out to multiple workers |
| Separate React/Vue dashboard | Server-rendered Jinja2 + HTMX is sufficient for 5-person dispatcher team. Build pipeline adds deployment complexity | Migrate to React if dashboard needs real-time collaboration or complex state |
| aiogram or Telethon | Team constraint is python-telegram-bot. Switching frameworks mid-project is high risk | Stay on PTB v22 |
| MongoDB / Redis as primary DB | PostgreSQL handles relational data (drivers, trucks, trips, expenses) cleanly. NoSQL adds schema flexibility we don't need | If event log volume becomes extreme, add TimescaleDB later |
| WebSockets for real-time map | HTMX polling every 30s is sufficient for location updates. WebSockets add complexity. Dispatchers don't need sub-second updates | Add SSE or WebSockets if dispatcher reports that 30s is too slow |
| Email notifications | All stakeholders are on Telegram. Use PTB to alert director, not email | Add email if director requests it |
| Docker Compose locally | Use `pip install -r requirements.txt` + local PostgreSQL for dev. Docker Compose adds overhead for a Python-first team | Add if dev team grows beyond 3 people |
| Separate auth service / OAuth | JWT tokens checked in FastAPI middleware is sufficient for 5 internal users. Keycloak/Auth0 is massive overkill | Add SSO if company requires it |
| MinIO self-hosted | Requires managing a server. Cloudflare R2 is zero-ops and has a free tier. | Never — use R2 or AWS S3 directly |
| `passlib` | Unmaintained since 2020, broken in Python 3.13. Use `pwdlib[bcrypt]` instead. | N/A — do not use passlib |
| GPS hardware / SIM tracker | Out of scope per PROJECT.md. Manual geolocation via Telegram is MVP. | Phase 2+ if client wants background tracking |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Telegram bot framework | python-telegram-bot 22.6 | aiogram 3.x | aiogram is excellent but team constraint is PTB. Switching has rewrite cost. |
| Async task queue | APScheduler AsyncIOScheduler | Celery + Redis | Celery requires Redis broker service. APScheduler runs in-process, zero extra infra for simple interval job. |
| Dashboard frontend | Jinja2 + HTMX + Leaflet | React + separate API | React requires Node.js build pipeline, separate Railway deployment. Overkill for internal ops tool with 5 users. |
| Object storage | Cloudflare R2 | AWS S3 / MinIO | R2: zero egress fees, 10GB free tier, S3-compatible. AWS S3: egress costs add up. MinIO: requires server management. |
| Password hashing | pwdlib[bcrypt] | passlib | passlib is unmaintained (2020), throws deprecation errors in Python 3.11+, removed in 3.13. |
| Background scheduling | APScheduler 3.x | arq (asyncio task queue) | arq is in maintenance-only mode. APScheduler 3.x is actively maintained and simpler for simple cron/interval jobs. |
| Map tiles | Leaflet + OpenStreetMap | Google Maps | Google Maps requires API key and billing. OpenStreetMap via Leaflet is free, no key required. |
| ORM | SQLAlchemy 2.0 | Tortoise ORM / SQLModel | SQLAlchemy 2.0 has the largest ecosystem, best Alembic integration, most production battle-tested. |

---

## Sources

- [python-telegram-bot v22.6 PyPI](https://pypi.org/project/python-telegram-bot/) — HIGH confidence (official)
- [python-telegram-bot ConversationHandler v22.6 docs](https://docs.python-telegram-bot.org/en/stable/) — HIGH confidence (official)
- [FastAPI 0.135.1 PyPI](https://pypi.org/project/fastapi/) — HIGH confidence (official)
- [SQLAlchemy 2.0.48 PyPI](https://pypi.org/project/sqlalchemy/) — HIGH confidence (official)
- [asyncpg 0.31.0 PyPI](https://pypi.org/project/asyncpg/) — HIGH confidence (official)
- [Alembic 1.18.4 PyPI](https://pypi.org/project/alembic/) — HIGH confidence (official)
- [uvicorn 0.41.0 PyPI](https://pypi.org/project/uvicorn/) — HIGH confidence (official)
- [Pydantic 2.12.5 PyPI](https://pypi.org/project/pydantic/) — HIGH confidence (official)
- [APScheduler 3.11.2 PyPI](https://pypi.org/project/APScheduler/) — HIGH confidence (official)
- [arq 0.27.0 PyPI](https://pypi.org/project/arq/) — HIGH confidence (official, noted maintenance-only mode)
- [pwdlib 0.3.0 PyPI](https://pypi.org/project/pwdlib/) — HIGH confidence (official)
- [python-jose 3.5.0 PyPI](https://pypi.org/project/python-jose/) — HIGH confidence (official)
- [boto3 1.42.63 PyPI](https://pypi.org/project/boto3/) — HIGH confidence (official)
- [Jinja2 3.1.6 PyPI](https://pypi.org/project/jinja2/) — HIGH confidence (official)
- [Cloudflare R2 Free Tier + boto3 docs](https://developers.cloudflare.com/r2/) — HIGH confidence (official Cloudflare)
- [FastAPI + APScheduler patterns](https://rajansahu713.medium.com/implementing-background-job-scheduling-in-fastapi-with-apscheduler-6f5fdabf3186) — MEDIUM confidence (verified pattern)
- [FastAPI + HTMX dashboard patterns](https://testdriven.io/blog/fastapi-htmx/) — MEDIUM confidence (testdriven.io)
- [Railway PostgreSQL docs](https://docs.railway.com/databases/postgresql) — HIGH confidence (official Railway)
- [FastAPI pwdlib security docs](https://github.com/fastapi/fastapi/discussions/11773) — HIGH confidence (official FastAPI maintainer discussion)
- [Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, and Asyncpg](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg) — MEDIUM confidence (verified via official docs)
