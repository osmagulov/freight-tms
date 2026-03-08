---
phase: 01-infrastructure-and-foundation
plan: 01
subsystem: database
tags: [postgresql, asyncpg, sqlalchemy, alembic, pydantic-settings, jwt, r2, boto3]

# Dependency graph
requires: []
provides:
  - "Settings with async_database_url property (postgresql:// -> postgresql+asyncpg://)"
  - "Phase 1 env vars: WEBHOOK_URL, R2_*, JWT_*, ADMIN_* in Settings"
  - "Driver.vehicle_id FK column and vehicle relationship"
  - "Vehicle.make, model, fuel_norm_per_100km columns"
  - "crud.link_driver_to_vehicle() function"
  - "Alembic migration 4d9175cac075 adding vehicle link and detail fields"
affects:
  - "02-PLAN.md (FastAPI, JWT auth needs JWT_SECRET_KEY from settings)"
  - "03-PLAN.md (R2 photo upload needs R2_* settings)"
  - "All plans using database (settings.async_database_url drives the connection)"

# Tech tracking
tech-stack:
  added:
    - "python-jose[cryptography]>=3.3.0 (JWT token signing)"
    - "pwdlib[bcrypt]>=0.2.0 (password hashing)"
    - "jinja2>=3.1.0 (HTML templates)"
    - "python-multipart>=0.0.9 (form data parsing)"
    - "boto3>=1.35.0 (Cloudflare R2 / S3 API)"
    - "aiosqlite>=0.20.0 (local dev SQLite fallback)"
  patterns:
    - "async_database_url property pattern: Settings transforms postgresql:// -> postgresql+asyncpg:// at property access time"
    - "env-based admin credentials: no DB table for admin user in Phase 1"
    - "Alembic migrations run as Railway pre-deploy hook, never in FastAPI startup"

key-files:
  created:
    - "alembic/versions/4d9175cac075_phase1_add_vehicle_link_and_fields.py"
  modified:
    - "src/core/config.py"
    - "src/db/database.py"
    - "src/db/models.py"
    - "src/db/crud.py"
    - "requirements.txt"

key-decisions:
  - "async_database_url as a @property on Settings avoids string mutation at import time and handles Railway's postgresql:// format transparently"
  - "Admin credentials stored in env vars (not DB) for Phase 1 simplicity — no admin table needed until Phase 2"
  - "aiosqlite kept in requirements for local dev fallback; asyncpg used on Railway with PostgreSQL"

patterns-established:
  - "URL transform pattern: settings.async_database_url property centralizes the postgresql:// -> postgresql+asyncpg:// conversion"
  - "FK naming: fk_{child_table}_{column} pattern (fk_drivers_vehicle_id)"

requirements-completed:
  - INFRA-01
  - INFRA-02

# Metrics
duration: 3min
completed: 2026-03-09
---

# Phase 1 Plan 01: Extend Settings and Schema for Phase 1 Summary

**PostgreSQL-ready asyncpg URL transform, 9 new env var fields (R2/JWT/admin), Driver-Vehicle FK link, and Alembic migration with fk_drivers_vehicle_id constraint**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-08T22:35:57Z
- **Completed:** 2026-03-08T22:38:57Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Settings class extended with async_database_url property that converts `postgresql://` to `postgresql+asyncpg://` — fixes Railway deploy URL format mismatch for asyncpg
- Added 9 new environment variable fields: WEBHOOK_URL, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, ADMIN_USERNAME, ADMIN_PASSWORD_HASH
- Driver model gets vehicle_id FK + vehicle relationship; Vehicle model gets make, model, fuel_norm_per_100km; crud.py gets link_driver_to_vehicle()
- Alembic migration 4d9175cac075 created with correct fk_drivers_vehicle_id constraint name

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Settings and fix database URL transformation** - `2a5b2d3` (feat)
2. **Task 2: Update models and create Phase 1 Alembic migration** - `0870568` (feat)

**Plan metadata:** `(pending - will be added in final commit)`

## Files Created/Modified

- `src/core/config.py` - Full Phase 1 Settings with async_database_url property and all new env var fields
- `src/db/database.py` - Changed engine creation to use settings.async_database_url
- `src/db/models.py` - Added vehicle_id FK and vehicle relationship to Driver; added make/model/fuel_norm_per_100km to Vehicle
- `src/db/crud.py` - Added link_driver_to_vehicle() function
- `requirements.txt` - Added python-jose, pwdlib, jinja2, python-multipart, boto3, aiosqlite
- `alembic/versions/4d9175cac075_phase1_add_vehicle_link_and_fields.py` - Migration adding vehicle_id FK and 3 vehicle detail columns

## Decisions Made

- Used `@property` on Settings for `async_database_url` to avoid mutating the raw DATABASE_URL string — keeps Railway's original URL accessible while giving asyncpg the correct format
- Admin credentials (ADMIN_USERNAME, ADMIN_PASSWORD_HASH) are env-var-only in Phase 1 — no DB admin table needed until a multi-dispatcher scenario requires it
- aiosqlite kept in requirements.txt for local development fallback while asyncpg is used on Railway with PostgreSQL

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required for this plan. (R2 and JWT secrets are configured when deploying to Railway in later plans.)

## Next Phase Readiness

- Settings foundation complete: all Wave 2 plans can access JWT_SECRET_KEY, R2_*, and ADMIN_* fields from settings
- database.py now correctly connects to PostgreSQL via asyncpg when DATABASE_URL is set on Railway
- Driver-Vehicle FK schema is in place; the Alembic migration is ready to run as a pre-deploy hook
- No blockers for Wave 2 plans

---
*Phase: 01-infrastructure-and-foundation*
*Completed: 2026-03-09*
