# Architecture: Freight TMS MVP

**Domain:** Freight Transportation Management System
**Researched:** 2026-03-08
**Overall confidence:** HIGH (FastAPI/PTB patterns) / MEDIUM (TMS-specific data model)

---

## System Overview

The Freight TMS is a single-repository, single-deployment Python application that combines:

1. **FastAPI backend** — REST API serving both the Telegram bot and the web dashboard
2. **python-telegram-bot (PTB v20)** — async Telegram bot mounted inside the FastAPI process via webhook
3. **PostgreSQL** — single shared database for all components
4. **Jinja2 + HTMX** — server-side rendered web dashboard (no separate frontend build process)
5. **Railway** — PaaS host, two services: the app and the managed PostgreSQL addon

The bot and the web app share the same database directly — no HTTP API boundary between them. This is the right choice for MVP: simpler to reason about, no network hops, no auth duplication, no serialization overhead.

```
┌─────────────────────────────────────────────────────────────┐
│                      Railway Project                        │
│                                                             │
│  ┌──────────────────────────────────────┐  ┌─────────────┐ │
│  │         FastAPI Application          │  │  PostgreSQL  │ │
│  │  (single process, single Railway     │  │  (Railway    │ │
│  │   service)                           │  │   addon)     │ │
│  │                                      │  └──────┬──────┘ │
│  │  ┌─────────────┐  ┌───────────────┐  │         │        │
│  │  │ Telegram    │  │  Web Dashboard│  │         │        │
│  │  │ Bot Handler │  │  (Jinja2+HTMX)│  │         │        │
│  │  │ (PTB v20    │  │               │  │         │        │
│  │  │  webhook)   │  │  /dispatcher/ │  │         │        │
│  │  └──────┬──────┘  │  /director/   │  │         │        │
│  │         │         └───────┬───────┘  │         │        │
│  │         └────────────┬───┘           │         │        │
│  │                      ▼               │         │        │
│  │              Service Layer           │         │        │
│  │         (shared business logic)      │         │        │
│  │                      │               │         │        │
│  │              SQLAlchemy 2.0          ├─────────┘        │
│  │              (async, asyncpg)        │                   │
│  └──────────────────────────────────────┘                   │
│                                                             │
│  External: Telegram Servers ──────► POST /webhook/telegram  │
│  External: Browser ──────────────► GET/POST /dispatcher/*   │
│  External: Browser ──────────────► GET/POST /director/*     │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Model

### Design Principles

- **Trip is the unit of business.** Every expense, location ping, and document attaches to a trip.
- **Soft deletes only.** Use `is_active` / `deleted_at` flags — never hard-delete operational data.
- **Audit columns on every table.** `created_at`, `updated_at` minimum.
- **No PostGIS for MVP.** Store `latitude FLOAT, longitude FLOAT` as plain columns. PostGIS adds operational complexity (extension must be enabled, Railway supports it but requires setup). Plain lat/lon is sufficient for displaying markers on a Leaflet map. Migrate to PostGIS if spatial queries are needed later.
- **Currency handling.** Store `amount_original NUMERIC(12,2)`, `currency_code CHAR(3)`, `amount_usd NUMERIC(12,2)`. Do FX conversion at submission time using a simple rate table or an FX API call. Don't defer this to reporting.

---

### Entity Map

```
trucks ──< trips >── drivers
            │
            ├──< expenses (fuel, per_diem, fine, other)
            │        └── expense_photos
            │
            ├──< location_pings
            │
            └──< trip_documents (CMR, etc.)

drivers ──< expenses
trucks ──< fuel_norms

users (dispatcher, director) — separate from drivers
```

---

### Tables

#### `trucks`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
plate_number    VARCHAR(20) NOT NULL UNIQUE       -- "001 AA 01"
model           VARCHAR(100)                      -- "Volvo FH 500"
year            SMALLINT
fuel_norm_l100km  NUMERIC(5,2)                   -- L/100km benchmark
status          ENUM('active', 'maintenance', 'inactive') DEFAULT 'active'
notes           TEXT
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

#### `drivers`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
telegram_id     BIGINT UNIQUE NOT NULL            -- Telegram user_id, used for bot auth
telegram_handle VARCHAR(100)                      -- @username, optional
full_name       VARCHAR(200) NOT NULL
phone           VARCHAR(30)
license_number  VARCHAR(50)
status          ENUM('active', 'inactive') DEFAULT 'active'
current_truck_id UUID REFERENCES trucks(id)      -- soft assignment, nullable
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```
Note: Driver registration via bot sets `telegram_id`. This is the auth key — no password, no JWT for bot users. Bot handlers look up driver by `telegram_id` from `message.from_user.id`.

