---
phase: 03-trip-management
plan: "04"
type: execute
wave: 3
depends_on:
  - "03-01"
  - "03-02"
files_modified:
  - src/web/panel.py
  - src/web/templates/trips_create.html
  - src/web/templates/trips_list.html
  - src/web/templates/base.html
autonomous: true
requirements:
  - TRIP-01
  - TRIP-02

must_haves:
  truths:
    - "Dispatcher opens /panel/trips and sees a table of all trips with status badges and filter controls"
    - "Dispatcher opens /panel/trips/create, selects truck and driver, fills route/cargo/client/dates, submits"
    - "After submission, dispatcher is redirected to /panel/trips and the assigned driver receives a Telegram notification"
    - "Telegram notification to driver includes trip ID, route, cargo, and client name"
  artifacts:
    - path: "src/web/panel.py"
      provides: "GET /panel/trips, GET /panel/trips/create, POST /panel/trips/create routes + notify_driver_trip_assignment"
      contains: "trips/create"
    - path: "src/web/templates/trips_create.html"
      provides: "Trip creation form with driver/vehicle selects, text inputs for route/cargo/client, datetime-local inputs for dates"
      min_lines: 40
    - path: "src/web/templates/trips_list.html"
      provides: "Trip list table with status badges, filter bar, and link to create"
      min_lines: 30
    - path: "src/web/templates/base.html"
      provides: "Updated nav with Рейсы and Флот links"
      contains: "/panel/trips"
  key_links:
    - from: "POST /panel/trips/create in panel.py"
      to: "notify_driver_trip_assignment()"
      via: "await after session.commit()"
      pattern: "notify_driver_trip_assignment"
    - from: "trips_create.html form"
      to: "POST /panel/trips/create"
      via: "action='/panel/trips/create' method='post'"
      pattern: "action.*trips/create"
---

<objective>
Add trip creation and trip list routes to the web panel so dispatchers can create trips, assign them to drivers, and view all trips in a filterable list. The assigned driver receives an immediate Telegram bot notification.

Purpose: Closes TRIP-01 (dispatcher creates trip from web panel) and TRIP-02 (driver receives notification).
Output: Three new routes in panel.py, two new templates, updated base.html navigation.
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
@src/web/templates/expenses.html
@.planning/phases/03-trip-management/03-01-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add trip routes + notify function to panel.py</name>
  <files>src/web/panel.py</files>
  <action>
1. Update imports at top of panel.py — add TripDocument and TripStatus to the models import:
