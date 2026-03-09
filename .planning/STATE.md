# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-08)

**Core value:** Dispatcher always knows where every truck is, what it's carrying, and how much it has spent — and can assign a new trip before the truck returns
**Current focus:** Phase 5 (Director Dashboard) — COMPLETE (2 plans done)

## Current Position

Phase: 5 of 5 (Director Dashboard & Reporting) — COMPLETE
Plan: 2 of 2 in Phase 5 — COMPLETE
Status: ALL PHASES COMPLETE. Director dashboard with cost summary, per-truck breakdown, CSV export, anomaly history, and per-driver history.
Last activity: 2026-03-10 — Phase 5 complete. src/web/director.py with 7 routes, 5 director templates, Директор nav link in base.html, director_router registered in main.py.

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 13
- Average duration: 6.2 min
- Total execution time: ~1.34 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-infrastructure-and-foundation | 6/6 | 52 min | 8.7 min |
| 02-expense-control | 5/5 | 34 min | 6.8 min |
| 03-trip-management | 5/5 | 33 min | 6.6 min |

**Recent Trend:**
- Last 7 plans: 02-04 (18 min), 02-05 (9 min), 03-01 (3 min), 03-02 (8 min), 03-03 (8 min), 03-04 (6 min)
- Trend: Stable

*Updated after each plan completion*
| Phase 02-expense-control P02 | 4 | 2 tasks | 4 files |
| Phase 02-expense-control P04 | 18 | 2 tasks | 6 files |
| Phase 02-expense-control P05 | 9 | 2 tasks | 3 files |
| Phase 03-trip-management P01 | 3 | 2 tasks | 2 files |
| Phase 03-trip-management P02 | 8 | 3 tasks | 3 files |
| Phase 03-trip-management P03 | 8 | 3 tasks | 3 files |
| Phase 03-trip-management P04 | 6 | 3 tasks | 4 files |
| Phase 03-trip-management P05 | 8 | 4 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-phase]: PicklePersistence for FSM in beta; migrate to PostgreSQL-backed persistence before production
- [Pre-phase]: APScheduler replaces Celery+Redis to save a Railway service; anomaly checks run hourly in-process
- [Pre-phase]: Alembic migrations run as pre-deploy hook, never inside FastAPI startup event
- [01-03]: PTB requires both name= AND persistent=True on ConversationHandler; FSM persistence survives redeployments
- [Phase 01-04]: boto3 is synchronous — wrapped in run_in_executor to avoid blocking asyncio event loop during R2 uploads
- [Phase 02-04]: check_fuel_anomaly_after_expense() opens its own async_session — avoids detached-instance error
- [Phase 03-01]: Alembic migration written manually — local SQLite cannot run Phase 1 FK ALTER migration; Railway PostgreSQL is the target
- [Phase 03-01]: All four new Trip columns nullable=True — existing trips have no client/date data
- [Phase 03-01]: TripDocument.file_type nullable=False — always required; r2_url and tg_file_id nullable for partial upload states
- [Phase 03-02]: trip_opening.py full rewrite — dispatcher-first AWAITING_CONFIRMATION + AWAITING_START_ODOMETER flow
- [Phase 03-02]: activate_trip() updates both Trip and Vehicle in single async_session commit — atomically
- [Phase 03-03]: upload_to_r2 is the new primary R2 upload function; upload_photo_to_r2 becomes a delegating alias for backward compat
- [Phase 03-03]: close_trip_db takes vehicle_id as explicit param — stored in user_data at FSM entry to avoid extra DB round-trip
- [Phase 03-03]: Delivery status keyboard labels hardcoded inline in trip_closing.py — translations.py owned by Plan 02
- [Phase 03-03]: TripDocument and close_trip_db share the same AsyncSession — committed atomically via close_trip_db's session.commit()
- [Phase 03-04]: notify_driver_trip_assignment reloads trip with selectinload after session.commit() — driver.tg_id accessible outside session
- [Phase 03-04]: Trip list filter bar uses GET params (driver_id, vehicle_id) for bookmarkable URLs
- [Phase 03-04]: parse_dt() helper converts datetime-local HTML string or empty string to Python datetime or None
- [Phase 03-05]: trip_detail route registered after trips/create — FastAPI matches in order so /create pattern matched first
- [Phase 03-05]: Fleet active trip detection done Python-side on loaded vehicle.trips — avoids extra DB query
- [Phase 03-05]: total_kzt calculated server-side with fallback to raw amount when amount_kzt is None
- [Phase 03-05]: Trip rows in trips_list use onclick JS navigation for clickability without breaking HTML table structure
- [Phase 04]: LOC-01 (bot location capture) was already complete in location_flow.py from Phase 3; no re-implementation needed
- [Phase 04]: No Alembic migration needed — locations table already in chain via 102c50087403_add_location_model.py
- [Phase 04]: _get_fleet_markers() uses subquery with func.max(created_at) GROUP BY driver_id for latest-per-driver query
- [Phase 04]: /panel/map/markers returns JSONResponse; HTMX polls it every 30s via hx-trigger="every 30s" on hidden div
- [Phase 04]: Leaflet markers updated in-place (setLatLng+setPopupContent) to avoid map flicker on refresh
- [Phase 05]: director.py separate router at /panel/director — keeps panel.py manageable
- [Phase 05]: _parse_date_range() defaults to current month (1st to today) when params absent
- [Phase 05]: CSV uses UTF-8 BOM (\ufeff) for Excel compatibility on Windows
- [Phase 05]: func.coalesce(amount_kzt, amount) for DB-side KZT totals in summary
- [Phase 05]: director_trucks groups trips Python-side (defaultdict by license_plate) — avoids complex GROUP BY
- [Phase 05]: Driver history uses select→join→where (Trip.driver_id) — no subquery needed
- [Phase 05]: director_driver.html has inline <select> dropdown to switch drivers without returning to picker

### Pending Todos

None yet.

### Blockers/Concerns

- DIRECTOR_TG_ID must be set in Railway env vars before Phase 2 anomaly digest notifications are enabled
- FX rate source for multi-currency expenses resolved as static table in Phase 2 — revisit if live rates needed

## Session Continuity

Last session: 2026-03-10
Stopped at: ALL 5 PHASES COMPLETE. Phase 5 added director dashboard: cost summary (DIR-01), per-truck breakdown (DIR-02), CSV export (DIR-03), anomaly history (DIR-04), per-driver history (DIR-05). v1 is feature-complete.
Resume file: None
