# Codebase Structure

**Analysis Date:** 2026-03-08

## Directory Layout

```
freight-tms/
├── src/                    # Main application source code
│   ├── bot/               # Telegram bot application
│   │   └── bot_app.py    # ConversationHandler setup and registration handlers
│   ├── core/              # Application configuration
│   │   └── config.py     # Environment settings (Pydantic)
│   ├── db/                # Database models and CRUD operations
│   │   ├── models.py     # SQLAlchemy ORM models
│   │   ├── crud.py       # Database operations (async CRUD)
│   │   └── database.py   # Engine and session initialization
│   └── main.py            # FastAPI application (stub)
├── antigravity_modules/   # Conversation flows and business logic
│   ├── trip_opening.py    # Trip start conversation handler
│   ├── trip_closing.py    # Trip end conversation handler
│   ├── expense_flow.py    # Expense entry conversation handler
│   ├── location_flow.py   # Location sharing conversation handler
│   ├── expense_crud.py    # Expense-specific database operations
│   ├── translations.py    # Internationalization (Russian, Kazakh)
│   └── __init__.py        # Package marker
├── alembic/               # Database migration configuration
│   ├── env.py            # Migration environment
│   └── versions/         # Migration scripts (auto-generated)
├── run_bot.py             # Entry point: Start Telegram bot
├── run_migration.py       # Entry point: Run database migrations
├── set_commands.py        # Entry point: Register bot commands with Telegram
├── kill_bot.py            # Utility: Stop bot gracefully
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (secrets, not committed)
├── .env.example           # Template for .env
├── Makefile               # Build and run shortcuts
├── docker-compose.yml     # Database container config (PostgreSQL ready)
├── alembic.ini            # Alembic configuration
└── data.sqlite3           # SQLite database (development)
```

## Directory Purposes

**`src/`**
- Purpose: Core application code separated by concern
- Contains: Bot handlers, database models, configuration, FastAPI server
- Key files: All `.py` files in subdirectories

**`src/bot/`**
- Purpose: Telegram bot application setup
- Contains: ConversationHandler registration, entry command handlers (start, menu, etc.)
- Key files: `src/bot/bot_app.py` (main bot application factory)

**`src/db/`**
- Purpose: Data persistence layer
- Contains: SQLAlchemy models (Driver, Vehicle, Trip, Expense, LocationUpdate), async CRUD functions, database engine/session
- Key files: `src/db/models.py` (domain models), `src/db/crud.py` (queries), `src/db/database.py` (connection)

**`src/core/`**
- Purpose: Application-wide configuration
- Contains: Environment variables loaded from `.env` via Pydantic
- Key files: `src/core/config.py` (Settings class)

**`antigravity_modules/`**
- Purpose: Conversation flows and domain business logic
- Contains: Multi-step conversation handlers (trip opening/closing, expenses, location), translations, expense database operations
- Key files:
  - `trip_opening.py` - Trip start conversation (route, cargo, docs, odometer)
  - `trip_closing.py` - Trip end conversation (end odometer, closing docs)
  - `expense_flow.py` - Expense entry conversation (type, amount, currency, photos, comment)
  - `location_flow.py` - Location sharing conversation (GPS coordinates)
  - `translations.py` - UI text for Russian and Kazakh
  - `expense_crud.py` - Trip/expense queries

**`alembic/`**
- Purpose: Database schema versioning
- Contains: Migration scripts (auto-generated via `alembic revision --autogenerate`)
- Key files: `env.py` (migration configuration), `versions/*.py` (individual migrations)

## Key File Locations

**Entry Points:**
- `run_bot.py`: Starts Telegram bot in polling mode - execute `python run_bot.py`
- `run_migration.py`: Runs pending database migrations - execute `python run_migration.py`
- `set_commands.py`: Registers bot commands with Telegram API - execute `python set_commands.py`
- `src/main.py`: FastAPI server (stub) - execute `uvicorn src.main:app` or `make run-api`

**Configuration:**
- `src/core/config.py`: Loads TELEGRAM_BOT_TOKEN and DATABASE_URL from environment
- `.env`: Runtime environment variables (Git-ignored)
- `alembic.ini`: Alembic migration tool configuration

**Core Logic:**
- `src/bot/bot_app.py`: Bot application factory `create_bot_app()`, registration handlers (start, menu), conversation handler mounting
- `src/db/models.py`: SQLAlchemy ORM models with enums (DriverStatus, TripStatus, ExpenseType)
- `src/db/crud.py`: Base CRUD operations (get_driver_by_tg_id, create_driver, get_vehicle_by_plate, create_vehicle, update_driver_language)
- `src/db/database.py`: SQLAlchemy async engine and session maker initialization
- `antigravity_modules/trip_opening.py`: Trip start conversation handler (AWAITING_ROUTE → AWAITING_CARGO → AWAITING_DOCUMENTS → AWAITING_START_ODOMETER)
- `antigravity_modules/trip_closing.py`: Trip end conversation handler (AWAITING_END_ODOMETER → AWAITING_CLOSING_DOCS)
- `antigravity_modules/expense_flow.py`: Expense entry conversation handler (AWAITING_EXPENSE_TYPE → ... → AWAITING_EXPENSE_COMMENT)
- `antigravity_modules/location_flow.py`: Location sharing conversation handler (AWAITING_LOCATION)
- `antigravity_modules/expense_crud.py`: Database operations for trips and expenses (get_active_trip_for_driver, create_expense)
- `antigravity_modules/translations.py`: Bilingual UI text dictionary and helper functions (get_text, get_main_menu)

