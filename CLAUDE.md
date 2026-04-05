# Golden Bridge Logistics — TMS

## Company & Product

Transport Management System for **Golden Bridge Logistics** — international freight carrier operating ~45 drivers and 50+ trucks on cross-border routes across Central Asia and CIS.

**Primary routes:**
- Khorgos (CN/KZ border) → Almaty → Moscow
- Khorgos → Almaty → Tashkent
- Almaty → Bishkek, Astana (domestic KZ)
- Seasonal: Turkey (Mersin), Georgia (Poti) via ferry/overland

**Key entities:** Trip, Driver, Vehicle, Cargo, Waybill (CMR/TIR), Expense, FuelRecord, Geofence, DriverRequest

## Stack

- **Backend:** Python 3.11, FastAPI, async everywhere
- **Database:** PostgreSQL (asyncpg), SQLAlchemy 2.0 ORM, Alembic migrations
- **Frontend:** Jinja2 + HTMX web panel (dispatcher/director), PWA mobile app (drivers)
- **Integrations:** Telegram bot (python-telegram-bot v22+, webhook mode), Cloudflare R2 (document/photo storage)
- **Deployment:** Railway (single-process: FastAPI + PTB webhook via lifespan context manager)

## Architecture

```
src/
  core/config.py          — Settings (pydantic-settings), async_database_url property
  db/
    database.py           — async engine, async_session factory
    models.py             — SQLAlchemy ORM models (all entities)
    crud.py               — DB query helpers
  bot/bot_app.py          — Telegram bot: register_handlers(), create_bot_app()
  services/
    r2.py                 — Cloudflare R2 upload (boto3, run_in_executor)
    fuel_antifraud.py     — Fuel anomaly detection
    maintenance.py        — Predictive maintenance calculations
  web/
    panel.py              — Dispatcher panel routes (/panel/*)
    director.py           — Analytics dashboard (/panel/director)
    driver_app.py         — Driver PWA routes (/app/*)
    auth.py               — JWT auth, password hashing (pwdlib[bcrypt])
    templates/            — Jinja2 templates (panel + mobile)
  main.py                 — FastAPI app, lifespan, /telegram webhook
antigravity_modules/      — PTB ConversationHandlers (trip, expense, location, closing)
alembic/                  — DB migrations (Railway preDeployCommand, NOT in app startup)
```

## Critical Rules

### Database
- **ALWAYS** use `settings.async_database_url` (not `settings.DATABASE_URL`) — property auto-converts `postgresql://` → `postgresql+asyncpg://`
- Alembic migrations run via Railway `preDeployCommand`, **never** inside FastAPI startup
- New columns = new Alembic migration: `alembic revision -m "description"`
- No raw SQL — use SQLAlchemy ORM. All amounts in KZT as integers (no floats for money)

### Telegram Bot
- **Webhook only** — NO polling. PTB built with `.updater(None)`
- All ConversationHandlers must have `name=` AND `persistent=True`
- PicklePersistence at `/data/bot_persistence.pkl` (Railway Volume)

### Auth & Security
- JWT via `python-jose[cryptography]` + `pwdlib[bcrypt]` (**NOT** passlib — broken in Python 3.11+)
- Multi-user panel: PanelUser model with roles (pending/dispatcher/director/admin)
- Fallback: env var `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH` for bootstrap admin
- Driver PWA: phone-based token auth

### R2 Storage
- boto3 is sync — always wrap in `asyncio.get_event_loop().run_in_executor()`
- If R2 credentials absent → log warning, store `None` (never crash)

### Code Style
- Async everywhere: `async def` + `await` for all DB and network ops
- No blocking calls in async handlers
- No `@app.on_event` — use lifespan context manager
- snake_case, type hints required, English variable names
- All user-facing strings in Russian (UI) or multilingual (i18n keys)

## Environment Variables

Key vars (see `.env.example`):
- `DATABASE_URL` — Railway provides `postgresql://...` (auto-converted)
- `TELEGRAM_BOT_TOKEN`, `WEBHOOK_URL`
- `JWT_SECRET_KEY` — `python -c "import secrets; print(secrets.token_hex(32))"`
- `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH`
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`

## Common Commands

```bash
alembic upgrade head              # Run migrations
uvicorn src.main:app --reload     # Dev server
alembic revision -m "desc"       # New migration
alembic history                   # Check migration chain
```

## Domain Knowledge

- **CMR** — international consignment note (required for cross-border freight)
- **TIR** — transit customs document (simplifies border crossings)
- **Fuel norms** — each vehicle has a fuel consumption norm per 100km; anomalies are flagged
- **Per diem (суточные)** — daily allowance paid to drivers on international trips
- **Khorgos** — primary China-Kazakhstan border crossing, frequent queues (2-48 hours)
- **Backload** — return cargo to avoid empty runs; critical for profitability
- **KPI** — driver rating based on fuel efficiency, delivery times, incident count

## Known Decisions

- APScheduler (not Celery) for background jobs — saves Railway service costs
- PWA parallel to Telegram bot — Telegram blocked in China, unreliable in Russia
- Static FX rates table (live API deferred)
- Receipt photos optional in bot (2G reliability on remote routes)
- Railway Volume for FSM pickle — blocks zero-downtime deploys (known trade-off)
