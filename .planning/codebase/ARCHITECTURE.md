# Architecture

**Analysis Date:** 2026-03-08

## Pattern Overview

**Overall:** Telegram Bot + FastAPI Backend with SQLite Database

The Freight TMS is a dual-interface system: a Telegram bot for driver interactions and a FastAPI server for potential API access. The primary application is the Telegram bot which orchestrates conversations and data persistence. The architecture follows a conversation-driven pattern where multi-step user flows are managed through SQLAlchemy ORM models and conversation handlers.

**Key Characteristics:**
- Asynchronous I/O throughout (async/await with SQLAlchemy asyncio)
- Conversational UI pattern using python-telegram-bot's ConversationHandler
- Multi-language support (Russian and Kazakh)
- Modular flow architecture with dedicated conversation handlers
- Database-driven state for trips, expenses, drivers, vehicles, and locations

## Layers

**Presentation Layer (Telegram):**
- Purpose: User interface and interaction management via Telegram Bot API
- Location: `src/bot/bot_app.py`, `antigravity_modules/`
- Contains: ConversationHandlers, message handlers, keyboard builders, state management
- Depends on: Database layer (via CRUD), Configuration (settings)
- Used by: End users (drivers) through Telegram

**Conversation Flow Layer:**
- Purpose: Orchestrate multi-step user interactions and collect input
- Location: `antigravity_modules/trip_opening.py`, `antigravity_modules/trip_closing.py`, `antigravity_modules/expense_flow.py`, `antigravity_modules/location_flow.py`
- Contains: ConversationHandler definitions, state machines for each flow
- Depends on: Database layer (CRUD operations), Translation layer
- Used by: Bot application layer

**Database Layer:**
- Purpose: SQLAlchemy ORM models and database access
- Location: `src/db/models.py`, `src/db/crud.py`, `src/db/database.py`
- Contains: SQLAlchemy declarative models, async CRUD operations
- Depends on: Configuration (DATABASE_URL)
- Used by: All conversational flows and bot handlers

**API Layer:**
- Purpose: FastAPI REST interface (stub in MVP)
- Location: `src/main.py`
- Contains: FastAPI app, startup/shutdown events
- Depends on: Database layer
- Used by: External systems (not fully implemented)

**Configuration Layer:**
- Purpose: Environment-based settings management
- Location: `src/core/config.py`
- Contains: Pydantic settings, environment variable loading
- Depends on: `.env` file
- Used by: All other layers

**Translation Layer:**
- Purpose: Internationalization and UI text management
- Location: `antigravity_modules/translations.py`
- Contains: TRANSLATIONS dictionary with Russian/Kazakh text, get_text() and get_main_menu() functions
- Depends on: None
- Used by: All conversation flows and bot handlers

## Data Flow

**Driver Registration Flow:**

1. User sends `/start` command to bot
2. `start_handler` in `src/bot/bot_app.py` presents language selection
3. `receive_language` checks if driver exists via `get_driver_by_tg_id()` in `src/db/crud.py`
4. If new driver: collect name, phone, vehicle plate through conversation states (AWAITING_NAME, AWAITING_PHONE, AWAITING_VEHICLE)
5. `receive_vehicle` calls `create_driver()` and `create_vehicle()` via CRUD layer
6. New Trip, Expense, LocationUpdate records are now available for this driver

**Trip Lifecycle (Open → Add Expenses → Close):**

1. Driver initiates trip via "НАЧАТЬ РЕЙС" / "РЕЙСТІ БАСТАУ" button or `/open_trip` command
2. `open_trip_handler` in `antigravity_modules/trip_opening.py` starts conversation
3. Collects: route details, cargo info, opening document photo, start odometer
4. Creates Trip record with status=ACTIVE, linked to driver_id and vehicle_id
5. Driver can add multiple expenses during trip via `antigravity_modules/expense_flow.py`
6. Each expense is linked to trip_id via `create_expense()` in `antigravity_modules/expense_crud.py`
7. Driver closes trip via "ЗАВЕРШИТЬ РЕЙС" / "РЕЙСТІ АЯҚТАУ" button or `/close_trip` command
8. `close_trip_handler` collects end odometer and closing document photo
9. Trip status changes to COMPLETED, completed_at timestamp set

**Location Tracking:**

1. Driver initiates location share via "ОТПРАВИТЬ ГЕОЛОКАЦИЮ" / "ГЕОЛОКАЦИЯ ЖІБЕРУ"
2. `share_location_handler` in `antigravity_modules/location_flow.py` requests location permission
3. Telegram sends location data (latitude, longitude)
4. LocationUpdate record created, optionally linked to active trip_id

**State Management:**

- **Ephemeral Context**: User input collected in `context.user_data` dict during conversation states
- **Persistent State**: Once conversation ends, data is committed to database via SQLAlchemy ORM
- **Trip State**: Active trip lookup done via `get_active_trip_for_driver()` which queries Trip.status == "ACTIVE"
- **Language Preference**: Stored in Driver.language, retrieved at each interaction to fetch correct translations

## Key Abstractions

**ConversationHandler:**
- Purpose: Manage multi-step user interactions with state transitions
- Examples: `get_trip_conversation_handler()` in `antigravity_modules/trip_opening.py`, `get_expense_conversation_handler()` in `antigravity_modules/expense_flow.py`
- Pattern: Entry points (commands or regex filters) → states dict → fallback handlers

**Async CRUD Operations:**
- Purpose: Encapsulate database access with async/await pattern
- Examples: `get_driver_by_tg_id()`, `create_expense()`, `get_active_trip_for_driver()`
- Pattern: SQLAlchemy select() with async_session, return scalars().first() for single objects or scalar() for aggregates

**Domain Models with Relationships:**
- Purpose: Represent business entities and their relationships
- Examples: Driver (has many Trips), Trip (has many Expenses, belongs to Driver and Vehicle), Expense (belongs to Trip)
- Pattern: SQLAlchemy ORM with relationship() and ForeignKey()

**Enum-based Status:**
- Purpose: Enforce valid state values for drivers, vehicles, trips, and expenses
- Examples: `DriverStatus`, `VehicleStatus`, `TripStatus`, `ExpenseType`
- Pattern: Python enum.Enum inherited from str for JSON serialization

## Entry Points

**Telegram Bot (Primary):**
- Location: `run_bot.py`
- Triggers: `python run_bot.py` or `make run-bot` (in Makefile if defined)
- Responsibilities:
  - Creates Application via `create_bot_app()` from `src/bot/bot_app.py`
  - Registers all conversation handlers
  - Starts bot in polling mode
  - Receives and dispatches user messages

**FastAPI Server (Secondary/Stub):**
- Location: `src/main.py`
- Triggers: `uvicorn src.main:app` or `make run-api`
- Responsibilities:
  - Provides health check endpoint at `/`
  - Placeholder for future webhook integration or API endpoints
  - Startup/shutdown event hooks (not yet used)

**Database Migrations:**
- Location: `run_migration.py`
- Triggers: `python run_migration.py`
- Responsibilities: Runs Alembic migrations to initialize or upgrade database schema

**Set Bot Commands:**
- Location: `set_commands.py`
- Triggers: `python set_commands.py`
- Responsibilities: Registers available commands with Telegram API

## Error Handling

**Strategy:**
- Graceful fallback with user-facing error messages in appropriate language
- Logging of errors to console via Python's logging module
- Validation at input time (e.g., odometer must be integer, amount must be float)

**Patterns:**
- Input validation with try/except ValueError (see `receive_start_odometer` in `antigravity_modules/trip_opening.py`)
- Conversation state re-entry on error (retry same state vs. return ConversationHandler.END)
- Database existence checks before operations (get_driver_by_tg_id returns None if not found)
- Telegram location object validation in `receive_location` in `antigravity_modules/location_flow.py`

## Cross-Cutting Concerns

**Logging:**
- Logger created per module: `logger = logging.getLogger(__name__)`
- Basic info level logging at bot startup
- No explicit debug logging in conversation handlers (opportunity for improvement)

**Validation:**
- Database-level: Foreign key constraints via SQLAlchemy
- Application-level: Type validation in conversation handlers (int for odometer, float for expense amount)
- User input: Regex filters in ConversationHandler entry points (e.g., `filters.Regex(r"НАЧАТЬ РЕЙС|РЕЙСТІ БАСТАУ")`)

**Authentication:**
- Telegram user ID (tg_id) as unique identifier for drivers
- No explicit user authentication; Telegram API ensures authenticity of user_id
- No permission/role-based access control in MVP

**Localization:**
- Translation dictionary in `antigravity_modules/translations.py` with "ru" and "kk" keys
- `get_text(lang_code, key, **kwargs)` function for substituting values in templates
- `get_main_menu(lang, has_active_trip)` generates context-aware keyboard buttons
- Language preference stored per driver and used throughout conversation

**Async Pattern:**
- All database operations wrapped in `async with async_session() as session`
- ConversationHandler callbacks are all async functions
- SQLAlchemy configured with `create_async_engine()` and `async_sessionmaker`
- No blocking I/O in critical paths

---

*Architecture analysis: 2026-03-08*