#### `trips`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
truck_id        UUID NOT NULL REFERENCES trucks(id)
driver_id       UUID NOT NULL REFERENCES drivers(id)
status          ENUM('planned', 'active', 'completed', 'cancelled') DEFAULT 'planned'

-- Route info
origin_city     VARCHAR(200)
destination_city VARCHAR(200)
cargo_description TEXT
cargo_weight_kg NUMERIC(10,2)
client_name     VARCHAR(200)

-- Timing
planned_departure TIMESTAMPTZ
actual_departure  TIMESTAMPTZ
planned_arrival   TIMESTAMPTZ
actual_arrival    TIMESTAMPTZ

-- Financials (denormalized for fast reporting)
total_fuel_cost_usd      NUMERIC(12,2) DEFAULT 0
total_per_diem_usd       NUMERIC(12,2) DEFAULT 0
total_fines_usd          NUMERIC(12,2) DEFAULT 0
total_other_expenses_usd NUMERIC(12,2) DEFAULT 0
revenue_usd              NUMERIC(12,2)           -- optional: dispatcher can enter

-- Odometer
odometer_start  INTEGER                           -- km at trip start
odometer_end    INTEGER                           -- km at trip end

notes           TEXT
created_by_user_id UUID REFERENCES users(id)     -- which dispatcher created it
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

#### `expenses`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
trip_id         UUID REFERENCES trips(id)         -- nullable if submitted outside trip context
driver_id       UUID NOT NULL REFERENCES drivers(id)
truck_id        UUID REFERENCES trucks(id)

category        ENUM('fuel', 'per_diem', 'fine', 'repair', 'toll', 'border_fee', 'other')
status          ENUM('pending', 'approved', 'rejected') DEFAULT 'pending'

-- Amounts
amount_original    NUMERIC(12,2) NOT NULL
currency_code      CHAR(3) NOT NULL DEFAULT 'USD'
amount_usd         NUMERIC(12,2)                 -- converted at submission time
exchange_rate      NUMERIC(10,6)

-- Context (category-specific)
description     TEXT
country_code    CHAR(2)                           -- ISO 3166-1 alpha-2, for per diem
city            VARCHAR(200)

-- Fuel-specific fields (null for non-fuel)
fuel_liters        NUMERIC(8,2)
odometer_reading   INTEGER
fuel_station_name  VARCHAR(200)
fuel_consumption_l100km NUMERIC(6,2)             -- calculated at submission

-- Anomaly detection
anomaly_flag    BOOLEAN DEFAULT FALSE
anomaly_reason  TEXT                              -- "42L/100km vs norm 35L/100km"

-- Approval
approved_by_user_id UUID REFERENCES users(id)
approved_at     TIMESTAMPTZ
rejection_reason TEXT

-- Submission metadata
submitted_via   ENUM('telegram', 'web') DEFAULT 'telegram'
submitted_at    TIMESTAMPTZ DEFAULT now()
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

#### `expense_photos`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
expense_id      UUID NOT NULL REFERENCES expenses(id) ON DELETE CASCADE
telegram_file_id VARCHAR(200)                    -- Telegram file_id for re-download
storage_path    VARCHAR(500)                      -- local path or S3 key after download
file_size_bytes INTEGER
uploaded_at     TIMESTAMPTZ DEFAULT now()
```
Note: Download photo from Telegram and store server-side. `telegram_file_id` expires eventually; `storage_path` is the durable copy.

#### `location_pings`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
trip_id         UUID REFERENCES trips(id)
driver_id       UUID NOT NULL REFERENCES drivers(id)
truck_id        UUID REFERENCES trucks(id)
latitude        DOUBLE PRECISION NOT NULL
longitude       DOUBLE PRECISION NOT NULL
accuracy_meters REAL
source          ENUM('telegram_manual', 'telegram_live', 'api') DEFAULT 'telegram_manual'
recorded_at     TIMESTAMPTZ DEFAULT now()         -- when location was captured
created_at      TIMESTAMPTZ DEFAULT now()
```
Index: `(truck_id, recorded_at DESC)` for "last known position" queries.
Index: `(trip_id, recorded_at)` for trip path rendering.

