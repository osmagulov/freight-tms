# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-08)

**Core value:** Dispatcher always knows where every truck is, what it's carrying, and how much it has spent — and can assign a new trip before the truck returns
**Current focus:** Phase 3 (Trip Management) — Plan 2 complete

## Current Position

Phase: 3 of 5 (Trip Management) — IN PROGRESS
Plan: 2 of 5 in Phase 3 — COMPLETE
Status: Phase 3 Plan 02 complete. Dispatcher-first trip opening flow active. Ready for Plan 03 (document upload).
Last activity: 2026-03-09 — Phase 3 Plan 02 complete. trip_opening.py rewritten for dispatcher-first model. get_planned_trip_for_driver() and activate_trip() added to expense_crud.py. Phase 3 translation keys added.

Progress: [█████░░░░░] 48%

## Performance Metrics

**Velocity:**
- Total plans completed: 11
- Average duration: 6.5 min
- Total execution time: ~1.18 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-infrastructure-and-foundation | 6/6 | 52 min | 8.7 min |
| 02-expense-control | 5/5 | 34 min | 6.8 min |
| 03-trip-management | 2/5 | 11 min | 5.5 min |

**Recent Trend:**
- Last 7 plans: 02-02 (4 min), 02-03 (2 min), 02-04 (18 min), 02-05 (9 min), 03-01 (3 min), 03-02 (8 min)
- Trend: Stable

*Updated after each plan completion*
| Phase 02-expense-control P02 | 4 | 2 tasks | 4 files |
| Phase 02-expense-control P04 | 18 | 2 tasks | 6 files |
| Phase 02-expense-control P05 | 9 | 2 tasks | 3 files |
| Phase 03-trip-management P01 | 3 | 2 tasks | 2 files |
| Phase 03-trip-management P02 | 8 | 3 tasks | 3 files |

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
- [Phase 02-04]: check_fuel_anomaly_after_expense() opens its own async_session and re-fetches expense/vehicle by ID — required because original create_expense() session is closed; avoids detached-instance error
- [Phase 02-04]: APScheduler start() is NOT awaited (synchronous call); scheduler.shutdown(wait=False) on lifespan cleanup; scheduler starts before PTB async with block
- [Phase 02-04]: Anomaly check wired into both process_final_expense() and process_final_expense_direct() — both paths save FUEL expenses in expense_flow.py
- [Phase 02-05]: Local imports (sqlalchemy func, Expense model) kept inside expense_summary_handler() body — consistent with existing pattern in process_final_expense(); avoids any top-level import ordering issues
- [Phase 02-05]: STATUS_LABELS dict defined inline in expense_summary_handler() rather than in translations — keeps status-to-label mapping co-located with formatting logic
- [Phase 03-01]: Alembic migration written manually (not autogenerated) — local SQLite cannot run Phase 1 FK ALTER migration; Railway PostgreSQL is the target
- [Phase 03-01]: All four new Trip columns are nullable=True — existing trips have no client/date data; nullable avoids NOT NULL migration failure on existing rows
- [Phase 03-01]: TripDocument.file_type is nullable=False — always required to classify the document; r2_url and tg_file_id are nullable for partial upload states
- [Phase 03-02]: trip_opening.py full rewrite — removed AWAITING_ROUTE/CARGO/DOCUMENTS states, replaced with dispatcher-first AWAITING_CONFIRMATION + AWAITING_START_ODOMETER flow
- [Phase 03-02]: activate_trip() updates both Trip and Vehicle in a single async_session commit — no partial state possible if session fails
- [Phase 03-02]: Legacy open_trip_ask_route/cargo/docs keys retained in translations — PicklePersistence sessions in old states get readable fallback message
- [Phase 03-02]: btn_yes/btn_no as explicit translation keys — confirmation keyboard buttons must match driver's language for receive_confirmation() text comparison

### Pending Todos

None yet.

### Blockers/Concerns

- DIRECTOR_TG_ID must be set in Railway env vars before Phase 2 anomaly digest notifications are enabled
- FX rate source for multi-currency expenses resolved as static table in Phase 2 — revisit if live rates needed

## Session Continuity

Last session: 2026-03-09
Stopped at: Phase 3 Plan 02 complete — trip_opening.py rewritten (dispatcher-first), get_planned_trip_for_driver/activate_trip added to expense_crud.py, Phase 3 translations complete. Ready for Phase 3 Plan 03.
Resume file: None
