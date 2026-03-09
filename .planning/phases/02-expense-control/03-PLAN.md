---
phase: 02-expense-control
plan: 03
type: execute
wave: 2
depends_on:
  - 02-01-PLAN.md
files_modified:
  - src/web/panel.py
  - src/web/templates/base.html
  - src/web/templates/expenses.html
  - src/web/templates/expense_row.html
autonomous: true
requirements:
  - EAPPR-01
  - EAPPR-02
  - EAPPR-03

must_haves:
  truths:
    - "Dispatcher navigates to /panel/expenses and sees a table of PENDING expenses with driver name, type, amount, currency, and receipt photo link"
    - "Dispatcher clicks Approve — the row updates inline to show APPROVED status without page reload"
    - "Dispatcher clicks Reject with optional comment — the row updates inline to show REJECTED status and comment without page reload"
    - "After approve or reject, a bot message is sent to the driver's Telegram chat immediately"
    - "HTMX script is loaded in base.html so approve/reject buttons work without additional JS"
  artifacts:
    - path: "src/web/templates/expenses.html"
      provides: "Full approval queue page with table of pending expenses"
      contains: "expense-"
    - path: "src/web/templates/expense_row.html"
      provides: "Single <tr> fragment returned by HTMX approve/reject endpoints"
      contains: "hx-post"
    - path: "src/web/panel.py"
      provides: "GET /panel/expenses, POST /panel/expenses/{id}/approve, POST /panel/expenses/{id}/reject routes"
      contains: "approve_expense"
    - path: "src/web/templates/base.html"
      provides: "HTMX script tag in <head>"
      contains: "htmx.org"
  key_links:
    - from: "expense_row.html hx-post buttons"
      to: "POST /panel/expenses/{id}/approve and /reject"
      via: "HTMX hx-post attribute with hx-target='#expense-{id}' and hx-swap='outerHTML'"
      pattern: "hx-post.*expenses"
    - from: "panel.py approve_expense()"
      to: "driver Telegram notification"
      via: "ptb_app.bot.send_message() using ptb_app from src.main (no circular import — same process)"
      pattern: "send_message"
---

<objective>
Build the dispatcher approval queue: a web page at /panel/expenses listing PENDING expenses, with HTMX inline approve/reject that swaps the table row and immediately notifies the driver via Telegram bot.

Purpose: Dispatchers need to review and act on driver expense submissions without leaving the web panel or reloading the page. Bot notification closes the feedback loop to the driver immediately.
Output: GET /panel/expenses route, two POST approve/reject routes, expenses.html page, expense_row.html fragment template, HTMX added to base.html.
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
@src/web/panel.py
@src/web/templates/base.html
@src/db/models.py
@src/main.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add HTMX to base.html and create expense queue templates</name>
  <files>src/web/templates/base.html, src/web/templates/expenses.html, src/web/templates/expense_row.html</files>
  <action>
  Step A — Update src/web/templates/base.html:
  Read the file. Add the HTMX script tag inside the `<head>` section, after any existing script/link tags:
  ```html
  <script src="https://unpkg.com/htmx.org@2.0.4" integrity="sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+" crossorigin="anonymous"></script>
  ```
  Also add a navigation link to the expenses queue in the nav bar (look for the existing nav links to /panel/drivers and add alongside them):
  ```html
  <a href="/panel/expenses">Расходы</a>
  ```

  Step B — Create src/web/templates/expenses.html (new file):
  This is the full approval queue page. Follow the same base template pattern used in drivers.html. The page extends base.html (or includes the same header/footer pattern as existing templates — check drivers.html first):
  ```html
  {% extends "base.html" %}
  {% block title %}Очередь расходов{% endblock %}
  {% block content %}
  <h1>Расходы на одобрение</h1>
  {% if not expenses %}
  <p>Нет расходов, ожидающих одобрения.</p>
  {% else %}
  <table>
    <thead>
      <tr>
        <th>Водитель</th>
        <th>Тип</th>
        <th>Сумма</th>
        <th>Фото</th>
        <th>Дата</th>
        <th>Действие</th>
      </tr>
    </thead>
    <tbody>
      {% for expense in expenses %}
        {% include "expense_row.html" %}
      {% endfor %}
    </tbody>
  </table>
  {% endif %}
  {% endblock %}
  ```
  NOTE: Check how drivers.html is structured first. If it does NOT use `{% extends %}` and instead is a standalone HTML file, follow the same pattern (standalone with full HTML structure, not extends). Match the existing template pattern exactly.

  Step C — Create src/web/templates/expense_row.html (new file):
  This is the `<tr>` fragment returned by HTMX approve/reject endpoints. Critical: the file renders ONLY the `<tr>` tag (no surrounding table/html/body):
  ```html
  <tr id="expense-{{ expense.id }}">
    <td>{{ expense.trip.driver.name if expense.trip and expense.trip.driver else "—" }}</td>
    <td>{{ expense.expense_type }}</td>
    <td>{{ expense.amount }} {{ expense.currency }}
        {% if expense.amount_kzt and expense.currency != 'KZT' %}
        <small>({{ expense.amount_kzt | int }} KZT)</small>
        {% endif %}
    </td>
    <td>
      {% if expense.photo_r2_url %}
      <a href="{{ expense.photo_r2_url }}" target="_blank">Фото</a>
      {% else %}нет{% endif %}
    </td>
    <td>{{ expense.created_at.strftime('%d.%m %H:%M') if expense.created_at else "—" }}</td>
    <td>
      {% if expense.status == "PENDING" %}
      <form hx-post="/panel/expenses/{{ expense.id }}/approve"
            hx-target="#expense-{{ expense.id }}"
            hx-swap="outerHTML"
            style="display:inline">
        <button type="submit">Одобрить</button>
      </form>
      <form hx-post="/panel/expenses/{{ expense.id }}/reject"
            hx-target="#expense-{{ expense.id }}"
            hx-swap="outerHTML"
            style="display:inline">
        <input name="comment" placeholder="Причина (необяз.)" style="width:120px">
        <button type="submit">Отклонить</button>
      </form>
      {% else %}
      <span>{{ expense.status }}</span>
      {% if expense.rejection_comment %}<small> — {{ expense.rejection_comment }}</small>{% endif %}
      {% endif %}
    </td>
  </tr>
  ```
  </action>
  <verify>
  Run: `python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('src/web/templates')); t = env.get_template('expense_row.html'); print('template ok')"` — should print "template ok"
  Run: `grep "htmx.org" src/web/templates/base.html` — should show the HTMX script tag line
  </verify>
  <done>base.html has HTMX 2.0.4 script tag in head and /panel/expenses nav link. expenses.html exists as full page template. expense_row.html exists rendering only a `<tr id="expense-{id}">` with PENDING-conditional approve/reject forms using hx-post + hx-target + hx-swap="outerHTML".</done>
