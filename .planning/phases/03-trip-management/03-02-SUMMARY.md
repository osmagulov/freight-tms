---
phase: 03-trip-management
plan: "02"
subsystem: bot
tags: [telegram-bot, python-telegram-bot, sqlalchemy, async, conversationhandler, i18n]

# Dependency graph
requires:
  - phase: 03-trip-management
    plan: "01"
    provides: Trip model with client_name/planned_departure/planned_arrival columns + TripDocument model

provides:
  - Dispatcher-first trip opening flow in trip_opening.py (driver sees assigned PLANNED trip, not manual entry)
  - get_planned_trip_for_driver() CRUD function in expense_crud.py
  - activate_trip() CRUD function that updates Trip.status=ACTIVE and Vehicle.status=ON_TRIP atomically
  - All Phase 3 bot translation keys (opening + closing) in both ru and kk

affects:
  - 03-trip-management plan 03 (document upload — trip must be ACTIVE first)
  - 03-trip-management plan 04 (dispatcher panel — can now show ACTIVE trips)
  - 03-trip-management plan 05 (trip tracking)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Dispatcher-first model — driver taps НАЧАТЬ РЕЙС to activate a pre-assigned PLANNED trip, never entering route/cargo manually
    - activate_trip() opens its own async_session and re-fetches Trip and Vehicle — same pattern as check_fuel_anomaly_after_expense() from Phase 2
    - Yes/No ReplyKeyboardMarkup built from localised btn_yes/btn_no translation keys so button text matches driver language
    - ConversationHandler name="trip_opening" persistent=True preserved from original — FSM state survives Railway redeployments

key-files:
  created: []
  modified:
    - antigravity_modules/trip_opening.py
    - antigravity_modules/expense_crud.py
    - antigravity_modules/translations.py

key-decisions:
  - "trip_opening.py is a full rewrite — removed AWAITING_ROUTE/CARGO/DOCUMENTS states, replaced with AWAITING_CONFIRMATION + AWAITING_START_ODOMETER dispatcher-first flow"
  - "activate_trip() updates both Trip and Vehicle in a single async_session commit — no partial state possible if session fails"
  - "Legacy open_trip_ask_route/cargo/docs keys retained in translations.py — any existing PicklePersistence sessions using old states will reach a fallback gracefully"
  - "btn_yes/btn_no added as explicit translation keys so confirmation keyboard buttons are language-aware"

patterns-established:
  - "Phase 3 trip activation pattern: get_planned_trip_for_driver → show details → Yes/No → start_odometer → activate_trip"
  - "Translation key naming: open_trip_* for opening flow, close_trip_* for closing flow — consistent prefix pattern"

requirements-completed:
  - TRIP-03

# Metrics
duration: 8min
completed: 2026-03-09
---

# Phase 3 Plan 02: Trip Opening Flow (Dispatcher-First Model) Summary

**Full rewrite of trip_opening.py from manual-entry MVP to dispatcher-first activation flow: driver sees assigned PLANNED trip details and confirms departure; activates trip and vehicle atomically via two new CRUD functions**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-09T13:30:00Z
- **Completed:** 2026-03-09T13:38:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Rewrote `trip_opening.py`: removed manual route/cargo/document entry; driver now taps НАЧАТЬ РЕЙС, sees dispatcher-assigned trip details (route/cargo/client/planned departure), confirms Yes/No, enters start odometer
- Added `get_planned_trip_for_driver()` to `expense_crud.py`: queries PLANNED trip for driver ordered by created_at ascending
- Added `activate_trip()` to `expense_crud.py`: atomically sets `Trip.status=ACTIVE`, `Trip.start_odometer`, and `Vehicle.status=ON_TRIP` in one session commit
- Added all Phase 3 trip opening translation keys to both `ru` and `kk` dicts: `open_trip_no_planned`, `open_trip_confirm_details`, `open_trip_confirm_prompt`, `btn_yes`, `btn_no`, `open_trip_activate_error`, updated `open_trip_success`
- Fixed hardcoded `vehicle_id=1` bug — vehicle_id now comes from the PLANNED trip record

## Task Commits

Each task was committed atomically:

1. **Task 1: Add CRUD functions to expense_crud.py** - `cfd1ba5` (feat)
2. **Task 2: Rewrite trip_opening.py dispatcher-first flow** - `3fa4266` (feat)
3. **Task 3: Add Phase 3 translation keys to translations.py** - `80f02b1` (feat)

**Plan metadata:** `[pending]` (docs: complete plan)

## Files Created/Modified
- `antigravity_modules/trip_opening.py` - Full rewrite: 187 lines, dispatcher-first flow with AWAITING_CONFIRMATION + AWAITING_START_ODOMETER states; ConversationHandler name="trip_opening" persistent=True
- `antigravity_modules/expense_crud.py` - Added TripStatus/Vehicle/VehicleStatus imports; get_planned_trip_for_driver() and activate_trip() appended
- `antigravity_modules/translations.py` - Added 8 new Phase 3 opening keys per language; updated open_trip_success signature; kept legacy keys for PicklePersistence compatibility

## Decisions Made
- **Full rewrite vs. modification:** The old flow (AWAITING_ROUTE → AWAITING_CARGO → AWAITING_DOCUMENTS → AWAITING_START_ODOMETER) was incompatible with the dispatcher-first model. States reduced to two (AWAITING_CONFIRMATION, AWAITING_START_ODOMETER).
- **activate_trip() atomicity:** Both Trip and Vehicle are updated in one session.commit() — no partial update is possible if the DB call fails.
- **Legacy translation keys retained:** Old `open_trip_ask_route`, `open_trip_ask_cargo`, `open_trip_ask_docs`, `open_trip_docs_error` keys kept in both dicts. Any drivers whose PicklePersistence has the bot in an old ConversationHandler state will still get a readable message from get_text() fallback rather than a raw key string.
- **btn_yes/btn_no as translation keys:** Confirmation keyboard buttons need to match exactly what the driver types to pass the `if text == yes_value` check in `receive_confirmation()`. Making them translation keys ensures language-aware comparison.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added negative odometer guard in receive_start_odometer**
- **Found during:** Task 2 (trip_opening.py rewrite)
- **Issue:** `int(odometer_text)` would succeed for negative values like "-100", creating an invalid trip record
- **Fix:** Added `if odometer < 0: raise ValueError("negative odometer")` after the int() cast
- **Files modified:** antigravity_modules/trip_opening.py
- **Verification:** ValueError raised → `open_trip_odo_error` shown, state stays in AWAITING_START_ODOMETER
- **Committed in:** 3fa4266 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor guard added. No scope creep.

## Issues Encountered
None — all tasks executed cleanly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 03 (document upload): `activate_trip()` ensures trip is ACTIVE before document upload handlers check status
- Plan 04 (dispatcher panel): Can now query trips in ACTIVE status with correct vehicle_id linkage
- Plan 05 (trip tracking): `delivery_status` column available on Trip for status updates during active trip

---
*Phase: 03-trip-management*
*Completed: 2026-03-09*

## Self-Check: PASSED

- FOUND: antigravity_modules/trip_opening.py (187 lines, full rewrite)
- FOUND: antigravity_modules/expense_crud.py (138 lines, 2 new functions)
- FOUND: antigravity_modules/translations.py (197 lines, Phase 3 keys in both ru and kk)
- FOUND: .planning/phases/03-trip-management/03-02-SUMMARY.md
- Commits cfd1ba5, 3fa4266, 80f02b1 created during execution
