---
phase: 03-trip-management
plan: "03"
type: execute
wave: 2
depends_on:
  - "03-01"
files_modified:
  - antigravity_modules/trip_closing.py
  - src/services/r2.py
  - antigravity_modules/expense_crud.py
autonomous: true
requirements:
  - TRIP-04
  - TRIP-05

must_haves:
  truths:
    - "r2.py upload_to_r2 accepts a content_type parameter (default 'image/jpeg') and upload_photo_to_r2 alias still works"
    - "Driver closing a trip goes through: end odometer → delivery status (3-button keyboard) → closing doc upload → done"
    - "Closing document (photo or PDF) is uploaded to R2 and saved as a TripDocument record with the r2_url"
    - "Vehicle.status is set to AVAILABLE after trip closes"
    - "Trip.delivery_status is saved as DELIVERED, PARTIAL, or FAILED"
  artifacts:
    - path: "src/services/r2.py"
      provides: "upload_to_r2 with content_type param + upload_photo_to_r2 backward-compat alias"
      contains: "content_type"
    - path: "antigravity_modules/trip_closing.py"
      provides: "Updated ConversationHandler with 3 states: odometer, delivery status, doc upload"
      contains: "AWAITING_DELIVERY_STATUS"
    - path: "antigravity_modules/expense_crud.py"
      provides: "close_trip_db CRUD function"
      contains: "close_trip_db"
  key_links:
    - from: "trip_closing.py receive_closing_docs"
      to: "src.services.r2.upload_to_r2"
      via: "await upload_to_r2(bytes(file_bytes), key, mime)"
      pattern: "upload_to_r2.*content_type|upload_to_r2.*mime"
    - from: "trip_closing.py receive_closing_docs"
      to: "TripDocument model"
      via: "session.add(TripDocument(trip_id=..., r2_url=...))"
      pattern: "TripDocument\\("
    - from: "expense_crud.close_trip_db"
      to: "Vehicle"
      via: "sa_update(Vehicle).values(status=VehicleStatus.AVAILABLE)"
      pattern: "VehicleStatus.AVAILABLE"
---

<objective>
Extend r2.py to support PDF uploads via a content_type parameter, rewrite trip_closing.py to add a delivery status step and upload closing documents to R2, and add close_trip_db to expense_crud.py for atomic trip+vehicle status updates.

Purpose: Makes the trip close flow production-ready with durable document storage and correct fleet status transitions.
Output: Updated r2.py with content_type param, rewritten trip_closing.py with 3 states, close_trip_db CRUD function.
</objective>

<execution_context>
@/Users/osmagulov/.claude/get-shit-done/workflows/execute-plan.md
@/Users/osmagulov/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@src/services/r2.py
@antigravity_modules/trip_closing.py
@antigravity_modules/expense_crud.py
@.planning/phases/03-trip-management/03-01-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add content_type parameter to r2.py</name>
  <files>src/services/r2.py</files>
  <action>
Three changes to r2.py:

1. Update `_upload_sync` signature to accept content_type:
