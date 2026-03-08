# Phase 1: Infrastructure & Foundation - Research

**Researched:** 2026-03-08
**Domain:** FastAPI + python-telegram-bot webhook, Railway deployment, PostgreSQL/Alembic, Cloudflare R2, JWT auth
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Система развёрнута на Railway — FastAPI + PTB webhook в одном процессе, PostgreSQL addon | FastAPI lifespan + Application.builder().updater(None) pattern; railway.toml startCommand |
| INFRA-02 | Alembic миграции запускаются до старта приложения (pre-deploy hook, не внутри startup) | railway.toml preDeployCommand = ["alembic", "upgrade", "head"] |
| INFRA-03 | Cloudflare R2 подключён для хранения фото чеков и документов | boto3 S3-compatible client with R2 endpoint; upload_fileobj pattern |
| INFRA-04 | FSM-состояние ConversationHandler персистируется (PicklePersistence) — не теряется при Railway редеплое | PicklePersistence with Railway Volume mounted at /data; name + persistent=True on each ConversationHandler |
| INFRA-05 | Веб-панель требует авторизации (JWT, роли: dispatcher / director) | python-jose JWT + pwdlib[bcrypt]; httponly cookie pattern with Jinja2 redirect on 401 |
| REG-01 | Водитель может зарегистрироваться через /start в Telegram-боте (ФИО, телефон) | Already exists in src/bot/bot_app.py — needs PicklePersistence added and driver-vehicle link fixed |
| REG-02 | Водитель может привязать борт к своему аккаунту (по номеру/госномеру) | receive_vehicle() exists but doesn't create driver-vehicle FK link; Driver model needs vehicle_id FK |
| REG-03 | Диспетчер видит список зарегистрированных водителей и их бортов на веб-панели | New Jinja2 route /panel/drivers; SQLAlchemy join query Driver+Vehicle |
| REG-04 | Диспетчер может вручную создать/отредактировать запись борта (марка, модель, норма расхода л/100км) | New Vehicle fields: make, model, fuel_norm_per_100km (Float); CRUD form in web panel |
</phase_requirements>

---

## Summary

This is a brownfield project. A working Telegram bot exists (polling mode, SQLite) with registration, trip, expense, and location flows. Phase 1 converts it to production infrastructure: switch from SQLite to PostgreSQL, integrate FastAPI + PTB in a single process using webhooks and the lifespan pattern, deploy on Railway, add FSM persistence via Railway Volume, store photos in Cloudflare R2, and create a minimal authenticated web panel for dispatchers.

The existing code has a critical gap: `receive_vehicle()` in `bot_app.py` creates a Vehicle and a Driver in separate transactions but never sets a FK relationship between them. The `Driver` model has no `vehicle_id` column and no relationship to Vehicle. This must be fixed in Phase 1 to satisfy REG-02 and enable REG-03 to show driver-truck pairs.

The existing Alembic migration chain (6 migrations, all targeting SQLite) is compatible with PostgreSQL when `DATABASE_URL` is switched to `postgresql+asyncpg://...`. No batch operations were used, so no SQLite-specific syntax needs removal. The migration chain can be replayed against a fresh PostgreSQL database unchanged.

**Primary recommendation:** Switch DATABASE_URL env var, add Railway Volume + PicklePersistence, wire FastAPI lifespan to start PTB in webhook mode, write one new Alembic migration to add `vehicle_id` FK to `drivers` and new fields to `vehicles`, then build minimal Jinja2 web panel with JWT cookie auth.

---

## What Already Exists (Brownfield Inventory)

### Files That EXIST and Must Be Preserved

