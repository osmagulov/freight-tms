---
phase: 01-infrastructure-and-foundation
plan: 06
subsystem: infra
tags: [railway, alembic, asyncpg, postgresql, nixpacks, uvicorn]

# Dependency graph
requires:
  - phase: 01-infrastructure-and-foundation
    provides: FastAPI app (src/main.py), Alembic setup, settings with async_database_url, all Phase 1 code
provides:
  - railway.toml with Alembic pre-deploy hook and uvicorn startCommand using $PORT
  - .env.example listing all 10 required env vars with setup comments
  - alembic/env.py fixed to use async_database_url (postgresql+asyncpg://) for asyncpg-compatible migrations
affects: [all future phases, Railway deployment pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Railway preDeployCommand array format for Alembic migrations before app start"
    - "async_database_url property on Settings transparently converts postgresql:// to postgresql+asyncpg:// for asyncpg"
    - "nixpacks builder auto-detects Python from requirements.txt"

key-files:
  created:
    - railway.toml
    - .env.example
  modified:
    - alembic/env.py

key-decisions:
  - "alembic/env.py get_url() must return settings.async_database_url not settings.DATABASE_URL — asyncpg rejects the bare postgresql:// scheme"
  - "preDeployCommand uses array format (not string) per Railway's supported syntax; runs in a separate container with only DATABASE_URL, no Volume mount"
  - "healthcheckPath set to / which returns {status: ok} from src/main.py root endpoint"

patterns-established:
  - "Alembic pre-deploy: Railway runs preDeployCommand before bringing up the new container, ensuring schema is current before app starts"
  - "Env var template: .env.example documents all external dependencies with generation commands for secrets"

requirements-completed: [INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05]

# Metrics
duration: 5min
completed: 2026-03-09
---

# Phase 1 Plan 06: Railway Deployment Configuration Summary

**railway.toml with Alembic pre-deploy hook + uvicorn startCommand, plus fixed alembic/env.py using postgresql+asyncpg:// URL for asyncpg migrations**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-09T00:00:00Z
- **Completed:** 2026-03-09T00:05:00Z
- **Tasks:** 1 auto-completed (Task 2 is a human-verify checkpoint, pending)
- **Files modified:** 3

## Accomplishments
- Created railway.toml configuring nixpacks builder, Alembic preDeployCommand, uvicorn startCommand with $PORT, healthcheck, and restart policy
- Created .env.example with all 10 required env vars and inline comments for how to generate secrets
- Fixed alembic/env.py get_url() to return settings.async_database_url so asyncpg-based migrations work against Railway's PostgreSQL

## Task Commits

Each task was committed atomically:

1. **Task 1: Create railway.toml, .env.example, fix alembic/env.py** - `f13a5b9` (feat)

**Plan metadata:** (pending — awaiting human-verify checkpoint approval)

## Files Created/Modified
- `railway.toml` - nixpacks build config + preDeployCommand (alembic upgrade head) + startCommand (uvicorn $PORT)
- `.env.example` - all 10 env vars with comments: TELEGRAM_BOT_TOKEN, DATABASE_URL, WEBHOOK_URL, R2_*, JWT_SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD_HASH
- `alembic/env.py` - get_url() now returns settings.async_database_url instead of settings.DATABASE_URL

## Decisions Made
- `get_url()` in alembic/env.py must return `settings.async_database_url` — Railway provides `postgresql://` but asyncpg requires `postgresql+asyncpg://`; the `@property` on Settings handles the conversion transparently
- preDeployCommand array format `["alembic", "upgrade", "head"]` is Railway's supported syntax (not a shell string)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed alembic/env.py using raw DATABASE_URL instead of async_database_url**
- **Found during:** Task 1 (Create railway.toml and .env.example)
- **Issue:** get_url() returned settings.DATABASE_URL which is `postgresql://...`; asyncpg driver requires `postgresql+asyncpg://...` — migrations would fail on Railway
- **Fix:** Changed get_url() to return settings.async_database_url which applies the scheme conversion via the @property
- **Files modified:** alembic/env.py
- **Verification:** `grep "async_database_url" alembic/env.py` confirms the fix
- **Committed in:** f13a5b9 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Necessary correctness fix — alembic migrations would have failed on Railway without it. No scope creep.

## Issues Encountered
None beyond the alembic async URL bug, which was auto-fixed inline.

## User Setup Required

**Railway requires manual configuration before first deploy.** Complete these steps in Railway Dashboard:

1. **Add PostgreSQL addon:** Dashboard -> project -> Add Service -> Database -> PostgreSQL
2. **Set env vars:** TELEGRAM_BOT_TOKEN, DATABASE_URL=${{Postgres.DATABASE_URL}}, JWT_SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD_HASH, R2_* (if R2 ready)
3. **Leave WEBHOOK_URL empty for first deploy**
4. **Push to Railway-connected branch** to trigger deploy
5. **After first deploy succeeds:** Add WEBHOOK_URL (your Railway public URL) -> Redeploy

See `.env.example` for how to generate JWT_SECRET_KEY and ADMIN_PASSWORD_HASH.

## Next Phase Readiness

**Checkpoint pending:** Task 2 (smoke test on Railway production) is a human-verify checkpoint. Phase 1 is complete when the smoke test passes all 5 success criteria:
1. Driver /start -> registration -> PostgreSQL record with vehicle_id FK set
2. Dispatcher sees driver+vehicle pair in /panel/drivers
3. Receipt photo stored in R2 with retrievable URL
4. Railway redeploy -> mid-conversation FSM state preserved
5. /panel/drivers requires login, unauthenticated -> redirect to /panel/login

No blockers for Phase 2 execution beyond confirming Railway plan tier (Hobby vs Pro cold-start behavior).

---
*Phase: 01-infrastructure-and-foundation*
*Completed: 2026-03-09*
