---
phase: 02-expense-control
plan: 05
subsystem: bot
tags: [python-telegram-bot, command-handler, expense-summary, sqlalchemy-aggregate]

# Dependency graph
requires:
  - phase: 02-expense-control
    plan: 02
    provides: "create_expense(), get_active_trip_for_driver(), Expense model with amount_kzt and status columns"
  - phase: 02-expense-control
    plan: 03
    provides: "Expense.status field transitions (PENDING -> APPROVED/REJECTED)"
provides:
  - "expense_summary_handler() command handler in antigravity_modules/expense_flow.py"
  - "/my_expenses CommandHandler registered in src/bot/bot_app.py"
  - "exp_summary_header, exp_summary_line, exp_summary_total, exp_summary_empty translation keys in both ru and kk"
affects:
  - "Driver-facing feedback loop: drivers can now view their pending/approved totals without contacting dispatcher"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLAlchemy async GROUP BY aggregate query with func.count() and func.sum() inside async_session context manager"
    - "Local imports inside async handler function (sqlalchemy func + Expense model) to avoid top-level circular dependency risk"

key-files:
  created: []
  modified:
    - "antigravity_modules/expense_flow.py"
    - "antigravity_modules/translations.py"
    - "src/bot/bot_app.py"

key-decisions:
  - "Local imports (sqlalchemy func, Expense model) kept inside expense_summary_handler() body following the existing pattern in process_final_expense() — avoids any top-level import ordering issues"
  - "STATUS_LABELS dict defined inline in handler rather than in translations to keep label logic co-located with the formatting logic"

patterns-established:
  - "expense_summary_handler() follows get_driver -> check_trip -> query pattern matching all other expense_flow.py handlers"

requirements-completed:
  - EXP-06

# Metrics
duration: 9min
completed: 2026-03-09
---

# Phase 2 Plan 05: Expense Summary Command Summary

**EXP-06 /my_expenses bot command: driver expense summary by status (PENDING/APPROVED/REJECTED) with KZT totals for the active trip via SQLAlchemy GROUP BY aggregate query**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-03-09T08:49:58Z
- **Completed:** 2026-03-09T08:58:18Z (Task 1 complete; checkpoint:human-verify pending)
- **Tasks:** 1 of 2 (Task 2 is checkpoint:human-verify — awaiting human sign-off)
- **Files modified:** 3

## Accomplishments

- Added 4 new translation keys in both `ru` and `kk` dicts in translations.py: `exp_summary_header`, `exp_summary_line`, `exp_summary_total`, `exp_summary_empty`
- Added `expense_summary_handler()` to expense_flow.py: looks up driver, checks for active trip, runs `SELECT status, COUNT(*), SUM(amount_kzt) GROUP BY status` on Expense table, formats per-status breakdown with APPROVED grand total
- Registered `CommandHandler("my_expenses", expense_summary_handler)` in `register_handlers()` in bot_app.py
- Updated `bot_app.py` import to include `expense_summary_handler` alongside existing expense_flow imports

## Task Commits

1. **Task 1: Add expense_summary_handler and register /my_expenses command** - `8428d71` (feat)

## Files Created/Modified

- `antigravity_modules/translations.py` - Added 4 EXP-06 summary keys in both ru and kk dicts
- `antigravity_modules/expense_flow.py` - Added expense_summary_handler() after cancel_expense()
- `src/bot/bot_app.py` - Updated import, added CommandHandler("my_expenses", expense_summary_handler)

## Decisions Made

- Local imports for `sqlalchemy.func` and `src.db.models.Expense` kept inside `expense_summary_handler()` body, consistent with existing pattern in `process_final_expense()` and `process_final_expense_direct()` in expense_flow.py.
- STATUS_LABELS dict defined inline in the handler (not in translations) to keep the status-to-label mapping close to the formatting code that uses it.

## Deviations from Plan

None - plan executed exactly as written.

## Checkpoint Status

Task 2 is `checkpoint:human-verify` requiring full Phase 2 smoke test on Railway:
- FUEL expense flow with odometer validation
- PER_DIEM flow
- Web panel approval queue (/panel/expenses) with HTMX inline approval + bot notification
- Anomaly feed (/panel/anomalies) with dismiss button
- /my_expenses summary command
- Duplicate prevention within 1 minute

Resume signal: user types "approved" after verifying all flows.

## Self-Check: PASSED

- antigravity_modules/expense_flow.py: FOUND
- antigravity_modules/translations.py: FOUND
- src/bot/bot_app.py: FOUND
- Commit 8428d71 (Task 1): FOUND
- `python -m py_compile antigravity_modules/expense_flow.py`: PASSED
- `python -c "from antigravity_modules.expense_flow import expense_summary_handler"`: PASSED
- `python -c "from antigravity_modules.translations import get_text; print(get_text('ru', 'exp_summary_header'))"`: PASSED (prints "Расходы по текущему рейсу:")
- `python -m py_compile src/bot/bot_app.py`: PASSED
- `grep "my_expenses" src/bot/bot_app.py`: FOUND

---
*Phase: 02-expense-control*
*Completed: 2026-03-09*