**Testing:**
- Not detected (no test files present)

## Naming Conventions

**Files:**
- Conversation handler files use snake_case: `trip_opening.py`, `expense_flow.py`
- Database files use snake_case: `database.py`, `models.py`, `crud.py`
- Entry point scripts use snake_case: `run_bot.py`, `run_migration.py`
- Example: `src/db/models.py`, `antigravity_modules/trip_opening.py`

**Directories:**
- Source code in lowercase: `src`, `antigravity_modules`, `alembic`
- Subdirectories reflect layers: `src/bot`, `src/db`, `src/core`

**Python Modules:**
- Models: PascalCase for class names (Driver, Vehicle, Trip, Expense, LocationUpdate)
- Enums: PascalCase (DriverStatus, VehicleStatus, TripStatus, ExpenseType)
- Functions: snake_case (get_driver_by_tg_id, create_driver, open_trip_handler, receive_language)
- Conversation states: UPPERCASE_SNAKE_CASE (AWAITING_LANGUAGE, AWAITING_ROUTE, AWAITING_EXPENSE_TYPE)

**Telegram/UI:**
- Commands: lowercase with underscore (`/start`, `/open_trip`, `/close_trip`, `/add_expense`, `/location`)
- Button text: UPPERCASE with emoji (🚚 НАЧАТЬ РЕЙС, 💸 ДОБАВИТЬ РАСХОД, 📍 ОТПРАВИТЬ ГЕОЛОКАЦИЮ)

## Where to Add New Code

**New Conversation Flow (e.g., vehicle inspection):**
- Create `antigravity_modules/vehicle_inspection.py`
- Define conversation states as module-level constants (AWAITING_EXTERIOR, AWAITING_INTERIOR, etc.)
- Implement handler functions (one per state transition)
- Implement `get_vehicle_inspection_conversation_handler()` returning ConversationHandler
- Import and register in `src/bot/bot_app.py` via `app.add_handler(get_vehicle_inspection_conversation_handler())`
- Add translations to "ru" and "kk" keys in `antigravity_modules/translations.py`

**New Database Model:**
- Add model class to `src/db/models.py` (inherit from Base, use Column and relationship decorators)
- Add CRUD operations to appropriate module (either `src/db/crud.py` for base entities or `antigravity_modules/[feature]_crud.py` for feature-specific)
- Generate migration: `alembic revision --autogenerate -m "Add [model name]"`
- Run migration: `python run_migration.py`

**New CRUD Function:**
- If for core entities (Driver, Vehicle): add to `src/db/crud.py`
- If for feature-specific operations (Expense, Trip queries): add to `antigravity_modules/[feature]_crud.py`
- Use async/await pattern: `async def [operation_name](session: AsyncSession, ...)`
- Use SQLAlchemy select() for queries, session.add()/commit() for mutations

**New Translation String:**
- Add key-value pair to both "ru" and "kk" dicts in `antigravity_modules/translations.py`
- Use placeholders: `"welcome_back": "Hello, {name}!"`
- Retrieve via: `get_text(lang_code, "welcome_back", name="Alice")`

**New API Endpoint:**
- Add to `src/main.py` as async function decorated with `@app.get()`, `@app.post()`, etc.
- Follow FastAPI patterns: use dependency injection for database sessions via `get_db()`
- Currently stub; not integrated with bot

**Utilities and Helpers:**
- Shared text utilities: `antigravity_modules/translations.py` (already contains get_main_menu and get_text helpers)
- Shared database utilities: `antigravity_modules/expense_crud.py` for trip/expense helpers
- No dedicated utils/ directory; keep helpers close to where they're used

## Special Directories

**`alembic/`:**
- Purpose: Alembic database migration management
- Generated: Yes (migration scripts in versions/ are auto-generated by `alembic revision --autogenerate`)
- Committed: Yes (env.py and versions/ are committed to track schema history)
- How to use:
  - Create new migration after model changes: `alembic revision --autogenerate -m "Description"`
  - Apply migrations: `alembic upgrade head` or `python run_migration.py`
  - View migration history: `alembic current`, `alembic history`

**`.env`:**
- Purpose: Runtime configuration and secrets
- Generated: No (template at `.env.example`)
- Committed: No (in .gitignore)
- Contains: TELEGRAM_BOT_TOKEN, DATABASE_URL (as of now, likely to grow)

**`venv/`:**
- Purpose: Python virtual environment (dependency isolation)
- Generated: Yes (via `make install` or `python -m venv venv`)
- Committed: No (in .gitignore)
- Activate: `source venv/bin/activate` (Unix) or `venv\Scripts\activate` (Windows)

**Development Database:**
- `data.sqlite3`: SQLite database file (development only, Git-ignored in production)
- For production: Docker Compose ready for PostgreSQL via `docker-compose.yml`

---

*Structure analysis: 2026-03-08*
