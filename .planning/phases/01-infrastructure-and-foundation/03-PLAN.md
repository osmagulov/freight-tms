---
phase: 01-infrastructure-and-foundation
plan: 03
type: execute
wave: 2
depends_on:
  - "01-01"
files_modified:
  - antigravity_modules/trip_opening.py
  - antigravity_modules/expense_flow.py
  - antigravity_modules/location_flow.py
  - antigravity_modules/trip_closing.py
autonomous: true
requirements:
  - INFRA-04

must_haves:
  truths:
    - "All 5 ConversationHandlers have both name= and persistent=True"
    - "PTB will persist conversation state across restarts (no silent skip of unnamed handlers)"
    - "Bot conversation state survives a Railway redeploy when Volume is mounted"
  artifacts:
    - path: "antigravity_modules/trip_opening.py"
      provides: "get_trip_conversation_handler() with persistent=True"
      contains: "persistent=True"
    - path: "antigravity_modules/expense_flow.py"
      provides: "get_expense_conversation_handler() with persistent=True"
      contains: "persistent=True"
    - path: "antigravity_modules/location_flow.py"
      provides: "get_location_conversation_handler() with persistent=True"
      contains: "persistent=True"
    - path: "antigravity_modules/trip_closing.py"
      provides: "get_trip_closing_conversation_handler() with persistent=True"
      contains: "persistent=True"
  key_links:
    - from: "PicklePersistence (src/main.py)"
      to: "ConversationHandlers (all 5)"
      via: "name= key used by PTB to store/restore state in pickle file"
      pattern: "name=.*persistent=True"
---

<objective>
Add `persistent=True` to all four remaining ConversationHandlers in the antigravity_modules. The registration handler already received this in Plan 02. This plan completes FSM persistence across all bot flows.

Purpose: PTB silently skips persistence for any ConversationHandler missing `persistent=True`. All 5 handlers need both `name=` (already present) AND `persistent=True` (currently missing in 4 handlers) for Railway redeploy to not lose driver conversations.
Output: Four updated antigravity module files, each with persistent=True added to their ConversationHandler factory functions.
</objective>

<execution_context>
@/Users/osmagulov/.claude/get-shit-done/workflows/execute-plan.md
@/Users/osmagulov/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/01-infrastructure-and-foundation/01-RESEARCH.md
@antigravity_modules/trip_opening.py
@antigravity_modules/expense_flow.py
@antigravity_modules/location_flow.py
@antigravity_modules/trip_closing.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add persistent=True to trip_opening and expense_flow ConversationHandlers</name>
  <files>antigravity_modules/trip_opening.py, antigravity_modules/expense_flow.py</files>
  <action>
  In antigravity_modules/trip_opening.py, find the `get_trip_conversation_handler()` function. Locate the `ConversationHandler(...)` call. It already has `name="trip_opening"`. Add `persistent=True` as a keyword argument after `name="trip_opening"`:

  Before:
  ```python
  return ConversationHandler(
      entry_points=[...],
      states={...},
      fallbacks=[CommandHandler("cancel", cancel_trip)],
      name="trip_opening"
  )
  ```

  After:
  ```python
  return ConversationHandler(
      entry_points=[...],
      states={...},
      fallbacks=[CommandHandler("cancel", cancel_trip)],
      name="trip_opening",
      persistent=True,
  )
  ```

  In antigravity_modules/expense_flow.py, find the `get_expense_conversation_handler()` function. It already has `name="expense_flow"`. Add `persistent=True` after `name="expense_flow"`:

  Before:
  ```python
  return ConversationHandler(
      ...
      fallbacks=[CommandHandler("cancel", cancel_expense)],
      name="expense_flow"
  )
  ```

  After:
  ```python
  return ConversationHandler(
      ...
      fallbacks=[CommandHandler("cancel", cancel_expense)],
      name="expense_flow",
      persistent=True,
  )
  ```

  Make NO other changes to these files. Only add `persistent=True,` to the ConversationHandler constructor call.
  </action>
  <verify>
  Run: `grep -n "persistent=True" antigravity_modules/trip_opening.py` — must match.
  Run: `grep -n "persistent=True" antigravity_modules/expense_flow.py` — must match.
  Run: `python -c "from antigravity_modules.trip_opening import get_trip_conversation_handler; h = get_trip_conversation_handler(); print(h.name, h.persistent)"` — should print: trip_opening True
  Run: `python -c "from antigravity_modules.expense_flow import get_expense_conversation_handler; h = get_expense_conversation_handler(); print(h.name, h.persistent)"` — should print: expense_flow True
  </verify>
  <done>trip_opening.py ConversationHandler has persistent=True. expense_flow.py ConversationHandler has persistent=True. Both still import and instantiate without errors.</done>