#### `trip_documents`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
trip_id         UUID NOT NULL REFERENCES trips(id)
document_type   ENUM('cmr', 'invoice', 'customs', 'other')
filename        VARCHAR(300)
storage_path    VARCHAR(500)
telegram_file_id VARCHAR(200)
uploaded_by_driver_id UUID REFERENCES drivers(id)
uploaded_by_user_id   UUID REFERENCES users(id)
uploaded_at     TIMESTAMPTZ DEFAULT now()
```

#### `users`
Web-only users (dispatchers and directors). Drivers use the bot with `telegram_id` auth.
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
email           VARCHAR(200) UNIQUE NOT NULL
password_hash   VARCHAR(200) NOT NULL             -- bcrypt
full_name       VARCHAR(200)
role            ENUM('dispatcher', 'director', 'admin') NOT NULL
is_active       BOOLEAN DEFAULT TRUE
last_login_at   TIMESTAMPTZ
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

#### `alert_log`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
alert_type      ENUM('fuel_anomaly', 'odometer_jump', 'duplicate_expense', 'other')
severity        ENUM('info', 'warning', 'critical') DEFAULT 'warning'
truck_id        UUID REFERENCES trucks(id)
driver_id       UUID REFERENCES drivers(id)
expense_id      UUID REFERENCES expenses(id)
message         TEXT NOT NULL
acknowledged_at TIMESTAMPTZ                       -- NULL = unread
acknowledged_by UUID REFERENCES users(id)
created_at      TIMESTAMPTZ DEFAULT now()
```

---

### Key Relationships Summary

```
trucks (1) ──< (many) trips
drivers (1) ──< (many) trips
trips (1) ──< (many) expenses
expenses (1) ──< (many) expense_photos
trips (1) ──< (many) location_pings
trips (1) ──< (many) trip_documents
users (1) ──< (many) expenses [approved_by]
users (1) ──< (many) trips [created_by]
```

---

## Component Architecture

### Directory Structure

