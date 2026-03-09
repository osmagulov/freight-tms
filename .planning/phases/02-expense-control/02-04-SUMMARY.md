---
phase: 02-expense-control
plan: 04
subsystem: anomaly-detection
tags: [apscheduler, sqlalchemy, htmx, jinja2, telegram, asyncio]

# Dependency graph
requires:
  - phase: 02-expense-control
    plan: 01
    provides: "FuelAnomaly model with actual_per_100km, norm_per_100km, threshold_per_100km, excess_percent, is_false_alarm, notified columns"
  - phase: 02-expense-control
    plan: 02
    provides: "count_fuel_expenses_for_vehicle(), get_last_fuel_odometer() CRUD functions; process_final_expense() and process_final_expense_direct() in expense_flow.py"
provides:
  - "src/services/anomaly.py with check_fuel_anomaly_after_expense() (ALERT-01 to -03: liters/km*100, 20% threshold, 2 fill-up minimum) and run_anomaly_digest() (ALERT-04: hourly Telegram batch send to DIRECTOR_TG_ID)"
  - "AsyncIOScheduler started in FastAPI lifespan before PTB block with hourly anomaly_digest job"
  - "FUEL expense save hooks in expense_flow.py (both process_final_expense and process_final_expense_direct) that call anomaly check in new session after expense commit"
  - "GET /panel/anomalies listing active (non-false-alarm) FuelAnomaly records with excess percentage"
  - "POST /panel/anomalies/{id}/dismiss that sets is_false_alarm=True and returns HTMX row fragment"
  - "anomalies.html template extending base.html with HTMX dismiss button per row"
  - "base.html nav updated with Аномалии link to /panel/anomalies"
affects:
  - 02-expense-control (Wave 3 complete — all anomaly alerting now operational)
  - director-notifications (DIRECTOR_TG_ID receives hourly batch digest of unnotified anomalies)
  - dispatcher-panel (new Аномалии page in nav)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred import of ptb_app inside run_anomaly_digest() avoids circular import between main.py and anomaly.py (same pattern as panel.py notify_driver_expense_decision)"
    - "Re-fetch expense and vehicle via session.get() in a new async_session after create_expense() commit — avoids detached-instance error on cross-session object access"
    - "APScheduler 3.x start() is synchronous (not awaited); scheduler.shutdown(wait=False) in lifespan cleanup"
    - "HTMX outerHTML swap pattern for inline row dismissal — consistent with expense row approve/reject pattern from plan 02-03"

key-files:
  created:
    - "src/services/anomaly.py"
    - "src/web/templates/anomalies.html"
  modified:
    - "src/main.py"
    - "antigravity_modules/expense_flow.py"
    - "src/web/panel.py"
    - "src/web/templates/base.html"

key-decisions:
  - "Anomaly check wired into both process_final_expense() and process_final_expense_direct() — covers both FUEL paths (with and without photo/comment steps)"
  - "check_fuel_anomaly_after_expense() opens its own session and re-fetches expense/vehicle by ID — required because original create_expense() session is closed before the anomaly check runs"
  - "scheduler starts before the async with ptb_app block — APScheduler lifecycle is independent of Telegram bot lifecycle"

patterns-established:
  - "Anomaly check always runs in a separate session after the original expense session is committed and closed"
  - "run_anomaly_digest uses deferred import for ptb_app to avoid circular dependency at module load time"

requirements-completed:
  - ALERT-01
  - ALERT-02
  - ALERT-03
  - ALERT-04
  - FLEET-03

# Metrics
duration: 18min
completed: 2026-03-09
---

# Phase 2 Plan 04: Anomaly Detection Service Summary

**Fuel consumption anomaly detection with APScheduler hourly Telegram digest to director, HTMX false-alarm dismissal page for dispatcher, and anomaly check hooked into FUEL expense save flow**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-03-09T08:10:20Z
- **Completed:** 2026-03-09T08:28:13Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created src/services/anomaly.py implementing the full ALERT-01 to ALERT-04 requirements: consumption calculation (liters/km * 100), 20% threshold check, 2 prior fill-up minimum guard, and hourly batch Telegram digest to director
- Integrated AsyncIOScheduler into FastAPI lifespan in src/main.py (starts before PTB, shuts down after yield)
- Wired anomaly check into both FUEL expense save paths in expense_flow.py using a new session to re-fetch the committed expense
- Built /panel/anomalies dispatcher feed with HTMX inline false-alarm dismissal, extending the existing base.html pattern

## Task Commits

Each task was committed atomically:

1. **Task 1: Create anomaly service and wire APScheduler into lifespan** - `3c508f8` (feat)
2. **Task 2: Add anomaly feed page to web panel** - `4e42286` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/services/anomaly.py` - check_fuel_anomaly_after_expense() and run_anomaly_digest() functions (ALERT-01 to -04)
- `src/main.py` - AsyncIOScheduler imported, module-level scheduler instance, scheduler.add_job/start in lifespan, scheduler.shutdown after yield
- `antigravity_modules/expense_flow.py` - Anomaly check block added to both process_final_expense() and process_final_expense_direct() after successful FUEL expense commit
- `src/web/panel.py` - FuelAnomaly imported; GET /panel/anomalies and POST /panel/anomalies/{id}/dismiss routes added
- `src/web/templates/anomalies.html` - New template: extends base.html, anomaly table with HTMX dismiss button per row
- `src/web/templates/base.html` - Added Аномалии nav link pointing to /panel/anomalies

## Decisions Made
- Anomaly check wired into both `process_final_expense()` and `process_final_expense_direct()` — required because PER_DIEM uses the direct path while FUEL with photo uses the standard path; both save FUEL expenses so both need the hook
- `check_fuel_anomaly_after_expense()` opens a fresh `async_session` and re-fetches the expense and vehicle by ID — the original `create_expense()` session is closed before the anomaly block runs, making the original expense object detached; re-fetching via `session.get()` gives a fresh, attached instance
- APScheduler `start()` is NOT awaited (synchronous call per APScheduler 3.x API); `scheduler.shutdown(wait=False)` in lifespan cleanup handles graceful stop

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
- `DIRECTOR_TG_ID` must be set in Railway env vars (int) before anomaly digest notifications are sent. If set to 0 (default), `run_anomaly_digest()` returns early without sending.

## Next Phase Readiness
- All Phase 2 anomaly alerting requirements (ALERT-01 to ALERT-04) are fully implemented
- Phase 2 Wave 3 complete — expense control, approval queue, and anomaly detection all operational
- Director will receive hourly Telegram digests of unnotified fuel anomalies once DIRECTOR_TG_ID is configured in Railway
- Dispatcher can view and dismiss false alarms at /panel/anomalies

---
*Phase: 02-expense-control*
*Completed: 2026-03-09*
