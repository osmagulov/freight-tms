---
phase: 03-trip-management
plan: "05"
type: execute
wave: 4
depends_on:
  - "03-04"
  - "03-03"
files_modified:
  - src/web/panel.py
  - src/web/templates/trip_detail.html
  - src/web/templates/fleet.html
autonomous: false
requirements:
  - TRIP-06
  - TRIP-07
  - FLEET-01
  - FLEET-02

must_haves:
  truths:
    - "Dispatcher visits /panel/trips/{id} and sees all expenses, attached documents, and location pings for that trip"
    - "Trip detail page shows a total expense cost in KZT"
    - "Dispatcher visits /panel/fleet and sees every truck with its status (AVAILABLE/ON_TRIP/MAINTENANCE)"
    - "ON_TRIP trucks on fleet page show the current driver name and trip route"
    - "Clicking a trip row in the trip list navigates to the detail page without errors"
  artifacts:
    - path: "src/web/panel.py"
      provides: "GET /panel/trips/{trip_id} and GET /panel/fleet routes"
      contains: "/fleet"
    - path: "src/web/templates/trip_detail.html"
      provides: "Trip detail page with 5 sections: info, expenses, documents, locations, total"
      min_lines: 60
    - path: "src/web/templates/fleet.html"
      provides: "Fleet dashboard with status badge per vehicle and current driver/trip link for ON_TRIP"
      min_lines: 40
  key_links:
    - from: "GET /panel/trips/{trip_id} in panel.py"
      to: "Trip.expenses + Trip.documents via selectinload"
      via: "selectinload(Trip.documents) in SQLAlchemy options"
      pattern: "selectinload.*documents"
    - from: "GET /panel/fleet in panel.py"
      to: "active trip detection"
      via: "Python-side filter on vehicle.trips for status == ACTIVE"
      pattern: "TripStatus.ACTIVE"
    - from: "fleet.html"
      to: "/panel/trips/{active_trip.id}"
      via: "anchor link on active trip row"
      pattern: "panel/trips.*active_trip"
---

<objective>
Add trip detail and fleet dashboard routes to the web panel, completing full trip history visibility (TRIP-06, TRIP-07) and fleet status dashboard (FLEET-01, FLEET-02).

Purpose: Gives dispatchers full visibility into trip costs, documents, and live fleet status.
Output: Two new panel routes, two new templates, and a human verification checkpoint confirming the full Phase 3 system works end-to-end.
</objective>

<execution_context>
@/Users/osmagulov/.claude/get-shit-done/workflows/execute-plan.md
@/Users/osmagulov/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@src/web/panel.py
@src/web/templates/base.html
@.planning/phases/03-trip-management/03-04-SUMMARY.md
@.planning/phases/03-trip-management/03-03-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add /panel/trips/{id} and /panel/fleet routes to panel.py</name>
  <files>src/web/panel.py</files>
  <action>
1. Add `LocationUpdate` to the models import if not present:
