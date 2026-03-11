---
phase: 02-expense-control
plan: 02
subsystem: bot
tags: [python-telegram-bot, conversation-handler, fsm, fx-rates, odometer-validation, idempotency]

# Dependency graph
requires:
  - phase: 02-expense-control
    plan: 01
    provides: "Expense model with liters, odometer_reading, station, fx_rate, amount_kzt, idempotency_minute columns and uq_expense_idempotent UniqueConstraint"
provides:
  - "src/services/fx.py with FX_RATES_TO_KZT static dict (KZT=1.0, RUB=5.5, USD=450, EUR=490) and get_fx_rate()"
  - "get_last_fuel_odometer() CRUD function for per-vehicle odometer validation"
  - "count_fuel_expenses_for_vehicle() CRUD function for anomaly detection minimum check"
  - "Updated create_expense() accepting all Phase 2 fields with IntegrityError idempotency handling"
  - "FUEL flow: liters -> odometer (validated) -> station -> amount -> currency -> photo (optional) -> saved"
  - "Odometer validation: rejects new_odo <= last_odo with exp_odo_too_low, rejects new_odo > last_odo + 5000 with exp_odo_too_high"
  - "PER_DIEM flow: amount -> currency -> city (stored in comment) -> saved, no photo step"
  - "FINE/REPAIR/OTHER flow: amount -> currency -> photo (optional) -> comment/reason"
  - "Currency keyboard shows KZT, RUB, USD, EUR (CNY removed)"
  - "Duplicate idempotency: create_expense() returns None, bot replies with exp_duplicate message"
affects:
  - 02-expense-control (Wave 3: approval queue, anomaly detection use create_expense output)
  - approval queue (expense.fx_rate, expense.amount_kzt, expense.station now populated)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Static FX rate dict as src/services/fx.py singleton — updated manually, no live API dependency"
    - "IntegrityError catch-and-return-None pattern for idempotency in async SQLAlchemy"
    - "ConversationHandler state integers 7-10 for Phase 2 type-specific bot flow branches"
    - "process_final_expense_direct() helper to re-use save logic from flows that skip the AWAITING_EXPENSE_COMMENT state"

key-files:
  created:
    - "src/services/fx.py"
  modified:
    - "antigravity_modules/expense_crud.py"
    - "antigravity_modules/expense_flow.py"
    - "antigravity_modules/translations.py"

key-decisions:
  - "FX rate source is a static dict in src/services/fx.py — no live API, updated manually; resolves the pre-phase blocker"
  - "PER_DIEM city is stored in expense.comment field — no new DB column needed"
  - "process_final_expense_direct() extracted as helper so PER_DIEM flow (which skips photo step) reuses identical save logic"
  - "Currency choices are KZT, RUB, USD, EUR — CNY removed from keyboard per plan spec"

patterns-established:
  - "All expense types route through receive_expense_type() dispatcher -> type-specific state chain -> AWAITING_EXPENSE_AMOUNT -> currency -> photo/city -> comment/save"
  - "Fuel-specific data (liters, odometer_reading, station) stored in context.user_data during multi-step flow and passed to create_expense() at final step"
  - "vehicle_id stored in context.user_data at trip load time (add_expense_handler) so odometer validation handler can query get_last_fuel_odometer() without DB re-query for driver"

requirements-completed:
  - EXP-01
  - EXP-02
  - EXP-03
  - EXP-04
  - EXP-05
  - EXP-07
  - EXP-08

# Metrics
duration: 4min
completed: 2026-03-09
---

# Phase 2 Plan 02: Expense Flow Refactor Summary

**Type-specific Telegram bot expense flows (FUEL with odometer validation, PER_DIEM with city, FINE/REPAIR/OTHER with comment) backed by static FX rate service and idempotency-safe create_expense()**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-09T03:51:36Z
- **Completed:** 2026-03-09T03:55:04Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created static FX rate service (src/services/fx.py) with KZT/RUB/USD/EUR rates and get_fx_rate() — resolves the pre-phase FX rate blocker
- Refactored expense_crud.py: added get_last_fuel_odometer(), count_fuel_expenses_for_vehicle(), and updated create_expense() with all Phase 2 fields plus IntegrityError idempotency handling
- Refactored expense_flow.py ConversationHandler: 4 new states (AWAITING_FUEL_LITERS=7, AWAITING_FUEL_ODOMETER=8, AWAITING_FUEL_STATION=9, AWAITING_DIEM_CITY=10), type-specific routing in receive_expense_type(), odometer validation with two distinct error messages, PER_DIEM city via receive_diem_city(), duplicate detection via exp_duplicate message
- Added 10 new translation strings to both Russian and Kazakh dicts in translations.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Create FX service and update expense CRUD** - `b938f54` (feat)
2. **Task 2: Refactor expense_flow.py with type-specific branches and update translations** - `b3209fd` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/services/fx.py` - Static FX rate dict FX_RATES_TO_KZT and get_fx_rate() function
- `antigravity_modules/expense_crud.py` - Added get_last_fuel_odometer(), count_fuel_expenses_for_vehicle(); updated create_expense() with Phase 2 fields and IntegrityError handling
- `antigravity_modules/expense_flow.py` - Full refactor: type-specific states 7-10, new handler functions, updated receive_expense_type() dispatcher, updated receive_expense_currency(), updated process_final_expense() with all Phase 2 fields and duplicate handling, process_final_expense_direct() helper
- `antigravity_modules/translations.py` - Added 10 new keys in both ru and kk dicts: exp_ask_liters, exp_ask_odometer, exp_odo_too_low, exp_odo_too_high, exp_odo_error, exp_ask_station, exp_ask_city, exp_ask_reason, exp_ask_subcategory, exp_duplicate

## Decisions Made
- FX rate source resolved as static dict in src/services/fx.py (was listed as a pre-phase blocker in STATE.md). No live API — rates updated manually. Rationale: drivers operate in areas with unreliable connectivity; live API adds failure mode with no benefit for internal accounting.
- PER_DIEM city stored in `expense.comment` — no new DB column required, consistent with the comment field's purpose as free-text context.
- `process_final_expense_direct()` extracted so PER_DIEM (which skips AWAITING_EXPENSE_PHOTO and AWAITING_EXPENSE_CARD_PHOTO states) reuses identical save logic without code duplication.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- System `python` command not found (macOS uses `python3`); verified using project virtualenv at `venv/bin/python3`. All verification commands confirmed correct with venv python.

## User Setup Required
None - no external service configuration required. FX rates are hardcoded in src/services/fx.py and can be updated by editing the file directly.

## Next Phase Readiness
- All Phase 2 expense submission flows are complete and ready for testing
- Approval queue (Wave 3) can now read expense.fx_rate, expense.amount_kzt, expense.station populated by this plan
- Anomaly detection scheduler can call count_fuel_expenses_for_vehicle() and get_last_fuel_odometer() from this plan
- The pre-phase blocker "FX rate source for multi-currency expenses needs a decision before Phase 2 implementation" is now resolved

## Self-Check: PASSED

- src/services/fx.py: FOUND
- antigravity_modules/expense_crud.py: FOUND
- antigravity_modules/expense_flow.py: FOUND
- antigravity_modules/translations.py: FOUND
- .planning/phases/02-expense-control/02-02-SUMMARY.md: FOUND
- Commit b938f54 (Task 1): FOUND
- Commit b3209fd (Task 2): FOUND

---
*Phase: 02-expense-control*
*Completed: 2026-03-09*