</task>

<task type="auto">
  <name>Task 2: Add approval queue routes to panel.py</name>
  <files>src/web/panel.py</files>
  <action>
  Read src/web/panel.py first. Add the following to the file:

  1. Add new imports at the top (after existing imports):
     ```python
     from datetime import datetime
     from src.db.models import Expense, Trip, Driver
     ```

  2. Add a helper function for sending bot notifications (add after the imports, before the router):
     ```python
     async def notify_driver_expense_decision(expense: Expense, approved: bool, rejection_comment: str = None) -> None:
         """Send Telegram message to driver about expense approval or rejection."""
         from src.main import ptb_app  # deferred import — ptb_app is set at lifespan startup
         if ptb_app is None:
             return
         try:
             driver_tg_id = expense.trip.driver.tg_id
             if approved:
                 text = f"Расход одобрен: {expense.expense_type} {expense.amount} {expense.currency}"
             else:
                 text = f"Расход отклонен: {expense.expense_type} {expense.amount} {expense.currency}"
                 if rejection_comment:
                     text += f"\nПричина: {rejection_comment}"
             await ptb_app.bot.send_message(chat_id=driver_tg_id, text=text)
         except Exception as e:
             logger.error(f"Failed to notify driver: {e}")
     ```
     NOTE: Using a deferred import `from src.main import ptb_app` inside the function body avoids the circular import — Python resolves module-level circular imports at import time, but deferred imports inside function bodies are resolved at call time when both modules are fully loaded. This is simpler than creating a separate state.py for now.

  3. Add three new route handlers at the end of the file:

     ```python
     @router.get("/expenses", response_class=HTMLResponse)
     async def list_expenses(
         request: Request,
         current_user: dict = Depends(get_current_user_from_cookie),
     ):
         async with async_session() as session:
             result = await session.execute(
                 select(Expense)
                 .join(Trip, Expense.trip_id == Trip.id)
                 .join(Driver, Trip.driver_id == Driver.id)
                 .where(Expense.status == "PENDING")
                 .order_by(Expense.created_at.desc())
                 .options(
                     selectinload(Expense.trip).selectinload(Trip.driver)
                 )
             )
             expenses = result.scalars().all()
         return templates.TemplateResponse(
             "expenses.html",
             {"request": request, "expenses": expenses, "user": current_user},
         )


     @router.post("/expenses/{expense_id}/approve", response_class=HTMLResponse)
     async def approve_expense(
         request: Request,
         expense_id: int,
         current_user: dict = Depends(get_current_user_from_cookie),
     ):
         async with async_session() as session:
             result = await session.execute(
                 select(Expense)
                 .where(Expense.id == expense_id)
                 .options(selectinload(Expense.trip).selectinload(Trip.driver))
             )
             expense = result.scalars().first()
             if expense:
                 expense.status = "APPROVED"
                 expense.approved_by = current_user.get("sub", "dispatcher")
                 expense.approved_at = datetime.utcnow()
                 session.add(expense)
                 await session.commit()
                 await session.refresh(expense)
         await notify_driver_expense_decision(expense, approved=True)
         return templates.TemplateResponse(
             "expense_row.html",
             {"request": request, "expense": expense},
         )


     @router.post("/expenses/{expense_id}/reject", response_class=HTMLResponse)
     async def reject_expense(
         request: Request,
         expense_id: int,
         comment: str = Form(default=""),
         current_user: dict = Depends(get_current_user_from_cookie),
     ):
         async with async_session() as session:
             result = await session.execute(
                 select(Expense)
                 .where(Expense.id == expense_id)
                 .options(selectinload(Expense.trip).selectinload(Trip.driver))
             )
             expense = result.scalars().first()
             if expense:
                 expense.status = "REJECTED"
                 expense.rejection_comment = comment or None
                 expense.approved_by = current_user.get("sub", "dispatcher")
                 expense.approved_at = datetime.utcnow()
                 session.add(expense)
                 await session.commit()
                 await session.refresh(expense)
         await notify_driver_expense_decision(expense, approved=False, rejection_comment=comment)
         return templates.TemplateResponse(
             "expense_row.html",
             {"request": request, "expense": expense},
         )
     ```

  4. Add selectinload to imports (SQLAlchemy eager loading for relationships in async context):
     ```python
     from sqlalchemy.orm import selectinload
     ```

  NOTE on HTMX + FastAPI: HTMX sends hx-post as a form POST. FastAPI reads the `comment` field via `Form(default="")`. The response must be `HTMLResponse` (TemplateResponse is a subclass), NOT JSON. The template response renders only the `<tr>` fragment which HTMX swaps into the table.
  </action>
  <verify>
  Run: `python -m py_compile src/web/panel.py` — no syntax errors

  Run: `python -c "from src.web.panel import router; routes = [r.path for r in router.routes]; print('/panel/expenses' in routes or any('/expenses' in r for r in routes))"` — should print True

  Run: `python -c "import uvicorn; from src.main import app; print([r.path for r in app.routes])"` or
  Run: `python -c "from src.web.panel import router; print([r.path for r in router.routes])"` — should list /panel/expenses, /panel/expenses/{expense_id}/approve, /panel/expenses/{expense_id}/reject
  </verify>
  <done>panel.py has GET /panel/expenses returning expenses.html with PENDING expenses. POST /panel/expenses/{id}/approve sets status=APPROVED, stores approved_by and approved_at, sends bot notification, returns expense_row.html fragment. POST /panel/expenses/{id}/reject sets status=REJECTED, stores rejection_comment, sends bot notification, returns expense_row.html fragment. Both POST routes use selectinload to eager-load trip.driver for notification. No circular import (deferred import inside function body).</done>
