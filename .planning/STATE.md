# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-08)

**Core value:** Dispatcher always knows where every truck is, what it's carrying, and how much it has spent — and can assign a new trip before the truck returns
**Current focus:** Phase 2: Expense Control

## Current Position

Phase: 2 of 5 (Expense Control)
Plan: 3 of ? in current phase
Status: In progress
Last activity: 2026-03-09 — Phase 2 Plan 03 complete. Dispatcher approval queue with HTMX inline approve/reject and Telegram driver notifications now operational.

Progress: [███░░░░░░░] 25%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 6.9 min
- Total execution time: 0.92 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-infrastructure-and-foundation | 6/6 | 52 min | 8.7 min |
| 02-expense-control | 3/? | 7 min | 2.3 min |

**Recent Trend:**
- Last 7 plans: 01-03 (2 min), 01-04 (8 min), 01-05 (32 min), 01-06 (5 min), 02-01 (5 min), 02-02 (?), 02-03 (2 min)
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
- [Phase 01-06]: alembic/env.py get_url() must return settings.async_database_url not settings.DATABASE_URL — asyncpg rejects bare postgresql:// scheme
- [Phase 01-06]: railway.toml preDeployCommand uses array format ["alembic","upgrade","head"]; runs in separate Railway container with only DATABASE_URL, no Volume mount
- [Phase 02-01]: status column uses both ORM default="PENDING" and migration server_default='PENDING' — both needed for Railway pre-deploy hook correctness on existing rows
- [Phase 02-01]: DIRECTOR_TG_ID defaults to 0 (int) in Settings — must be set in Railway env before anomaly alerts go live
- [Phase 02-01]: threshold_per_100km added to FuelAnomaly model to store per-vehicle threshold at detection time for audit trail (false positive review)
- [Phase 02-03]: Deferred import of ptb_app inside notify_driver_expense_decision() avoids circular import between main.py and panel.py
- [Phase 02-03]: expense_row.html used as both include in expenses.html and direct TemplateResponse in POST handlers — single template, no duplication
- [Phase 02-03]: HTMX 2.0.4 loaded via unpkg CDN in base.html head — applies to all panel pages; hx-post+hx-target+hx-swap=outerHTML pattern for inline row replacement

### Pending Todos

None yet.

### Blockers/Concerns

- FX rate source for multi-currency expenses needs a decision before Phase 2 implementation (static table vs live API)
- Photo mandatory vs optional in bot beta — decide before Phase 2 UX is written (2G upload reliability on driver routes)
- Railway plan tier (Hobby vs Pro) should be confirmed before Phase 1 deploy to understand cold-start behavior
- DIRECTOR_TG_ID must be set in Railway env vars before Phase 2 anomaly digest notifications are enabled

## Session Continuity

Last session: 2026-03-09
Stopped at: 02-03-PLAN.md complete — Dispatcher approval queue with HTMX inline approve/reject and Telegram notifications
Resume file: None