```
freight-tms/
├── src/
│   ├── main.py                    # FastAPI app factory, lifespan, router registration
│   ├── database.py                # Async engine, session factory, Base
│   ├── config.py                  # Settings via pydantic-settings (.env)
│   ├── dependencies.py            # Shared FastAPI dependencies (get_db, get_current_user)
│   │
│   ├── bot/                       # Telegram bot — all PTB handlers
│   │   ├── __init__.py
│   │   ├── application.py         # PTB Application builder, webhook setup
│   │   ├── handlers/
│   │   │   ├── registration.py    # /start, driver registration flow
│   │   │   ├── expenses.py        # Expense submission conversations
│   │   │   ├── location.py        # Location sharing handler
│   │   │   ├── trip.py            # Trip confirmation, status commands
│   │   │   └── common.py          # Error handler, fallback handler
│   │   └── keyboards.py           # InlineKeyboard builders
│   │
│   ├── web/                       # Web dashboard — Jinja2 + HTMX
│   │   ├── __init__.py
│   │   ├── auth/
│   │   │   ├── router.py          # GET/POST /login, /logout
│   │   │   └── service.py         # Password verify, session token
│   │   ├── dispatcher/
│   │   │   ├── router.py          # All /dispatcher/* routes
│   │   │   ├── service.py         # Business logic for dispatcher views
│   │   │   └── templates/
│   │   │       ├── layout.html
│   │   │       ├── dashboard.html
│   │   │       ├── trips.html
│   │   │       ├── expense_queue.html
│   │   │       └── map.html
│   │   └── director/
│   │       ├── router.py          # All /director/* routes
│   │       ├── service.py
│   │       └── templates/
│   │           ├── layout.html
│   │           ├── overview.html
│   │           └── reports.html
│   │
│   ├── api/                       # JSON API — for HTMX partial updates and future mobile
│   │   ├── __init__.py
│   │   ├── trucks.py              # CRUD /api/trucks
│   │   ├── drivers.py             # CRUD /api/drivers
│   │   ├── trips.py               # CRUD /api/trips
│   │   ├── expenses.py            # List, approve, reject /api/expenses
│   │   └── locations.py           # GET /api/trucks/{id}/location
│   │
│   ├── services/                  # Shared business logic (used by both bot and web)
│   │   ├── expense_service.py     # Submit expense, run anomaly check, trigger alerts
│   │   ├── trip_service.py        # Create/close trip, calculate totals
│   │   ├── driver_service.py      # Register driver, assign truck
│   │   ├── anomaly_service.py     # Fuel consumption check, odometer validation
│   │   ├── photo_service.py       # Download from Telegram, store locally/S3
│   │   └── notification_service.py # Send Telegram alerts to director/dispatcher
│   │
│   ├── models/                    # SQLAlchemy ORM models (one file per entity)
│   │   ├── __init__.py            # Exports all models (needed for Alembic autogenerate)
│   │   ├── truck.py
│   │   ├── driver.py
│   │   ├── trip.py
│   │   ├── expense.py
│   │   ├── location_ping.py
│   │   ├── trip_document.py
│   │   ├── user.py
│   │   └── alert_log.py
│   │
│   └── schemas/                   # Pydantic v2 schemas (request/response validation)
│       ├── truck.py
│       ├── driver.py
│       ├── trip.py
│       ├── expense.py
│       └── user.py
│
├── alembic/                       # Database migrations
│   ├── env.py
│   └── versions/
│
├── templates/                     # Jinja2 templates (top-level, shared base)
│   └── base.html
│
├── static/                        # CSS, JS, icons
│   ├── css/
│   └── js/
│       ├── htmx.min.js
│       └── leaflet.js
│
├── tests/
│   ├── test_services/
│   └── test_api/
│
├── .env
├── .env.example
├── Dockerfile
├── requirements.txt
└── alembic.ini
```

---

### Telegram Bot — FastAPI Integration

The bot runs inside the FastAPI process using PTB v20's webhook mode. No separate process, no separate port.

```python
# src/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.bot.application import build_bot_application

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: register webhook and start bot
    ptb_app = build_bot_application()
    app.state.bot = ptb_app
    webhook_url = f"{settings.PUBLIC_URL}/webhook/telegram"
    await ptb_app.bot.set_webhook(
        url=webhook_url,
        secret_token=settings.TELEGRAM_WEBHOOK_SECRET
    )
    async with ptb_app:
        await ptb_app.start()
        yield
        await ptb_app.stop()

app = FastAPI(lifespan=lifespan)

# src/bot/webhook_router.py
from fastapi import APIRouter, Request, Response, Header
from telegram import Update

router = APIRouter()

@router.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    # Validate secret token to prevent spoofed requests
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        return Response(status_code=403)

    data = await request.json()
    update = Update.de_json(data, request.app.state.bot.bot)
    await request.app.state.bot.process_update(update)
    return Response(status_code=200)
```

The bot handlers call into `src/services/` directly (same process, same database session). No HTTP round-trips between bot and web — they share the same SQLAlchemy async session factory.

**Confidence:** HIGH — verified against python-telegram-bot v20 official webhook docs and FreeCodeCamp implementation guide.

---

### Web Dashboard — Jinja2 + HTMX

**Recommendation: Jinja2 templates + HTMX, not a SPA framework.**

Rationale:
- Python developers can own the entire stack
- No build pipeline (no npm, no webpack, no node_modules in deployment)
- HTMX delivers dynamic updates (approve/reject expense inline, map marker refresh) without React
- Leaflet.js loads as a static JS file — works fine alongside HTMX
- Server-side render is faster for the first load (no JS bundle hydration)
- Admin dashboards are 95% tables and forms — exactly what Jinja2 excels at

The map view uses Leaflet.js directly in a `<script>` block. Location data is fetched via a JSON endpoint (`GET /api/trucks/locations`) and rendered client-side. HTMX polls this endpoint on an interval to refresh markers without a full page reload.

