---
phase: 01-infrastructure-and-foundation
plan: 02
subsystem: infra
tags: [fastapi, python-telegram-bot, webhook, lifespan, pickle-persistence, sqlalchemy]

# Dependency graph
requires:
  - phase: 01-infrastructure-and-foundation/01-01
    provides: settings.WEBHOOK_URL field, link_driver_to_vehicle() crud function, async_session
provides:
  - FastAPI app with asynccontextmanager lifespan pattern (no deprecated on_event)
  - POST /telegram webhook endpoint that feeds updates into PTB
  - GET / healthcheck endpoint
  - PTB Application built in webhook mode (.updater(None)) with PicklePersistence at /data/bot_persistence.pkl
  - register_handlers() function for attaching all bot handlers to any PTB app instance
  - Fixed driver-vehicle FK link in receive_vehicle() (REG-02 resolved)
  - registration ConversationHandler with persistent=True
affects:
  - 01-03 (persistent conversation handlers for other flows)
  - 01-04 (Railway deploy — webhook URL and lifespan startup)
  - All future plans that add bot handlers (use register_handlers())

# Tech tracking
tech-stack:
  added: [python-telegram-bot PicklePersistence, asynccontextmanager lifespan]
  patterns:
    - lifespan context manager for FastAPI app startup/shutdown (replaces deprecated on_event)
    - PicklePersistence created in main.py and injected into PTB app so bot_app.py stays testable
    - register_handlers() separates handler registration from app construction
    - .updater(None) disables polling — webhook mode is the only update source

key-files:
  created: []
  modified:
    - src/main.py
    - src/bot/bot_app.py

key-decisions:
  - "PicklePersistence created in main.py lifespan, not in bot_app.py, so bot_app.py stays testable without disk side effects"
  - "register_handlers() extracted as standalone function so lifespan can attach handlers to persistence-equipped app while create_bot_app() remains for local polling tests"
  - "WEBHOOK_URL absence logged as warning (not error) to allow local development without Railway env vars"

patterns-established:
  - "Lifespan pattern: all startup/shutdown logic inside asynccontextmanager lifespan(app: FastAPI)"
  - "Handler registration: always call register_handlers(app) — never inline add_handler calls in create_bot_app"
  - "Webhook-only PTB: always build with .updater(None) in production; create_bot_app() is polling-only for local dev"

requirements-completed: [INFRA-01, REG-01, REG-02]

# Metrics
duration: 8min
completed: 2026-03-09
---

# Phase 1 Plan 02: FastAPI Lifespan + PTB Webhook Integration Summary

**Single-process FastAPI+PTB server using asynccontextmanager lifespan and /telegram webhook endpoint, with driver-vehicle FK bug fixed so registration flow produces fully linked records**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-08T22:41:00Z
- **Completed:** 2026-03-08T22:49:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Rewrote src/main.py with asynccontextmanager lifespan pattern — no deprecated @app.on_event anywhere
- PTB Application runs webhook-only inside FastAPI process: built with .updater(None), PicklePersistence at /data/bot_persistence.pkl, started/stopped inside lifespan
- POST /telegram endpoint decodes updates via Update.de_json() and feeds them to ptb_app.process_update()
- Extracted register_handlers() from create_bot_app() so main.py lifespan can attach handlers after persistence is bound
- Fixed REG-02: receive_vehicle() now calls link_driver_to_vehicle(session, driver.id, vehicle.id) so driver.vehicle_id FK is always set after registration
- registration ConversationHandler gains persistent=True so multi-step state survives bot restarts

## Task Commits

Each task was committed atomically (Tasks 1 and 2 committed together due to mutual import dependency):

1. **Task 1: Rewrite src/main.py with lifespan + PTB webhook** + **Task 2: Refactor bot_app.py, fix receive_vehicle FK** - `3181b03` (feat)

## Files Created/Modified
- `src/main.py` - FastAPI app with lifespan context manager, PicklePersistence, PTB startup/shutdown, /telegram POST endpoint, GET / healthcheck
- `src/bot/bot_app.py` - Added register_handlers(), fixed receive_vehicle() FK bug, updated create_bot_app() to delegate to register_handlers(), added persistent=True to registration_conv

## Decisions Made
- PicklePersistence created in main.py lifespan (not bot_app.py) so bot_app.py stays side-effect-free and testable in isolation
- register_handlers() extracts handler registration so it can be called with any PTB app instance (persistence-equipped in production, plain in tests)
- WEBHOOK_URL absence is a warning not an error — local development works without Railway env vars
- Tasks 1 and 2 committed together because main.py imports register_handlers from bot_app.py; committing separately would leave a broken HEAD

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Tasks 1 and 2 have a mutual import dependency (main.py imports register_handlers from bot_app.py), so verification of Task 1 import required Task 2 to be complete first. Both tasks were committed atomically in a single commit rather than two separate commits. This matches the plan's intent as both files form one integration unit.

## User Setup Required
None - no external service configuration required beyond the WEBHOOK_URL env var documented in plan 01-04.

## Next Phase Readiness
- FastAPI+PTB integration is complete and verified importable
- Plan 03 can now add persistent=True to the remaining conversation handlers (trip_opening, expense_flow, location_flow, trip_closing)
- Railway deploy (Plan 04) can use the lifespan webhook pattern as-is

## Self-Check: PASSED

- FOUND: src/main.py
- FOUND: src/bot/bot_app.py
- FOUND: .planning/phases/01-infrastructure-and-foundation/01-02-SUMMARY.md
- FOUND commit: 3181b03 (task commit)
- FOUND commit: 8330b9d (docs commit)

---
*Phase: 01-infrastructure-and-foundation*
*Completed: 2026-03-09*
