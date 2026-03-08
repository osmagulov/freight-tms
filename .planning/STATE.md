# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-08)

**Core value:** Dispatcher always knows where every truck is, what it's carrying, and how much it has spent — and can assign a new trip before the truck returns
**Current focus:** Phase 1: Infrastructure & Foundation

## Current Position

Phase: 1 of 5 (Infrastructure & Foundation)
Plan: 5 of 6 in current phase
Status: Executing
Last activity: 2026-03-09 — Completed plan 05 (JWT cookie auth + Jinja2 web panel for dispatcher drivers/vehicle management)

Progress: [████░░░░░░] 17%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 9.4 min
- Total execution time: 0.78 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-infrastructure-and-foundation | 5/6 | 47 min | 9.4 min |

**Recent Trend:**
- Last 5 plans: 01-01 (3 min), 01-02 (2 min), 01-03 (2 min), 01-04 (8 min), 01-05 (32 min)
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-phase]: PicklePersistence for FSM in beta; migrate to PostgreSQL-backed persistence before production
- [Pre-phase]: Fuel anomaly threshold set at 20% over norm (not 10%) to reduce false positives on mountain routes
- [Pre-phase]: APScheduler replaces Celery+Redis to save a Railway service; anomaly checks run hourly in-process
- [Pre-phase]: Alembic migrations run as pre-deploy hook, never inside FastAPI startup event
- [01-01]: async_database_url as @property on Settings converts postgresql:// to postgresql+asyncpg:// transparently for asyncpg driver
- [01-01]: Admin credentials (ADMIN_USERNAME, ADMIN_PASSWORD_HASH) in env vars only for Phase 1 — no DB admin table until multi-dispatcher needed
- [01-01]: aiosqlite kept in requirements for local dev SQLite fallback; asyncpg used on Railway with PostgreSQL
- [01-02]: PicklePersistence created in main.py lifespan (not bot_app.py) so bot_app.py stays testable without disk side effects
- [01-02]: register_handlers() extracted so lifespan attaches handlers to persistence-equipped app; create_bot_app() delegates to it for local polling tests
- [01-02]: WEBHOOK_URL absence logged as warning (not error) to allow local development without Railway env vars
- [01-03]: PTB requires both name= AND persistent=True on ConversationHandler; only persistent=True was missing in 4 of 5 handlers — added with no other changes
- [01-03]: FSM persistence now complete across all 5 ConversationHandlers; bot conversation state survives Railway redeployments
- [Phase 01-04]: boto3 is synchronous — wrapped in run_in_executor(None, partial(...)) to avoid blocking asyncio event loop during R2 uploads
- [Phase 01-04]: photo_file_id kept alongside photo_r2_url for backward compat; R2 upload gracefully degrades to None if credentials absent (no crash)
- [Phase 01-05]: HTTPException(302) raised inline at each auth guard in get_current_user_from_cookie() — no helper function to avoid unreachable-raise confusion
- [Phase 01-05]: 302 exception handler added to FastAPI app so browser follows auth redirects from Depends() cookie guard dependency

### Pending Todos

None yet.

### Blockers/Concerns

- FX rate source for multi-currency expenses needs a decision before Phase 2 implementation (static table vs live API)
- Photo mandatory vs optional in bot beta — decide before Phase 2 UX is written (2G upload reliability on driver routes)
- Railway plan tier (Hobby vs Pro) should be confirmed before Phase 1 deploy to understand cold-start behavior

## Session Continuity

Last session: 2026-03-09
Stopped at: Completed 01-05-PLAN.md (JWT cookie auth + Jinja2 web panel for dispatcher drivers/vehicle management — human-verify checkpoint pending)
Resume file: None