```html
<!-- Expense approval row — HTMX inline update -->
<tr id="expense-{{ expense.id }}">
  <td>{{ expense.driver.full_name }}</td>
  <td>{{ expense.category }}</td>
  <td>{{ expense.amount_usd }} USD</td>
  <td>
    <button hx-post="/api/expenses/{{ expense.id }}/approve"
            hx-target="#expense-{{ expense.id }}"
            hx-swap="outerHTML">
      Approve
    </button>
    <button hx-post="/api/expenses/{{ expense.id }}/reject"
            hx-target="#expense-{{ expense.id }}"
            hx-swap="outerHTML">
      Reject
    </button>
  </td>
</tr>
```

---

### Service Layer

Services are the only place business logic lives. Both bot handlers and web route handlers call services, never directly querying the DB.

```python
# src/services/expense_service.py

class ExpenseService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def submit_fuel_expense(
        self,
        driver_id: UUID,
        trip_id: UUID | None,
        liters: float,
        odometer: int,
        amount_original: Decimal,
        currency_code: str,
        photo_file_id: str,
    ) -> Expense:
        # 1. Get driver's current truck
        # 2. Get truck's fuel norm
        # 3. Calculate consumption vs previous odometer reading
        # 4. Run anomaly check
        # 5. Convert currency
        # 6. Create expense record
        # 7. Queue photo download (background task)
        # 8. Fire alert if anomaly detected
        ...
```

This pattern keeps bot handler code minimal (conversation logic only) and makes services testable without HTTP.

---

## Integration Points

### 1. Telegram → FastAPI (Webhook)
- **Direction:** Telegram servers → `POST /webhook/telegram`
- **Auth:** Secret token header (`X-Telegram-Bot-Api-Secret-Token`)
- **Format:** Telegram `Update` JSON object
- **Latency requirement:** Must respond within 60 seconds (Telegram timeout)
- **Risk:** Railway cold starts on free plan can miss webhook deliveries

### 2. Bot Handler → Service Layer
- **Direction:** In-process function call
- **Auth:** None (same process)
- **Session management:** Each handler gets its own `AsyncSession` via dependency injection or direct instantiation
- **Risk:** Long-running bot conversations hold no state between messages — must persist conversation state to DB or use PTB's built-in `ConversationHandler` (which is in-memory and lost on restart)

### 3. Web Route Handler → Service Layer
- **Direction:** In-process function call
- **Auth:** Session cookie / JWT checked in FastAPI dependency
- **Session management:** FastAPI `Depends(get_db)` injects `AsyncSession`

### 4. Service Layer → PostgreSQL
- **Driver:** `asyncpg` via SQLAlchemy 2.0 async engine
- **Connection pool:** `create_async_engine(..., pool_size=10, max_overflow=5)`
- **Risk:** Railway PostgreSQL connection limits — stay under 20 concurrent connections on starter plan

### 5. Service Layer → Telegram (Outbound Alerts)
- **Direction:** FastAPI app → Telegram Bot API → user's Telegram
- **Use case:** Anomaly alert to director, approval confirmation to driver
- **Method:** `await bot.send_message(chat_id=..., text=...)`
- **Access:** `request.app.state.bot.bot` inside web handlers; passed directly in bot handlers

### 6. Photo Download → Storage
- **Direction:** Service calls `bot.get_file(file_id)` → downloads → writes to local disk or object storage
- **MVP option:** Write to local Railway disk (`/data/` persistent volume) — simple, no external dependency
- **Scale option:** S3-compatible (Cloudflare R2 / AWS S3) — needed if Railway service restarts wipe disk

### 7. Web Dashboard → Map Data
- **Direction:** Browser → `GET /api/trucks/locations` (JSON)
- **Format:** `[{"truck_id": "...", "plate": "...", "lat": 51.5, "lon": 12.3, "last_seen": "..."}]`
- **Polling:** HTMX `hx-trigger="every 30s"` on the map page
- **Rendering:** Leaflet.js client-side marker placement

---

## Recommended Build Order

### Phase 0: Infrastructure (1-2 days)
Everything else blocks on this. Do it first, do it once.

1. FastAPI project scaffold (directory structure, `config.py`, `database.py`, `main.py`)
2. SQLAlchemy 2.0 async setup with asyncpg
3. Alembic configured for async — first migration creating all tables
4. Railway project created: app service + PostgreSQL addon
5. Dockerfile + Railway deploy confirmed working
6. PTB v20 webhook mounted in FastAPI lifespan — `/webhook/telegram` responding
7. Basic driver registration conversation (proves end-to-end: Telegram → webhook → DB → response)