| File | What It Does | Phase 1 Changes Needed |
|------|-------------|------------------------|
| `src/bot/bot_app.py` | Registration ConversationHandler + all other handlers | Add `persistent=True, name=` to all ConversationHandlers; add PicklePersistence to builder; fix receive_vehicle() to link driver→vehicle |
| `src/db/models.py` | Driver, Vehicle, Trip, Expense, LocationUpdate models | Add `vehicle_id` FK to Driver; add `make`, `model`, `fuel_norm_per_100km` to Vehicle |
| `src/db/database.py` | SQLAlchemy async engine + session factory | No code change needed — DATABASE_URL switch via env var is sufficient |
| `src/db/crud.py` | get_driver_by_tg_id, create_driver, create_vehicle, get_vehicle_by_plate | Add link_driver_to_vehicle() function |
| `src/core/config.py` | Pydantic Settings — reads DATABASE_URL, TELEGRAM_BOT_TOKEN | Add new settings: WEBHOOK_URL, R2_*, JWT_SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD_HASH |
| `src/main.py` | Stub FastAPI app with deprecated @on_event | Replace with lifespan pattern; add PTB webhook route; add web panel routes |
| `alembic/env.py` | Async Alembic runner | No change needed |
| `alembic/versions/` | 6 migrations (SQLite-compatible) | Add one new migration for driver-vehicle link + vehicle fields |
| `antigravity_modules/` | All bot conversation flows | No changes in Phase 1 (flows work; need to add name+persistent to their ConversationHandlers) |
| `requirements.txt` | Core dependencies | Add: `python-jose[cryptography]`, `pwdlib[bcrypt]`, `jinja2`, `python-multipart`, `boto3`, `aiosqlite` (remove or keep for dev) |

### Files That Do NOT Exist Yet

| File | What It Will Be |
|------|----------------|
| `railway.toml` | Railway deployment config |
| `src/web/` | Web panel (routes, templates, auth) |
| `src/web/templates/` | Jinja2 HTML templates |
| `src/services/r2.py` | Cloudflare R2 upload helper |

---

## Standard Stack

### Core
| Library | Version (installed) | Purpose | Why Standard |
|---------|---------------------|---------|--------------|
| `python-telegram-bot[job-queue]` | >=21.6 (already in req) | Telegram bot + ConversationHandler | Already used |
| `fastapi` | >=0.115.0 (already in req) | Web framework + webhook endpoint | Already used |
| `uvicorn[standard]` | >=0.30.0 (already in req) | ASGI server | Already used |
| `SQLAlchemy` | >=2.0.30 (already in req) | Async ORM | Already used |
| `asyncpg` | >=0.30.0 (already in req) | PostgreSQL async driver | Already in req.txt |
| `alembic` | >=1.13.1 (already in req) | Schema migrations | Already used |
| `pydantic-settings` | >=2.5.0 (already in req) | Config from env vars | Already used |

### New Dependencies to Add
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `python-jose[cryptography]` | >=3.3.0 | JWT encode/decode | Standard for FastAPI JWT auth |
| `pwdlib[bcrypt]` | >=0.2.0 | Password hashing | Decided; passlib deprecated/unmaintained |
| `jinja2` | >=3.1.0 | HTML templates for web panel | Decided |
| `python-multipart` | >=0.0.9 | Form data parsing (login form) | Required by FastAPI for form handling |
| `boto3` | >=1.35.0 | Cloudflare R2 (S3-compatible) | Decided |

### Not Needed
- `aiosqlite` — only needed if keeping SQLite for dev; can remove from prod requirements
- `celery`, `redis` — explicitly replaced by APScheduler (not in Phase 1)

**Installation:**
```bash
pip install "python-jose[cryptography]" "pwdlib[bcrypt]" jinja2 python-multipart boto3
```

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
src/
├── bot/
│   └── bot_app.py          # Existing — add persistence + fix vehicle link
├── core/
│   └── config.py           # Add new settings fields
├── db/
│   ├── models.py            # Add vehicle_id FK to Driver; add fields to Vehicle
│   ├── crud.py              # Add link_driver_to_vehicle()
│   └── database.py          # No change
├── web/                     # NEW
│   ├── __init__.py
│   ├── auth.py              # JWT cookie logic, dependencies
│   ├── panel.py             # Dispatcher routes (drivers list, vehicle edit)
│   └── templates/           # Jinja2 HTML
│       ├── base.html
│       ├── login.html
│       └── drivers.html
├── services/                # NEW
│   └── r2.py               # Cloudflare R2 upload helper
└── main.py                  # Replace stub with lifespan + PTB webhook + web routes
alembic/
└── versions/
    └── XXXX_phase1_postgresql_schema.py  # New migration
railway.toml                 # NEW
```

### Pattern 1: FastAPI + PTB Webhook via Lifespan

**What:** Build PTB Application with `.updater(None)` (disables polling), attach to FastAPI via `@asynccontextmanager` lifespan, register `/telegram` POST endpoint that feeds updates to PTB.

**When to use:** Single-process deploy on Railway (one dyno). Polling would require a separate process; webhook is preferred for production.

**Source:** freecodecamp.org PTB v20 webhook guide + PTB official docs

```python
# src/main.py
from contextlib import asynccontextmanager
from http import HTTPStatus
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, PicklePersistence
from src.core.config import settings
from src.bot.bot_app import create_bot_app

