---
phase: 02-expense-control
plan: 05
type: execute
wave: 4
depends_on:
  - 02-02-PLAN.md
  - 02-03-PLAN.md
  - 02-04-PLAN.md
files_modified:
  - antigravity_modules/expense_flow.py
  - antigravity_modules/translations.py
  - src/bot/bot_app.py
autonomous: false
requirements:
  - EXP-06

must_haves:
  truths:
    - "Driver sends /my_expenses or taps the summary button and receives a message showing pending count/total, approved count/total, and trip grand total in KZT"
    - "Summary message shows per-status breakdown for the driver's currently active trip"
    - "If driver has no active trip, a clear 'no active trip' message is returned"
    - "Summary command is registered in the bot handlers so it responds to /my_expenses"
  artifacts:
    - path: "antigravity_modules/expense_flow.py"
      provides: "expense_summary_handler() command handler function"
      contains: "expense_summary_handler"
    - path: "antigravity_modules/translations.py"
      provides: "exp_summary_header and related string keys"
      contains: "exp_summary_header"
    - path: "src/bot/bot_app.py"
      provides: "/my_expenses CommandHandler registered"
      contains: "my_expenses"
  key_links:
    - from: "src/bot/bot_app.py register_handlers()"
      to: "expense_summary_handler in expense_flow.py"
      via: "CommandHandler('my_expenses', expense_summary_handler)"
      pattern: "my_expenses"
    - from: "expense_summary_handler()"
      to: "SQLAlchemy SUM(amount_kzt) GROUP BY status"
      via: "get_active_trip_for_driver() then group_by query on Expense.status"
      pattern: "amount_kzt"
---

<objective>
Add the /my_expenses bot command so drivers can view their expense summary (pending / approved / total) for the active trip. This is the final piece of Phase 2 — the driver-facing feedback loop after the approval queue is working.

Purpose: Drivers need visibility into which expenses are pending approval and what the approved total is for the trip. This closes the feedback loop without requiring the driver to contact the dispatcher.
Output: expense_summary_handler() function in expense_flow.py, registration in bot_app.py, translation strings.
</objective>

<execution_context>
@/Users/osmagulov/.claude/get-shit-done/workflows/execute-plan.md
@/Users/osmagulov/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-expense-control/02-RESEARCH.md
@antigravity_modules/expense_flow.py
@antigravity_modules/expense_crud.py
@antigravity_modules/translations.py
@src/bot/bot_app.py
@src/db/models.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add expense_summary_handler and register /my_expenses command</name>
  <files>antigravity_modules/expense_flow.py, antigravity_modules/translations.py, src/bot/bot_app.py</files>
  <action>
  Step A — Update antigravity_modules/translations.py:
  Read the file. Add new string keys following the existing pattern:
  ```python
  "exp_summary_header": {
      "ru": "Расходы по текущему рейсу:",
      "kk": "Ағымдағы рейс бойынша шығындар:"
  },
  "exp_summary_line": {
      "ru": "{status}: {count} поз. / {total:.0f} KZT",
      "kk": "{status}: {count} поз. / {total:.0f} KZT"
  },
  "exp_summary_total": {
      "ru": "ИТОГО одобрено: {total:.0f} KZT",
      "kk": "БАРЛЫҒЫ бекітілді: {total:.0f} KZT"
  },
  "exp_summary_empty": {
      "ru": "По этому рейсу расходов пока нет.",
      "kk": "Бұл рейс бойынша шығындар жоқ."
  },
  ```

  Step B — Update antigravity_modules/expense_flow.py:
  Read the file. Add the following function after `cancel_expense()` and before `get_expense_conversation_handler()`:

  ```python
  async def expense_summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
      """EXP-06: Show driver their expense summary for the active trip."""
      tg_id = update.effective_user.id

      async with async_session() as session:
          driver = await get_driver_by_tg_id(session, tg_id)
          if not driver:
              await update.message.reply_text(get_text("ru", "need_reg"))
              return
          lang = driver.language

          trip = await get_active_trip_for_driver(session, driver.id)
          if not trip:
              await update.message.reply_text(get_text(lang, "exp_no_trip"))
              return

          from sqlalchemy import func as sql_func
          from src.db.models import Expense as ExpenseModel
          result = await session.execute(
              select(
                  ExpenseModel.status,
                  sql_func.count().label("cnt"),
                  sql_func.sum(ExpenseModel.amount_kzt).label("total_kzt"),
              )
              .where(ExpenseModel.trip_id == trip.id)
              .group_by(ExpenseModel.status)
          )
          rows = result.all()

      if not rows:
          await update.message.reply_text(get_text(lang, "exp_summary_empty"))
          return

      STATUS_LABELS = {
          "PENDING": "Ожидают" if lang == "ru" else "Күтуде",
          "APPROVED": "Одобрены" if lang == "ru" else "Бекітілді",
          "REJECTED": "Отклонены" if lang == "ru" else "Қабылданбады",
      }

      lines = [get_text(lang, "exp_summary_header")]
      approved_total = 0.0
      for status, count, total_kzt in rows:
          label = STATUS_LABELS.get(status, status)
          total = total_kzt or 0.0
          lines.append(f"  {label}: {count} поз. / {total:.0f} KZT")
          if status == "APPROVED":
              approved_total = total

      lines.append("")
      lines.append(get_text(lang, "exp_summary_total", total=approved_total))

      await update.message.reply_text("\n".join(lines))
  ```

  NOTE: The `select` import already exists in expense_flow.py (it comes from sqlalchemy via crud imports). If not, add `from sqlalchemy import select` to the imports. Use the existing `get_driver_by_tg_id` and `get_active_trip_for_driver` functions already imported in expense_flow.py.

  Step C — Update src/bot/bot_app.py:
  Read the file. Find the `register_handlers()` function. Add the /my_expenses CommandHandler alongside existing expense handlers:
  ```python
  from antigravity_modules.expense_flow import get_expense_conversation_handler, expense_summary_handler

  # In register_handlers(), after adding get_expense_conversation_handler():
  app.add_handler(CommandHandler("my_expenses", expense_summary_handler))
  ```
  NOTE: Check the existing import line for expense_flow — it may already import from that module. If so, add `expense_summary_handler` to the existing import, do not create a duplicate import line.
  </action>
  <verify>
  Run: `python -m py_compile antigravity_modules/expense_flow.py` — no syntax errors

  Run: `python -c "from antigravity_modules.expense_flow import expense_summary_handler; print('handler ok')"` — no ImportError

  Run: `python -c "from antigravity_modules.translations import get_text; print(get_text('ru', 'exp_summary_header'))"` — prints the Russian summary header string

  Run: `python -m py_compile src/bot/bot_app.py` — no syntax errors

  Run: `python -c "import src.bot.bot_app; print('bot_app ok')"` — no ImportError
  </verify>
  <done>expense_summary_handler() exists in expense_flow.py: fetches active trip, runs GROUP BY status query on expenses, formats summary with per-status count and KZT total, sends to driver. Translations have exp_summary_header, exp_summary_empty, exp_summary_total keys. bot_app.py registers CommandHandler('my_expenses', expense_summary_handler) in register_handlers().</done>