**Gate:** Driver can `/start`, complete registration, and be found in the database.

---

### Phase 1: Expense Control (core value, week 1-2)

Build expense submission first — it's the most validated flow from the existing fuel bot.

1. `ExpenseService.submit_fuel_expense()` with anomaly detection
2. Bot: fuel expense conversation (liters → odometer → photo → station → confirm)
3. Bot: per diem conversation (amount → currency → city → confirm)
4. Bot: fine conversation (photo → amount → currency → reason → confirm)
5. Bot: "other expense" conversation (category → amount → photo → confirm)
6. `AnomalyService.check_fuel_consumption()` — compare vs truck norm, write `alert_log`
7. `NotificationService.send_alert()` — Telegram message to director on anomaly
8. Web: `POST /auth/login` — dispatcher/director login with session cookie
9. Web: expense approval queue (`/dispatcher/expenses`) — list pending, HTMX approve/reject

**Gate:** Driver submits fuel expense with photo, dispatcher approves it, director receives anomaly alert.

---

### Phase 2: Trip Management (week 2-3)

Trips make all historical data queryable and attach expenses to a meaningful unit.

1. Web: trip creation form (`/dispatcher/trips/new`) — truck, driver, route, cargo
2. Web: trip list and detail views
3. `TripService.assign_trip()` — notify driver via Telegram bot on assignment
4. Bot: trip confirmation command (`/trip` shows current assignment)
5. Bot: trip start (sets `actual_departure`, links subsequent expenses to trip)
6. Bot: trip end (sets `actual_arrival`, triggers trip cost rollup)
7. `TripService.calculate_totals()` — update denormalized cost columns on trip
8. Web: trip detail with expense breakdown, profitability if revenue entered

**Gate:** Dispatcher creates trip, driver confirms, expenses attach to trip, director sees trip cost.

---

### Phase 3: Location and Map (week 3-4)

Location is independent of expense/trip flow — can be built in parallel.

1. Bot: `/location` command — driver sends Telegram native location → `location_pings` table
2. API endpoint: `GET /api/trucks/locations` → returns last ping per truck
3. Web: dispatcher map view (`/dispatcher/map`) — Leaflet.js + marker per truck
4. HTMX polling: refresh markers every 30 seconds
5. Trip document upload via bot (CMR, etc.) → `trip_documents` table

**Gate:** Dispatcher sees all trucks on map with last-known position timestamps.

---

### Phase 4: Director Dashboard and Reporting (week 4-5)

1. Web: director overview (`/director/overview`) — KPI tiles: active trucks, pending expenses, anomalies today
2. Web: expense report by truck/period — filterable date range
3. Web: anomaly log view — table of `alert_log` with acknowledge button
4. Web: CSV export — `GET /director/export/expenses.csv?from=&to=&truck_id=`
5. Per-truck profitability view (revenue vs expenses per trip)

**Gate:** Director logs in, sees current costs, exports CSV for accountant.

---

### Defer to Phase 5+

- Background GPS tracking (requires native mobile or Telegram Live Location — not bot-native)
- Multi-currency per diem rate automation (country → rate table)
- Route benchmarking (needs 3+ months of data)
- Driver balance ledger (requires payment tracking)
- Fuel card integration

---

## Railway Deployment Notes

### Architecture on Railway

```
Railway Project: freight-tms
├── Service: app          (FastAPI + Bot — single process)
│   ├── Dockerfile-based deploy
│   ├── PORT=8000 (Railway sets $PORT)
│   ├── Environment variables: DATABASE_URL, BOT_TOKEN, etc.
│   └── Public URL: assigned by Railway (needed for webhook)
│
└── Service: PostgreSQL   (Railway managed addon)
    └── DATABASE_URL injected automatically into app service
```

**Single app service is correct for MVP.** The bot and web dashboard share the same process, same port, same database connection pool. No need for separate bot service or worker service.

### Why Single Service

