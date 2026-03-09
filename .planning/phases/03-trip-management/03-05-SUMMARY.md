---
phase: 03-trip-management
plan: "05"
subsystem: ui
tags: [fastapi, jinja2, htmx, sqlalchemy, selectinload]

# Dependency graph
requires:
  - phase: 03-trip-management
    provides: "Trip, TripDocument, Expense, LocationUpdate models; trip creation routes"
  - phase: 02-expense-control
    provides: "Expense approval workflow; amount_kzt field on expenses"
provides:
  - "GET /panel/trips/{trip_id} — trip detail page with expenses, documents, location pings"
  - "GET /panel/fleet — fleet dashboard showing all vehicles with status badges and active trip info"
  - "trip_detail.html — 5-section detail view (info, expenses, total KZT, documents, locations)"
  - "fleet.html — fleet dashboard with summary bar and per-vehicle status badges"
  - "Парк nav link in base.html navbar"
  - "Clickable trip rows in trips_list.html navigating to detail page"
affects: [04-reporting, 05-analytics]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "selectinload chaining: selectinload(Trip.documents) for eager-loading relationships"
    - "Python-side active trip detection: next(filter on vehicle.trips for TripStatus.ACTIVE)"
    - "KZT total calculated server-side: sum(amount_kzt or amount for each expense)"

key-files:
  created:
    - src/web/templates/trip_detail.html
    - src/web/templates/fleet.html
  modified:
    - src/web/panel.py
    - src/web/templates/base.html
    - src/web/templates/trips_list.html

key-decisions:
  - "trip_detail route registered after trips/create — FastAPI matches in order, so /create is matched first"
  - "Fleet active trip detection done Python-side on loaded vehicle.trips to avoid extra DB query"
  - "total_kzt calculated server-side using amount_kzt if set, otherwise falling back to raw amount"
  - "Trip rows in trips_list use onclick JS navigation for clickability without wrapping table row in anchor"

patterns-established:
  - "Pattern: selectinload chain — use selectinload(Vehicle.trips).selectinload(Trip.driver) for nested eager-loading"
  - "Pattern: Python-side filter — filter TripStatus.ACTIVE on loaded collection rather than subquery"

requirements-completed: [TRIP-06, TRIP-07, FLEET-01, FLEET-02]

# Metrics
duration: 8min
completed: 2026-03-09
---

# Phase 3 Plan 05: Trip Detail and Fleet Dashboard Summary

**Trip detail page (/panel/trips/{id}) with expenses/documents/locations + fleet dashboard (/panel/fleet) with per-vehicle status badges and active trip links**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-09T15:40:56Z
- **Completed:** 2026-03-09T15:48:00Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments
- Added GET /panel/trips/{trip_id} route loading trip with selectinload(driver, vehicle, expenses, documents) and location pings separately; calculates total_kzt server-side
- Added GET /panel/fleet route loading all vehicles with trips+driver eager-loaded; Python-side filter for TripStatus.ACTIVE to find active_trip per vehicle
- Created trip_detail.html (201 lines) with 5 sections: info grid, expenses table, KZT total block, documents list with R2 links, location pings with Google Maps links
- Created fleet.html (110 lines) with summary counts bar and table with status badges; ON_TRIP rows show driver name, route, and link to /panel/trips/{active_trip.id}
- Added "Парк" nav link to base.html and clickable rows to trips_list.html

## Task Commits

Each task was committed atomically:

1. **Task 1: Add /panel/trips/{id} and /panel/fleet routes to panel.py** - `7eb5b6b` (feat)
2. **Task 2: Create trip_detail.html with 5 sections** - `9e9f416` (feat)
3. **Task 3: Create fleet.html dashboard** - `94bfc7c` (feat)
4. **Task 4: Add Парк nav link and clickable trip rows** - `95953ca` (feat)

**Plan metadata:** (docs commit — see final_commit)

## Files Created/Modified
- `src/web/panel.py` - Added LocationUpdate+VehicleStatus imports; GET /panel/trips/{trip_id} and GET /panel/fleet routes
- `src/web/templates/trip_detail.html` - New: 5-section trip detail page (201 lines)
- `src/web/templates/fleet.html` - New: Fleet dashboard with status badges (110 lines)
- `src/web/templates/base.html` - Added Парк nav link pointing to /panel/fleet
- `src/web/templates/trips_list.html` - Made trip rows clickable via onclick navigation

## Decisions Made
- trip_detail route registered after trips/create — FastAPI matches routes in order so /create pattern is matched before /{trip_id}
- Fleet active trip detection done Python-side: vehicle.trips is already loaded by selectinload, no extra DB query needed
- total_kzt calculated server-side with fallback to raw amount when amount_kzt is None (handles pre-Phase-2 expenses)
- Trip rows use onclick JS navigation (not anchor wrapping) to keep HTML table structure valid

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 is now complete: all 5 plans executed (trip models, FSM rewrite, trip closing, dispatcher UI, detail+fleet)
- Requirements TRIP-01 through TRIP-07 and FLEET-01/FLEET-02 all fulfilled
- Ready for Phase 4 (Reporting) or Phase 5 (Analytics)

## Self-Check: PASSED

All files found and all commits verified:
- FOUND: src/web/panel.py
- FOUND: src/web/templates/trip_detail.html (201 lines)
- FOUND: src/web/templates/fleet.html (110 lines)
- FOUND: src/web/templates/base.html
- FOUND: src/web/templates/trips_list.html
- FOUND: 03-05-SUMMARY.md
- FOUND commit: 7eb5b6b (panel.py routes)
- FOUND commit: 9e9f416 (trip_detail.html)
- FOUND commit: 94bfc7c (fleet.html)
- FOUND commit: 95953ca (nav + clickable rows)

---
*Phase: 03-trip-management*
*Completed: 2026-03-09*