ptb_app: Application = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build PTB Application
    persistence = PicklePersistence(filepath="/data/bot_persistence.pkl")
    global ptb_app
    ptb_app = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .updater(None)           # Disable polling — use webhook
        .persistence(persistence)
        .build()
    )
    # Register all handlers (imported from bot_app)
    _register_handlers(ptb_app)

    async with ptb_app:
        # Set webhook URL at startup
        await ptb_app.bot.set_webhook(
            url=f"{settings.WEBHOOK_URL}/telegram",
            allowed_updates=Update.ALL_TYPES,
        )
        await ptb_app.start()
        yield
        await ptb_app.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=HTTPStatus.OK)
```

**Critical:** `@app.on_event("startup")` in current `src/main.py` is deprecated. Must replace with `lifespan=` parameter.

### Pattern 2: PicklePersistence with Railway Volume

**What:** Mount Railway Volume at `/data`, point PicklePersistence to `/data/bot_persistence.pkl`, add `name=` and `persistent=True` to every ConversationHandler.

**Railway Volume note (HIGH confidence from docs):** Volumes are NOT mounted during pre-deploy — they are only available at runtime. Pre-deploy hook cannot read/write to the volume. This is fine for Alembic (only needs database, not volume).

```python
# PicklePersistence setup
from pathlib import Path
from telegram.ext import PicklePersistence

PERSISTENCE_FILE = Path("/data/bot_persistence.pkl")

persistence = PicklePersistence(filepath=PERSISTENCE_FILE)

# Every ConversationHandler must have name + persistent=True
registration_conv = ConversationHandler(
    entry_points=[...],
    states={...},
    fallbacks=[...],
    name="registration",      # Required for persistence
    persistent=True,          # Required for persistence
)
```

**All 5 existing ConversationHandlers need name + persistent=True:**
- `registration` (bot_app.py)
- `trip_opening` (trip_opening.py — need to verify get_trip_conversation_handler() returns with name)
- `expense_flow` (expense_flow.py)
- `location_flow` (location_flow.py)
- `trip_closing` (trip_closing.py)

### Pattern 3: Cloudflare R2 Upload via boto3

**Source:** developers.cloudflare.com/r2/examples/aws/boto3/ — HIGH confidence

```python
# src/services/r2.py
import io
import boto3
from botocore.config import Config
from src.core.config import settings

def get_r2_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",   # Required by SDK, ignored by R2
        config=Config(signature_version="s3v4"),
    )

async def upload_photo_to_r2(file_bytes: bytes, key: str) -> str:
    """Upload bytes to R2 bucket, return public URL or key."""
    client = get_r2_client()
    client.upload_fileobj(
        io.BytesIO(file_bytes),
        settings.R2_BUCKET_NAME,
        key,
    )
    # Return permanent URL if bucket has public access, else generate presigned
    return f"https://{settings.R2_BUCKET_NAME}.{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{key}"
```

**boto3 is synchronous.** For async FastAPI, run upload in threadpool:
```python
import asyncio
result = await asyncio.get_event_loop().run_in_executor(None, upload_sync_fn)
```

### Pattern 4: JWT Auth for Jinja2 Web Panel (Cookie-based)

**Decided stack:** python-jose for JWT, pwdlib[bcrypt] for password hashing, httponly cookie, Jinja2 templates, redirect to /login on 401.

**Source:** FastAPI docs + fastapitutorial.com (MEDIUM confidence, verified against FastAPI docs pattern)

```python
# src/web/auth.py
from datetime import datetime, timedelta
from jose import JWTError, jwt
from pwdlib import PasswordHash
from fastapi import Cookie, HTTPException, status
from fastapi.responses import RedirectResponse
from src.core.config import settings

password_hash = PasswordHash.recommended()

def create_access_token(data: dict, expires_minutes: int = 480) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm="HS256")

def get_current_user_from_cookie(access_token: str = Cookie(default=None)):
    if not access_token:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    try:
        payload = jwt.decode(access_token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise HTTPException(status_code=302, headers={"Location": "/login"})
        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=302, headers={"Location": "/login"})

