---
phase: 03-trip-management
plan: "02"
type: execute
wave: 2
depends_on:
  - "03-01"
files_modified:
  - antigravity_modules/trip_opening.py
  - antigravity_modules/expense_crud.py
  - antigravity_modules/translations.py
autonomous: true
requirements:
  - TRIP-03

must_haves:
  truths:
    - "Driver tapping 'НАЧАТЬ РЕЙС' with no PLANNED trip sees a 'no assigned trip' message and returns to menu"
    - "Driver with a PLANNED trip sees route, cargo, and client details and is asked to confirm departure with Yes/No keyboard"
    - "After confirming and entering start odometer, trip status becomes ACTIVE and vehicle status becomes ON_TRIP"
    - "get_planned_trip_for_driver() and activate_trip() functions exist in expense_crud.py"
    - "All Phase 3 translation keys (opening + closing) are present in both ru and kk dicts"
  artifacts:
    - path: "antigravity_modules/trip_opening.py"
      provides: "Refactored trip opening ConversationHandler — dispatcher-first model"
      min_lines: 80
    - path: "antigravity_modules/expense_crud.py"
      provides: "get_planned_trip_for_driver and activate_trip CRUD functions"
      contains: "get_planned_trip_for_driver"
    - path: "antigravity_modules/translations.py"
      provides: "All Phase 3 bot translation keys for opening and closing flows"
      contains: "open_trip_no_planned"
  key_links:
    - from: "trip_opening.py open_trip_handler"
      to: "expense_crud.get_planned_trip_for_driver"
      via: "async call within async_session block"
      pattern: "get_planned_trip_for_driver"
    - from: "trip_opening.py receive_start_odometer"
      to: "expense_crud.activate_trip"
      via: "async call that updates Trip.status and Vehicle.status"
      pattern: "activate_trip"
---

<objective>
Rewrite trip_opening.py so drivers see their dispatcher-assigned PLANNED trip instead of entering route/cargo manually. Add supporting CRUD functions and all Phase 3 bot translation keys (opening + closing) to translations.py.

Purpose: Fixes hardcoded vehicle_id=1 bug and aligns bot trip-open flow with dispatcher-first model where dispatcher pre-fills route, cargo, client, and dates.
Output: Refactored trip_opening.py, two new CRUD functions in expense_crud.py, complete Phase 3 bot translations.
</objective>

<execution_context>
@/Users/osmagulov/.claude/get-shit-done/workflows/execute-plan.md
@/Users/osmagulov/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@antigravity_modules/trip_opening.py
@antigravity_modules/expense_crud.py
@antigravity_modules/translations.py
@.planning/phases/03-trip-management/03-01-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add CRUD functions to expense_crud.py</name>
  <files>antigravity_modules/expense_crud.py</files>
  <action>
First, update the import at the top of expense_crud.py to include TripStatus and VehicleStatus:
