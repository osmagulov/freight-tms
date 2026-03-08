# External Integrations

**Analysis Date:** 2026-03-08

## APIs & External Services

**Telegram Bot API:**
- Telegram Bot API via python-telegram-bot library
  - SDK/Client: python-telegram-bot[job-queue] 21.6+
  - Auth: Env var `TELEGRAM_BOT_TOKEN` (set in `.env`)
  - Implementation: `src/bot/bot_app.py` creates Application with token
  - Mode: Polling (long-polling via `app.run_polling()` in `run_bot.py`)
  - Handlers: Registration flow, trip management, expense tracking, location updates, trip closing

## Data Storage

**Databases:**
- PostgreSQL (production)
  - Provider: Docker service via `docker-compose.yml` (postgres:15-alpine)
  - Connection: Env var `DATABASE_URL` - defaults to SQLite for development
  - Client: SQLAlchemy 2.0 async ORM with asyncpg driver
  - Async: Full async support via `create_async_engine()` and `AsyncSession` (`src/db/database.py`)
  - Models: `src/db/models.py` (Driver, Vehicle, Trip, Expense, LocationUpdate)
  - Migrations: Alembic-managed schema versions in `alembic/versions/`

- SQLite (development/lightweight)
  - Default location: `./data.sqlite3`
  - Connection string: `sqlite+aiosqlite:///./data.sqlite3`
  - Used when `DATABASE_URL` not set in `.env`

**File Storage:**
- Local filesystem only (no cloud storage integration)
- Telegram file uploads: Bot stores file_id references for receipts and card photos (`photo_file_id`, `card_photo_file_id` in `Expense` model)

**Caching:**
- None detected - no caching layer configured

## Authentication & Identity

**Auth Provider:**
- Telegram as primary identity provider
- Custom implementation via Telegram user IDs
  - Driver identity: Linked to `tg_id` (BigInteger) in Driver model (`src/db/models.py`)
  - Language preference: Stored per driver (`language` field)
  - No JWT/OAuth - Telegram ID acts as user identifier

**Session Management:**
- Bot user context maintained in `context.user_data` during conversation flows (`src/bot/bot_app.py`)
- AsyncSession from SQLAlchemy for database session handling (`src/db/database.py`)

## Monitoring & Observability

**Error Tracking:**
- None detected - no external error tracking service integrated

**Logs:**
- Python standard logging module
  - Logging configuration in `run_bot.py` and `src/main.py`
  - Format: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`
  - Level: INFO for bot, INFO for API
  - Output: Console/stderr
  - Log file observed: `bot_v2.log` (manual logging to file)

## CI/CD & Deployment

**Hosting:**
- Not configured - Local development only currently
- Docker support: `docker-compose.yml` for local PostgreSQL setup

**CI Pipeline:**
- None detected

**Deployment:**
- Manual: Via `run_bot.py` for Telegram bot polling
- Manual: Via Uvicorn for FastAPI (`python -m uvicorn src.main:app`)
- Docker-ready: `docker-compose.yml` for database service

## Environment Configuration

**Required env vars:**
- `TELEGRAM_BOT_TOKEN` - Telegram bot token (no default, must be provided)
- `DATABASE_URL` - Database connection string (default: `sqlite+aiosqlite:///./data.sqlite3`)

**Optional env vars:**
- None explicitly defined beyond the above

**Secrets location:**
- `.env` file (in `.gitignore`, not committed)
- Default template: `.env.example` shows structure
- Usage: pydantic-settings loads from `.env` in `src/core/config.py`

## Webhooks & Callbacks

**Incoming:**
- FastAPI endpoints in `src/main.py`: GET `/` (health check)
- No webhook endpoints for Telegram yet - using polling mode instead

**Outgoing:**
- Telegram Bot API calls via python-telegram-bot:
  - Message sends (`reply_text`, keyboard updates)
  - File uploads (receipt and card photos via Telegram API)
  - User data requests (contact info via `update.message.contact`)

## Integration Points

**Bot-to-Database:**
- Driver registration: Creates `Driver` and `Vehicle` records in `receive_vehicle()` (`src/bot/bot_app.py`)
- Expense tracking: Stores expense records with Telegram file IDs (`antigravity_modules/expense_flow.py`)
- Location updates: Stores location coordinates per trip (`antigravity_modules/location_flow.py`)
- Trip lifecycle: Opens/closes trips, updates trip status (`antigravity_modules/trip_opening.py`, `trip_closing.py`)

**API-to-Database:**
- FastAPI serves as REST interface (minimal implementation)
- All bot operations go through SQLAlchemy ORM
- Async database calls via `async_session` (`src/db/database.py`)

**Telegram Bot Features:**
- ConversationHandler for multi-step registration (`AWAITING_LANGUAGE` → `AWAITING_NAME` → `AWAITING_PHONE` → `AWAITING_VEHICLE`)
- Message handlers for trip opening, expense submission, location sharing
- Keyboard buttons for language selection (Russian, Kazakh) and primary menu interactions
- File uploads: Receipt photos and card/terminal photos for expenses

## Data Exchange Patterns

**Command Handlers:**
- `/start` - Initiates registration or welcome
- `/menu` - Shows main menu
- `/cancel` - Aborts current conversation

**Conversation States:**
- Registration: Multi-step conversation with fallback to `/cancel`
- Trip management: Separate conversation handlers for trip opening/closing
- Expense submission: Conversation flow for amount, type, receipts
- Location tracking: Real-time location updates via message handler

---

*Integration audit: 2026-03-08*