</task>

<task type="auto">
  <name>Task 2: Add persistent=True to location_flow and trip_closing ConversationHandlers</name>
  <files>antigravity_modules/location_flow.py, antigravity_modules/trip_closing.py</files>
  <action>
  In antigravity_modules/location_flow.py, find the `get_location_conversation_handler()` function. It already has `name="location_flow"`. Add `persistent=True` after `name="location_flow"`:

  Before:
  ```python
  return ConversationHandler(
      entry_points=[...],
      states={...},
      fallbacks=[CommandHandler("cancel", cancel_location)],
      name="location_flow"
  )
  ```

  After:
  ```python
  return ConversationHandler(
      entry_points=[...],
      states={...},
      fallbacks=[CommandHandler("cancel", cancel_location)],
      name="location_flow",
      persistent=True,
  )
  ```

  In antigravity_modules/trip_closing.py, find the `get_trip_closing_conversation_handler()` function. It already has `name="trip_closing"`. Add `persistent=True` after `name="trip_closing"`:

  Before:
  ```python
  return ConversationHandler(
      entry_points=[...],
      states={...},
      fallbacks=[CommandHandler("cancel", cancel_close_trip)],
      name="trip_closing"
  )
  ```

  After:
  ```python
  return ConversationHandler(
      entry_points=[...],
      states={...},
      fallbacks=[CommandHandler("cancel", cancel_close_trip)],
      name="trip_closing",
      persistent=True,
  )
  ```

  Make NO other changes to these files.
  </action>
  <verify>
  Run: `grep -n "persistent=True" antigravity_modules/location_flow.py` — must match.
  Run: `grep -n "persistent=True" antigravity_modules/trip_closing.py` — must match.
  Run: `python -c "from antigravity_modules.location_flow import get_location_conversation_handler; h = get_location_conversation_handler(); print(h.name, h.persistent)"` — should print: location_flow True
  Run: `python -c "from antigravity_modules.trip_closing import get_trip_closing_conversation_handler; h = get_trip_closing_conversation_handler(); print(h.name, h.persistent)"` — should print: trip_closing True
  </verify>
  <done>location_flow.py ConversationHandler has persistent=True. trip_closing.py ConversationHandler has persistent=True. Both still import without errors.</done>
</task>

</tasks>

<verification>
Run this single verification to confirm all 5 handlers are properly configured:
```bash
python -c "
from antigravity_modules.trip_opening import get_trip_conversation_handler
from antigravity_modules.expense_flow import get_expense_conversation_handler
from antigravity_modules.location_flow import get_location_conversation_handler
from antigravity_modules.trip_closing import get_trip_closing_conversation_handler

handlers = [
    get_trip_conversation_handler(),
    get_expense_conversation_handler(),
    get_location_conversation_handler(),
    get_trip_closing_conversation_handler(),
]
for h in handlers:
    assert h.persistent == True, f'{h.name} missing persistent=True'
    print(f'{h.name}: name=OK, persistent=True OK')
print('All 4 handlers verified.')
"
```
Expected output: 4 lines each confirming name + persistent=True, then "All 4 handlers verified."

Also verify registration handler from Plan 02:
```bash
grep "persistent=True" src/bot/bot_app.py
```
Should match.
</verification>

<success_criteria>
- All 4 antigravity module ConversationHandlers have persistent=True in their factory functions
- Combined with Plan 02's registration handler, all 5 ConversationHandlers in the project are persistence-enabled
- PTB will key persistence storage by handler name (already set: trip_opening, expense_flow, location_flow, trip_closing)
- No other code changes made to the antigravity modules
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-and-foundation/01-03-SUMMARY.md`
</output>