# Login endpoint
@router.post("/login")
async def login(response: Response, username: str = Form(), password: str = Form()):
    # Verify against settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD_HASH
    if not password_hash.verify(password, settings.ADMIN_PASSWORD_HASH):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    token = create_access_token({"sub": username, "role": "dispatcher"})
    response = RedirectResponse(url="/panel/drivers", status_code=302)
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response
```

**Role model for Phase 1:** Store role in JWT payload. Phase 1 only needs `dispatcher` and `director` — no per-user DB table needed. Admin credentials come from environment variables (ADMIN_USERNAME, ADMIN_PASSWORD_HASH). Multi-user with DB table is deferred.

### Pattern 5: Railway Deployment Configuration

**Source:** docs.railway.com/guides/config-as-code — HIGH confidence

```toml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
preDeployCommand = ["alembic", "upgrade", "head"]
startCommand = "uvicorn src.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/"
healthcheckTimeout = 100
restartPolicyType = "on-failure"
```

**Critical limitation confirmed by Railway docs:** Pre-deploy command runs in a separate container. Railway Volumes are NOT mounted during pre-deploy. This means Alembic (database only, no volume writes) is safe to run as pre-deploy. PicklePersistence file must be written/read during app start/runtime only.

### Pattern 6: SQLite → PostgreSQL Switch (Alembic)

**Current state:** 6 migration files exist, all SQLite-compatible. No batch operations used.

**Migration strategy:** Switch DATABASE_URL to `postgresql+asyncpg://...`. The existing migrations replay cleanly against PostgreSQL because:
- All column types used (String, Integer, BigInteger, Float, DateTime) are standard SQL, supported identically by both dialects
- No SQLite-specific `AUTOINCREMENT` or `CHECK` constraints present
- No SQLite batch operations used

**New migration needed** (single migration for Phase 1 schema additions):
```python
# What the new migration must do:
# 1. Add vehicle_id FK column to drivers table
# 2. Add make (String), model (String), fuel_norm_per_100km (Float) to vehicles table
# 3. Create WebPanelUser table (or use env-based auth — recommended for Phase 1)
```

**DATABASE_URL format for asyncpg:**
```
postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME
```

Railway PostgreSQL addon provides `DATABASE_URL` as `postgresql://...` (sync format). Must transform to `postgresql+asyncpg://...` in config:

```python
# src/core/config.py
class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./data.sqlite3"

    @property
    def async_database_url(self) -> str:
        """Convert Railway's postgresql:// to postgresql+asyncpg://"""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url
```

### Anti-Patterns to Avoid

- **Running Alembic in FastAPI startup event** — decided against; use pre-deploy hook only
- **Polling mode in production** — `Application.builder()` without `.updater(None)` starts polling; this conflicts with Railway's single-port model
- **Storing PicklePersistence on ephemeral container filesystem** — Railway container filesystem is wiped on redeploy; must use Volume
- **boto3 synchronous calls in async context without executor** — will block the event loop
- **Storing JWT secret in code** — must come from `JWT_SECRET_KEY` env var
- **Using @app.on_event("startup")** — deprecated in FastAPI; use lifespan context manager

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom bcrypt wrapper | `pwdlib[bcrypt]` | Correct salt handling, timing-safe compare |
| JWT creation/validation | Custom base64+HMAC | `python-jose` | Algorithm selection, expiry, proper encoding |
| S3/R2 upload | Direct HTTP multipart | `boto3` | Retry logic, credential signing, multipart for large files |
| Alembic async runner | Custom migration script | Existing `alembic/env.py` (already async) | Already handles async engine correctly |
| ConversationHandler state storage | Custom pickle logic | PTB `PicklePersistence` | Handles concurrent updates, flush intervals |

**Key insight:** The existing alembic/env.py already implements the async migration pattern correctly — do not replace it.

---

## Common Pitfalls

### Pitfall 1: Railway DATABASE_URL is postgresql:// not postgresql+asyncpg://

**What goes wrong:** `create_async_engine("postgresql://...")` silently falls back to sync driver or raises `NoSuchModuleError`.

**Why it happens:** Railway PostgreSQL addon provides standard `postgresql://` URL. asyncpg driver requires `postgresql+asyncpg://` scheme.

**How to avoid:** Transform URL in `Settings.async_database_url` property before passing to `create_async_engine`.

