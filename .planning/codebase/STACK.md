# Technology Stack

**Analysis Date:** 2026-03-08

## Languages

**Primary:**
- Python 3.13 - Core application and API development

**Secondary:**
- SQL - Database schema and migrations via Alembic

## Runtime

**Environment:**
- Python 3.13 (virtualenv-based: `venv/`, `venv2/`, `venv3/`, `venv5/`)

**Package Manager:**
- pip
- Lockfile: requirements.txt (explicit dependencies listed)

## Frameworks

**Core:**
- FastAPI 0.115.0+ - RESTful API framework (`src/main.py`)
- python-telegram-bot 21.6+ - Telegram bot integration with job queue (`src/bot/bot_app.py`)

**Database:**
- SQLAlchemy 2.0.30+ - Async ORM (`src/db/database.py`)
- asyncpg 0.30.0+ - Async PostgreSQL driver
- Alembic 1.13.1+ - Database migration tool (`alembic/env.py`, `alembic.ini`)

**Web Server:**
- Uvicorn 0.30.0+ (with standard extras) - ASGI server for FastAPI

**Configuration:**
- Pydantic 2.9.0+ - Data validation
- pydantic-settings 2.5.0+ - Environment configuration management (`src/core/config.py`)
- python-dotenv 1.0.1+ - .env file loading

## Key Dependencies

**Critical:**
- FastAPI - REST API framework, enables rapid development with async/await support
- python-telegram-bot - Official Telegram Bot API client, handles all bot interactions and job queue scheduling
- SQLAlchemy 2.0 - Async ORM for database operations, supports async sessions and declarative models
- asyncpg - High-performance async PostgreSQL driver, required for async database operations
- Pydantic/pydantic-settings - Type-safe configuration management via `.env` files
- Uvicorn - ASGI application server, runs FastAPI async applications

**Infrastructure:**
- Alembic - Manages database schema versioning and migrations

## Configuration

**Environment:**
- Loaded from `.env` file via pydantic-settings (`src/core/config.py`)
- Required environment variables:
  - `TELEGRAM_BOT_TOKEN` - Telegram bot token for API access
  - `DATABASE_URL` - Database connection string (supports SQLite or PostgreSQL)

**Build:**
- No build step required (Python application)
- Entry points: `run_bot.py` (Telegram bot polling), `src/main.py` (FastAPI server)

**Database:**
- Alembic migration configuration in `alembic.ini` and `alembic/env.py`
- Migrations stored in `alembic/versions/`
- Async migration support via `run_migrations_online()` in `alembic/env.py`

## Platform Requirements

**Development:**
- Python 3.13+
- PostgreSQL 15 (for production) or SQLite (default for development)
- pip for dependency management

**Production:**
- Docker deployment: `docker-compose.yml` includes PostgreSQL 15-alpine service
- Environment: Any system supporting Python 3.13
- Database: PostgreSQL 15+ recommended (SQLite supported for lightweight setups)
- ASGI server: Uvicorn

**Database:**
- Development: SQLite (default at `./data.sqlite3`)
- Production: PostgreSQL 15-alpine via Docker
- Connection: Async via asyncpg
- Pooling: NullPool for migrations, default pooling for runtime

---

*Stack analysis: 2026-03-08*