</task>

</tasks>

<verification>
1. `python -m py_compile src/web/panel.py` — no errors
2. `grep "htmx.org" src/web/templates/base.html` — HTMX script tag present
3. `grep "hx-post" src/web/templates/expense_row.html` — HTMX attributes present
4. `python -c "from src.web.panel import approve_expense, reject_expense, list_expenses; print('routes ok')"` — no ImportError
5. `grep "selectinload" src/web/panel.py` — eager loading in place
</verification>

<success_criteria>
- GET /panel/expenses shows table of PENDING expenses with driver, type, amount, photo link columns; requires auth
- POST /panel/expenses/{id}/approve: updates status to APPROVED, records dispatcher username from JWT, sends driver Telegram notification, returns expense_row.html <tr> fragment
- POST /panel/expenses/{id}/reject: updates status to REJECTED with rejection_comment, sends driver Telegram notification, returns expense_row.html <tr> fragment
- HTMX 2.0.4 loaded in base.html; approve/reject forms use hx-post + hx-target="#expense-{id}" + hx-swap="outerHTML"
- No page reload on approve/reject — row swaps inline
- Bot notification sent immediately after approve/reject (non-blocking try/except)
</success_criteria>

<output>
After completion, create `.planning/phases/02-expense-control/02-03-SUMMARY.md`
</output>