</task>

<task type="checkpoint:human-verify">
  <what-built>
  Complete Phase 2: Expense Control implementation:
  - Plan 02-01: Schema migration (new Expense columns + FuelAnomaly table)
  - Plan 02-02: Bot expense flows (FUEL with odometer validation, PER_DIEM, FINE, OTHER) + FX rates + idempotency
  - Plan 02-03: HTMX approval queue (/panel/expenses) + bot notifications on approve/reject
  - Plan 02-04: Anomaly detection service + APScheduler hourly digest + /panel/anomalies feed
  - Plan 02-05 Task 1: /my_expenses bot command

  Railway will run `alembic upgrade head` as pre-deploy hook before the new code starts.
  </what-built>
  <how-to-verify>
  1. Deploy to Railway and confirm alembic migration runs without error (check Railway deploy logs for "Running upgrade ... -> phase2")

  2. Bot — FUEL expense flow:
     - Send /add_expense (or tap "ДОБАВИТЬ РАСХОД" button)
     - Select "Топливо" (FUEL)
     - Enter liters (e.g. "50")
     - Enter odometer — try a value LOWER than last reading to verify rejection message appears
     - Enter a valid odometer value
     - Enter station name (e.g. "Shell Алматы")
     - Enter amount (e.g. "15000")
     - Select currency "KZT"
     - Skip photo (/skip_photo)
     - Confirm expense is saved successfully

  3. Bot — PER_DIEM flow:
     - Send /add_expense, select "Суточные"
     - Enter amount, select currency, enter city
     - Confirm saved successfully

  4. Web panel — expense approval queue:
     - Navigate to https://freight-tms-api-production.up.railway.app/panel/expenses
     - Confirm the FUEL and PER_DIEM expenses from step 2-3 appear in the queue
     - Click "Одобрить" on the FUEL expense — row should update inline to show "APPROVED" without page reload
     - Check Telegram — driver should receive a "Расход одобрен" message

  5. Web panel — anomaly feed:
     - Navigate to /panel/anomalies
     - Page loads without error (may be empty if no anomalies yet)
     - If an anomaly exists, click "Ложная тревога" — row updates inline

  6. Bot — expense summary:
     - Send /my_expenses
     - Message shows breakdown by status (Ожидают / Одобрены) with KZT totals

  7. Duplicate prevention:
     - Send the same expense amount within 1 minute — second submission should show "Такой расход уже зафиксирован" message
  </how-to-verify>
  <resume-signal>Type "approved" if all flows work as expected, or describe any issues found</resume-signal>
</task>

</tasks>

<verification>
1. `python -m py_compile antigravity_modules/expense_flow.py` — no errors
2. `python -c "from antigravity_modules.expense_flow import expense_summary_handler"` — no ImportError
3. `python -m py_compile src/bot/bot_app.py` — no errors
4. `grep "my_expenses" src/bot/bot_app.py` — CommandHandler registered
5. Full Phase 2 smoke test on Railway (see checkpoint task above)
</verification>

<success_criteria>
- /my_expenses command works: shows pending/approved/rejected counts and KZT totals for active trip
- Message is clear when no active trip exists
- All Phase 2 requirement flows verified on Railway:
  - FUEL: liters + odometer validation + station + FX rate stored
  - PER_DIEM: amount + currency + city
  - FINE and OTHER: amount + currency + optional photo + comment
  - Duplicate within 1 minute: rejected with clear message
  - Approval queue: HTMX inline with bot notification
  - Anomaly feed: loads without error, dismiss button works
  - Director digest: registered hourly in APScheduler
</success_criteria>

<output>
After completion, create `.planning/phases/02-expense-control/02-05-SUMMARY.md`
</output>