- Railway charges per service resource — one service minimizes cost
- No inter-service networking complexity
- Logs are unified (one place to look)
- PTB v20 webhook mode runs inside FastAPI — does not need a separate process
- Scale consideration: 100 drivers is not high traffic. A single Railway instance handles it.

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run Alembic migrations then start server
CMD alembic upgrade head && \
    uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Run `alembic upgrade head` as part of CMD (not as a separate Railway command) so migrations run on every deploy before traffic is accepted.

### Environment Variables on Railway

```
# Required
BOT_TOKEN=                    # From @BotFather
DATABASE_URL=                 # Auto-set by Railway PostgreSQL addon
PUBLIC_URL=                   # Railway app URL — needed to register webhook
                              # e.g. https://freight-tms-production.up.railway.app
TELEGRAM_WEBHOOK_SECRET=      # Random 32+ char string for webhook auth
SECRET_KEY=                   # FastAPI session encryption key

# Optional
DIRECTOR_TELEGRAM_ID=         # Telegram user_id of director for alerts
FUEL_ANOMALY_THRESHOLD=10     # % over norm before alert fires
FX_API_KEY=                   # If using external FX rate API
```

### Persistent File Storage

Railway services have an ephemeral filesystem by default — files written to disk are lost on restart.

Options for photo storage:
1. **Railway Volume (MVP):** Attach a Railway Volume to the app service. Persists across restarts. Free tier: 1GB. Sufficient for MVP. Mount at `/data/photos/`.
2. **Cloudflare R2 (Scale):** S3-compatible, generous free tier (10GB), no egress fees. Switch when photo volume grows.

For MVP, use Railway Volume. `photo_service.py` writes to `/data/photos/{expense_id}/{filename}`. Serve photos via a FastAPI static route or a signed URL endpoint.

### Cold Start / Webhook Reliability

PTB sets the webhook on startup. If Railway restarts the service (deploy, crash), the webhook URL stays the same — Telegram will resume delivering to the existing URL. No action needed.

Risk: Railway free plan may sleep services after inactivity. Upgrade to Railway Hobby plan ($5/month) to avoid sleeping. The bot will miss messages while sleeping.

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| FastAPI app structure | HIGH | Official FastAPI docs + well-validated community patterns |
| PTB v20 webhook in FastAPI lifespan | HIGH | Verified via official PTB docs and FreeCodeCamp guide |
| Data model (core entities) | MEDIUM | Standard TMS entities, but fuel norm and anomaly fields are domain-reasoned |
| No PostGIS for MVP | HIGH | PostGIS adds operational cost without benefit for marker display |
| Jinja2+HTMX over SPA | MEDIUM | Appropriate for team of Python devs; disadvantage if frontend complexity grows |
| Railway single-service | HIGH | Confirmed Railway supports FastAPI + PostgreSQL addon pattern |
| Railway Volume for photos | MEDIUM | Railway Volume exists and is documented; behavior under deploy needs validation |
| Async SQLAlchemy + Alembic | HIGH | Well-documented pattern, multiple production references verified |

---

## Sources

- [python-telegram-bot v20 Webhook Guide — FreeCodeCamp](https://www.freecodecamp.org/news/how-to-build-and-deploy-python-telegram-bot-v20-webhooks/) — HIGH confidence
- [FastAPI Best Practices — zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) — HIGH confidence (5k+ stars, widely referenced)
- [FastAPI Bigger Applications — Official Docs](https://fastapi.tiangolo.com/tutorial/bigger-applications/) — HIGH confidence
- [Railway FastAPI Deployment Guide](https://docs.railway.com/guides/fastapi) — HIGH confidence (official)
- [Async SQLAlchemy 2.0 + Alembic + FastAPI — Berk Karaal](https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/) — HIGH confidence (2024, verified)
- [FastAPI + HTMX Real-Time Dashboards — Medium/CodeX](https://medium.com/codex/building-real-time-dashboards-with-fastapi-and-htmx-01ea458673cb) — MEDIUM confidence
- [Hyperleaflet — HTMX-Compatible Leaflet](https://github.com/cemrehancavdar/hyperleaflet) — MEDIUM confidence (archived but documented)
- [Application Initialization — Telegram Bot AI Integration Guide](https://aotegaliyev.github.io/telegrambot-ai-integration-guide/app-guide/) — MEDIUM confidence
