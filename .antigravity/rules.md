# Freight TMS — Claude Instructions

## Project Overview

Freight TMS — система управления грузоперевозками для 100+ водителей и 200+ грузовиков на международных маршрутах (CN↔KZ, KZ↔RU, Центральная Азия, Турция, Грузия).

**Stack:** Python 3.11, FastAPI + python-telegram-bot v22+, PostgreSQL (asyncpg), Alembic, Cloudflare R2 (boto3), Jinja2 + HTMX, Railway deployment.

## Architecture

Single-process: FastAPI + PTB webhook в одном процессе через `asynccontextmanager lifespan`.

```
src/
  core/config.py       — Settings (pydantic-settings), async_database_url property
  db/
    database.py        — async engine, async_session factory
    models.py          — SQLAlchemy ORM models
    crud.py            — DB operations
  bot/bot_app.py       — register_handlers(), create_bot_app()
  services/r2.py       — Cloudflare R2 upload via boto3
  web/                 — Jinja2 templates, JWT auth, web panel routes
  main.py              — FastAPI app, lifespan, /telegram endpoint, GET /
antigravity_modules/   — PTB ConversationHandlers (trip, expense, location, closing)
alembic/               — DB migrations (run as pre-deploy hook, NOT in startup)
```

## Critical Rules

### Database
- **ALWAYS** use `settings.async_database_url` (not `settings.DATABASE_URL`) for async engine — property converts `postgresql://` → `postgresql+asyncpg://`
- Alembic migrations run via Railway `preDeployCommand`, **never** inside FastAPI startup
- New columns → new Alembic migration file (`alembic revision -m "description"`)

### PTB / Telegram Bot
- **NO polling** — webhook only. PTB built with `.updater(None)`
- **ALL** ConversationHandlers must have both `name=` AND `persistent=True` for FSM state to survive redeployments
- PicklePersistence at `/data/bot_persistence.pkl` (Railway Volume mount)
- `register_handlers(app)` in `bot_app.py` — called from lifespan in `main.py`

### Auth & Security
- JWT via `python-jose[cryptography]` + `pwdlib[bcrypt]` (**NOT** passlib — broken in Python 3.11+)
- Admin credentials: `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH` (bcrypt hash) in env vars
- Unauthenticated web panel requests → redirect to `/panel/login`

### R2 Photo Storage
- boto3 is synchronous — always use `asyncio.get_event_loop().run_in_executor()` for uploads
- If R2 credentials absent → log warning, store `None` (no crash)
- Store URL in `Expense.photo_r2_url`, keep `photo_file_id` for backward compat

### Code Style
- Async everywhere — `async def` + `await` for all DB and network operations
- No blocking calls in async handlers (use run_in_executor for boto3/sync libs)
- No `@app.on_event` — deprecated, use lifespan context manager

## Environment Variables

All required vars are in `.env.example`. Key ones:
- `DATABASE_URL` — Railway provides as `postgresql://...` (auto-converted to asyncpg)
- `TELEGRAM_BOT_TOKEN` — from BotFather
- `WEBHOOK_URL` — Railway public URL (set after first deploy)
- `JWT_SECRET_KEY` — `python -c "import secrets; print(secrets.token_hex(32))"`
- `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` — dispatcher login
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`

## GSD Workflow

Project uses GSD (Get Shit Done) planning system.

- Plans: `.planning/phases/01-infrastructure-and-foundation/XX-PLAN.md`
- Current phase: **Phase 1 — Infrastructure & Foundation** (6 plans)
- Wave structure: Wave1(01) → Wave2(02+03) → Wave3(04+05) → Wave4(06)
- After completing: `/gsd:progress` to check state, `/gsd:execute-phase N` to run

**Never modify files listed in a plan's `files_modified` unless executing that plan.**

## Common Commands

```bash
# Run migrations locally
alembic upgrade head

# Start locally (needs .env)
uvicorn src.main:app --reload --port 8000

# Check alembic migration chain
alembic history

# Generate new migration
alembic revision -m "description"
```

## Known Issues / Decisions

- **SQLite → PostgreSQL**: existing `data.sqlite3` is dev data only; production uses PostgreSQL
- **FX rates**: multi-currency support uses static table in Phase 2 (live API deferred)
- **Photo optional**: receipt photo is optional in bot (2G reliability on driver routes)
- **APScheduler** (not Celery): anomaly checks run hourly in-process to save Railway service costs
- **Railway Volume**: FSM pickle file at `/data/bot_persistence.pkl` — Volume blocks zero-downtime deploys (known trade-off)