**Warning signs:** `ModuleNotFoundError: No module named 'psycopg2'` or `greenlet_spawn has not been called` at startup.

### Pitfall 2: Railway Volume Not Mounted in Pre-Deploy

**What goes wrong:** If pre-deploy tries to write pickle file or read from `/data`, it fails silently — pre-deploy runs in a container without volumes mounted.

**Why it happens:** Railway docs confirm volumes are runtime-only. Pre-deploy is a separate container build step.

**How to avoid:** Only Alembic (database operations) in pre-deploy. PicklePersistence reads/writes happen only during app runtime.

**Warning signs:** Pre-deploy command works but FSM state is lost on redeploy even with volume attached.

### Pitfall 3: ConversationHandler Without name= Silently Not Persisted

**What goes wrong:** Bot restarts lose all in-progress conversation states even when PicklePersistence is configured.

**Why it happens:** PTB only persists ConversationHandlers that have both `name=` AND `persistent=True`. Handlers without name are skipped silently.

**How to avoid:** All 5 existing ConversationHandlers in the project need `name=` and `persistent=True`. Check `get_trip_conversation_handler()`, `get_expense_conversation_handler()`, `get_location_conversation_handler()`, `get_trip_closing_conversation_handler()` — each factory function must pass these params.

**Warning signs:** `context.user_data` persists but conversation state (which step user is on) resets to beginning.

### Pitfall 4: Driver-Vehicle Link Missing in receive_vehicle()

**What goes wrong:** Registration flow creates Driver and Vehicle in separate DB calls with no FK relationship. REG-03 (web panel showing driver-truck pairs) has nothing to join on.

**Why it happens:** Comment in code explicitly says "MVP just registers them" without linking. The `Driver` model has no `vehicle_id` column.

**How to avoid:** In Phase 1, add `vehicle_id` FK to `Driver`, update `receive_vehicle()` to set `driver.vehicle_id = vehicle.id` before commit.

**Warning signs:** Web panel query `Driver.vehicle` returns None for all drivers.

### Pitfall 5: Alembic env.py Reads DATABASE_URL with +aiosqlite scheme During Pre-Deploy

**What goes wrong:** `alembic upgrade head` in pre-deploy tries to connect using asyncpg (async driver) which works; but if DATABASE_URL somehow has `sqlite+aiosqlite://` (wrong env), migrations run against SQLite instead of PostgreSQL.

**Why it happens:** `get_url()` in `alembic/env.py` calls `settings.DATABASE_URL` directly, which reads from env var.

**How to avoid:** Ensure Railway has `DATABASE_URL=${{Postgres.DATABASE_URL}}` in service environment variables. Verify with `railway variables` CLI after setup.

### Pitfall 6: boto3 Blocking the Event Loop

**What goes wrong:** Photo upload hangs all concurrent bot requests for several seconds.

**Why it happens:** boto3 is synchronous; calling it directly in an `async def` handler blocks the asyncio event loop.

**How to avoid:** Wrap all boto3 calls in `asyncio.get_event_loop().run_in_executor(None, sync_fn)` or use `anyio.to_thread.run_sync()`.

### Pitfall 7: Webhook URL Must Be HTTPS

**What goes wrong:** `set_webhook()` raises error, Telegram refuses to register webhook.

**Why it happens:** Telegram requires HTTPS for webhook endpoints. Railway provides HTTPS by default on `*.up.railway.app` domains.

**How to avoid:** Use Railway's auto-generated HTTPS URL as `WEBHOOK_URL`. Do not use localhost or HTTP.

---

## Code Examples

### Config with All Phase 1 Settings

