---
phase: 02-expense-control
plan: 03
subsystem: ui
tags: [htmx, jinja2, fastapi, sqlalchemy, sqlalchemy-selectinload, telegram-bot]

# Dependency graph
requires:
  - phase: 02-expense-control
    plan: 01
    provides: "Expense model with status, approved_by, approved_at, rejection_comment columns; Trip and Driver relationships"
  - phase: 01-infrastructure-and-foundation
    provides: "FastAPI panel router, Jinja2 templates with base.html, async_session, get_current_user_from_cookie, ptb_app in main.py"
provides:
  - "GET /panel/expenses route listing PENDING expenses with eager-loaded driver relationship"
  - "POST /panel/expenses/{id}/approve route: sets APPROVED, records dispatcher username, notifies driver via Telegram"
  - "POST /panel/expenses/{id}/reject route: sets REJECTED with comment, notifies driver via Telegram"
  - "expenses.html full approval queue page (extends base.html)"
  - "expense_row.html <tr> fragment for HTMX outerHTML swap on approve/reject"
  - "HTMX 2.0.4 loaded in base.html for all panel pages"
  - "notify_driver_expense_decision() helper with deferred ptb_app import to avoid circular import"
affects:
  - 02-expense-control (bot submission flow depends on approval queue closing the loop)
  - dispatcher workflow (all expense reviews happen at this URL)

# Tech tracking
tech-stack:
  added:
    - "HTMX 2.0.4 (unpkg CDN) — inline row swapping without JavaScript"
  patterns:
    - "HTMX hx-post + hx-target='#expense-{id}' + hx-swap='outerHTML' for inline table row replacement"
    - "Deferred import (from src.main import ptb_app inside function body) to avoid circular imports between main.py and panel.py"
    - "selectinload(Expense.trip).selectinload(Trip.driver) chain for async eager loading of nested relationships"
    - "expense_row.html as a reusable <tr> fragment — returned by both GET (via include) and POST (direct TemplateResponse)"

key-files:
  created:
    - "src/web/templates/expenses.html"
    - "src/web/templates/expense_row.html"
  modified:
    - "src/web/templates/base.html"
    - "src/web/panel.py"

key-decisions:
  - "Deferred import of ptb_app inside notify_driver_expense_decision() body — avoids circular import since main.py imports panel.py; both modules are fully loaded by call time"
  - "expense_row.html rendered via both {% include %} in expenses.html and direct TemplateResponse in POST handlers — single source of truth for row HTML"
  - "HTMX loaded via unpkg CDN in base.html <head> — applies to all panel pages without per-page inclusion"

patterns-established:
  - "HTMX pattern: POST handler returns TemplateResponse with HTMLResponse class — HTMX swaps the <tr> fragment inline, no page reload"
  - "Approval flow: status written inside session context, session closed, then bot notification sent — notification failure does not roll back DB change"

requirements-completed:
  - EAPPR-01
  - EAPPR-02
  - EAPPR-03

# Metrics
duration: 2min
completed: 2026-03-09
---

# Phase 2 Plan 03: Dispatcher Approval Queue Summary

**HTMX-powered expense approval queue at /panel/expenses with inline approve/reject row swaps and immediate Telegram driver notifications using deferred ptb_app import**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-09T03:51:49Z
- **Completed:** 2026-03-09T03:54:06Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Built complete dispatcher expense approval queue at GET /panel/expenses showing all PENDING expenses with driver name, type, amount, currency, photo link, and date
- Implemented HTMX inline approve/reject: POST handlers return expense_row.html <tr> fragment that replaces the row without page reload
- Wired immediate Telegram bot notification to drivers on approve or reject (non-blocking try/except, deferred import avoids circular dependency)
- Added HTMX 2.0.4 to base.html making it available across all panel pages

## Task Commits

Each task was committed atomically:

1. **Task 1: Add HTMX to base.html and create expense queue templates** - `6be0d87` (feat)
2. **Task 2: Add approval queue routes to panel.py** - `f0d0fcd` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/web/templates/base.html` - Added HTMX 2.0.4 script tag in head; added /panel/expenses nav link
- `src/web/templates/expenses.html` - Full approval queue page extending base.html, table of PENDING expenses
- `src/web/templates/expense_row.html` - Single <tr> fragment with PENDING-conditional hx-post approve/reject forms
- `src/web/panel.py` - Added imports (datetime, Expense, Trip, selectinload), notify helper, and 3 new routes

## Decisions Made
- Deferred import `from src.main import ptb_app` inside `notify_driver_expense_decision()` function body — main.py imports panel.py at module level, so a top-level import in panel.py would be circular. Deferred imports resolve at call time when both modules are fully loaded.
- Bot notification failure is caught and logged but does NOT roll back the DB status change — DB write is authoritative, notification is best-effort.
- expense_row.html is used both as an `{% include %}` in expenses.html and as a direct TemplateResponse in POST handlers — single template, no duplication.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `python` command not available in shell (macOS default); used `python3` and `source venv/bin/activate` for verification. No code impact.

## User Setup Required

None - no external service configuration required. The HTMX CDN is loaded from unpkg.com; no API keys or env vars needed for the approval queue itself. Bot notifications use the existing TELEGRAM_BOT_TOKEN already configured.

## Next Phase Readiness
- Approval queue is operational — dispatchers can now review PENDING expenses at /panel/expenses and approve or reject inline
- Driver receives Telegram notification immediately after dispatcher action
- Phase 2 Plan 02 (bot expense submission flow) and Plan 04 (anomaly detection) can proceed independently — they use the same Expense model columns set up in Phase 2 Plan 01

---
*Phase: 02-expense-control*
*Completed: 2026-03-09*