```python
# src/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Existing
    TELEGRAM_BOT_TOKEN: str = "replace_me"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data.sqlite3"

    # New in Phase 1
    WEBHOOK_URL: str = ""                    # e.g. https://myapp.up.railway.app

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "freight-tms-photos"

    # JWT Auth
    JWT_SECRET_KEY: str = "change-in-production"  # 32+ random bytes
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 hours

    # Admin credentials (env-based for Phase 1)
    ADMIN_USERNAME: str = "dispatcher"
    ADMIN_PASSWORD_HASH: str = ""  # Generate with: pwdlib hash "password"

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

### New Alembic Migration (Phase 1 Schema)

```python
# alembic/versions/XXXX_phase1_add_vehicle_link_and_fields.py
def upgrade() -> None:
    # Add vehicle link to drivers
    op.add_column('drivers',
        sa.Column('vehicle_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_drivers_vehicle_id', 'drivers', 'vehicles',
        ['vehicle_id'], ['id']
    )
    # Add vehicle detail fields
    op.add_column('vehicles', sa.Column('make', sa.String(), nullable=True))
    op.add_column('vehicles', sa.Column('model', sa.String(), nullable=True))
    op.add_column('vehicles',
        sa.Column('fuel_norm_per_100km', sa.Float(), nullable=True)
    )
```

### Railway Volume Environment Variable

```python
# Access via env var set by Railway automatically
import os
VOLUME_MOUNT = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/data")
PERSISTENCE_FILE = Path(VOLUME_MOUNT) / "bot_persistence.pkl"
```

### Web Panel Dispatcher Route (REG-03)

```python
# src/web/panel.py
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from src.db.database import async_session
from src.db.models import Driver, Vehicle
from src.web.auth import get_current_user_from_cookie

router = APIRouter(prefix="/panel")
templates = Jinja2Templates(directory="src/web/templates")

@router.get("/drivers", response_class=HTMLResponse)
async def list_drivers(
    request: Request,
    current_user=Depends(get_current_user_from_cookie)
):
    async with async_session() as session:
        result = await session.execute(
            select(Driver, Vehicle)
            .outerjoin(Vehicle, Driver.vehicle_id == Vehicle.id)
            .order_by(Driver.created_at.desc())
        )
        rows = result.all()
    return templates.TemplateResponse(
        "drivers.html",
        {"request": request, "rows": rows, "user": current_user}
    )
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `@app.on_event("startup")` | `lifespan=` context manager | Old style deprecated in FastAPI 0.95+; lifespan is the correct pattern |
| passlib[bcrypt] | pwdlib[bcrypt] | passlib is unmaintained; pwdlib is actively maintained drop-in |
| Polling (run_bot.py) | Webhook (FastAPI POST /telegram) | Polling requires separate process; webhook integrates with FastAPI in one process |
| SQLite + aiosqlite | PostgreSQL + asyncpg | Production-grade; asyncpg already in requirements.txt |

**Deprecated/outdated in this project:**
- `src/main.py` using `@app.on_event` — deprecated, must convert to lifespan
- `run_bot.py` polling runner — replaced by webhook in Phase 1
- `data.sqlite3` file — replaced by Railway PostgreSQL addon

---

## Parallelization Map (for Planner)

Tasks that can be worked in parallel after the database migration is in place:

```
[PLAN A] Database & Config Setup
   ├── Switch DATABASE_URL to postgresql+asyncpg
   ├── Extend Settings with new fields
   ├── Write new Alembic migration (vehicle_id + vehicle fields)
   └── Test migration locally with docker-compose postgres
   MUST COMPLETE BEFORE: [PLAN B], [PLAN C], [PLAN D]

[PLAN B] FastAPI + PTB Webhook Integration
   ├── Rewrite src/main.py with lifespan pattern
   ├── Add /telegram POST route
   └── Wire all handlers from bot_app.py
   PARALLEL WITH: [PLAN C], [PLAN D]
   DEPENDS ON: [PLAN A]

[PLAN C] FSM Persistence
   ├── Add PicklePersistence to Application.builder()
   ├── Add name + persistent=True to all 5 ConversationHandlers
   ├── Add Railway Volume (UI step) + set mount path /data
   └── Fix receive_vehicle() to link driver.vehicle_id
   PARALLEL WITH: [PLAN B], [PLAN D]
   DEPENDS ON: [PLAN A]

[PLAN D] Cloudflare R2 Integration
   ├── Create R2 bucket (Cloudflare dashboard step)
   ├── Create R2 API token (Cloudflare dashboard step)
   ├── Write src/services/r2.py upload helper
   └── Wire into expense_flow.py photo upload
   PARALLEL WITH: [PLAN B], [PLAN C]
   DEPENDS ON: [PLAN A] (env vars must exist)

[PLAN E] Web Panel + JWT Auth
   ├── Create src/web/auth.py (JWT, pwdlib)
   ├── Create /login POST + GET routes
   ├── Create /panel/drivers GET (list + vehicle join)
   ├── Create /panel/vehicles/:id GET/POST (edit form)
   └── Create Jinja2 templates (login, drivers, vehicle edit)
   PARALLEL WITH: [PLAN B], [PLAN C], [PLAN D]
   DEPENDS ON: [PLAN A]

[PLAN F] Railway Deployment Config
   ├── Write railway.toml (preDeployCommand + startCommand)
   ├── Set all env vars in Railway dashboard
   └── Smoke test webhook + redeploy persistence
   DEPENDS ON: [PLAN B], [PLAN C], [PLAN D], [PLAN E]
```

---

## Open Questions

1. **Multiple admin users vs env-based for Phase 1**
   - What we know: INFRA-05 requires JWT with roles dispatcher/director
   - What's unclear: Is one set of credentials (env vars) sufficient for Phase 1, or do dispatchers and directors need separate logins?
   - Recommendation: Use env-based credentials for Phase 1 (ADMIN_USERNAME + ADMIN_PASSWORD_HASH per role). DB-backed user table is more appropriate for a later phase when multi-user is needed.

2. **Existing ConversationHandlers' factory functions — do they already have name/persistent?**
   - What we know: `get_trip_conversation_handler()`, `get_expense_conversation_handler()`, etc. were not fully read
   - What's unclear: Whether these factory functions already pass `name=` and `persistent=True`
   - Recommendation: During implementation, read all 4 antigravity module factory functions and add `name=` + `persistent=True` if missing.

3. **Photo storage for expense_flow.py — currently stores Telegram file_id, not R2 URL**
   - What we know: `photo_file_id` column in Expense stores Telegram's internal file ID
   - What's unclear: INFRA-03 says "photos stored durably in R2" — does this require changing expense_flow.py to download photo from Telegram and upload to R2?
   - Recommendation: Yes — Phase 1 success criterion 3 requires photos in R2. expense_flow.py must download photo bytes from Telegram API then upload to R2, storing the R2 URL (not Telegram file_id) in a new `photo_r2_url` column.

4. **WEBHOOK_URL value on Railway**
   - What we know: Railway provides auto-generated URL like `https://freight-tms-production.up.railway.app`
   - What's unclear: Must be set as env var before first deploy
   - Recommendation: Set WEBHOOK_URL as Railway service environment variable referencing `$RAILWAY_STATIC_URL` or the custom domain.

---

## Sources

### Primary (HIGH confidence)
- developers.cloudflare.com/r2/examples/aws/boto3/ — boto3 R2 configuration and upload pattern
- docs.python-telegram-bot.org/en/stable/telegram.ext.picklepersistence.html — PicklePersistence API
- github.com/python-telegram-bot/python-telegram-bot/wiki/Making-your-bot-persistent — ConversationHandler persistence requirements
- docs.railway.com/volumes — Volume mount path, runtime-only limitation
- docs.railway.com/guides/config-as-code — railway.toml preDeployCommand syntax
- Codebase direct inspection (bot_app.py, models.py, crud.py, alembic/versions/) — brownfield inventory

### Secondary (MEDIUM confidence)
- freecodecamp.org/news/how-to-build-and-deploy-python-telegram-bot-v20-webhooks/ — FastAPI lifespan + PTB webhook pattern (verified against PTB docs)
- docs.railway.com/databases/postgresql — PostgreSQL env vars (DATABASE_URL format not fully specified; asyncpg transformation derived from SQLAlchemy docs)
- francoisvoron.com/blog/introducing-pwdlib — pwdlib usage pattern
- fastapitutorial.com/blog/fastapi-jwt-httponly-cookie/ — JWT httponly cookie pattern for Jinja2

### Tertiary (LOW confidence — flag for validation)
- Railway preDeployCommand array vs string format: sources say array `["alembic", "upgrade", "head"]` is correct; confirm by checking actual Railway dashboard behavior on first deploy

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project or standard well-documented choices
- Architecture (PTB webhook + lifespan): HIGH — multiple official sources confirm pattern
- Alembic migration path (SQLite→PG): HIGH — no dialect-specific syntax in existing migrations
- Railway Volume + PicklePersistence: HIGH — Railway docs explicitly confirm volume lifecycle
- R2 boto3 pattern: HIGH — official Cloudflare docs
- JWT cookie pattern: MEDIUM — well-established but not verified against latest FastAPI version
- Pitfalls: HIGH — confirmed via official docs and direct code inspection

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable libraries; Railway config syntax may change)
