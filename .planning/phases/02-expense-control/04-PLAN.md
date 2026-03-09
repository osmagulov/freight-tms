---
phase: 02-expense-control
plan: 04
type: execute
wave: 3
depends_on:
  - 02-01-PLAN.md
  - 02-02-PLAN.md
files_modified:
  - src/services/anomaly.py
  - src/web/panel.py
  - src/web/templates/anomalies.html
  - src/main.py
autonomous: true
requirements:
  - ALERT-01
  - ALERT-02
  - ALERT-03
  - ALERT-04
  - FLEET-03

must_haves:
  truths:
    - "After a FUEL expense is saved, actual consumption (liters/km * 100) is computed and compared to vehicle norm"
    - "If consumption exceeds norm by more than 20% AND vehicle has at least 2 prior fill-ups, a FuelAnomaly record is created"
    - "FuelAnomaly records with notified=False and is_false_alarm=False are batched and sent to DIRECTOR_TG_ID as one Telegram message hourly"
    - "Dispatcher sees /panel/anomalies listing active anomalies with vehicle, excess percentage, and a 'false alarm' button"
    - "Clicking 'false alarm' sets is_false_alarm=True on the anomaly inline via HTMX, removing it from the active list"
    - "APScheduler AsyncIOScheduler starts alongside PTB in FastAPI lifespan with the hourly anomaly digest job"
  artifacts:
    - path: "src/services/anomaly.py"
      provides: "check_fuel_anomaly_after_expense() and run_anomaly_digest() functions"
      contains: "run_anomaly_digest"
    - path: "src/web/templates/anomalies.html"
      provides: "Anomaly feed page with false alarm button"
      contains: "is_false_alarm"
    - path: "src/main.py"
      provides: "APScheduler AsyncIOScheduler started in lifespan alongside PTB"
      contains: "AsyncIOScheduler"
  key_links:
    - from: "antigravity_modules/expense_flow.py process_final_expense()"
      to: "src/services/anomaly.check_fuel_anomaly_after_expense()"
      via: "called after create_expense() returns committed expense (FUEL type only)"
      pattern: "check_fuel_anomaly_after_expense"
    - from: "src/main.py lifespan"
      to: "src/services/anomaly.run_anomaly_digest"
      via: "scheduler.add_job(run_anomaly_digest, 'interval', hours=1)"
      pattern: "run_anomaly_digest"
    - from: "src/services/anomaly.run_anomaly_digest()"
      to: "DIRECTOR_TG_ID Telegram chat"
      via: "ptb_app.bot.send_message() with ptb_app from src.main"
      pattern: "DIRECTOR_TG_ID"
---

<objective>
Build the anomaly detection service (compute fuel consumption, create FuelAnomaly records), wire it into the expense flow, set up APScheduler for hourly director digest, and add the dispatcher anomaly feed page with HTMX false-alarm dismissal.

Purpose: The director needs automated alerting when fuel consumption spikes beyond 20% of norm (after sufficient history). The dispatcher needs to see and dismiss false alarms without cluttering the director's view.
Output: src/services/anomaly.py, APScheduler in lifespan, anomalies.html template, /panel/anomalies route and /dismiss endpoint, anomaly check wired into FUEL expense save.
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
@src/services/anomaly.py
@src/main.py
@src/db/models.py
@src/web/panel.py
@antigravity_modules/expense_flow.py
@antigravity_modules/expense_crud.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create anomaly service and wire APScheduler into lifespan</name>
  <files>src/services/anomaly.py, src/main.py, antigravity_modules/expense_flow.py</files>
  <action>
  Step A — Create src/services/anomaly.py (new file):
  ```python
  import logging
  from datetime import datetime
  from sqlalchemy import select, func as sql_func
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.db.database import async_session
  from src.db.models import Expense, FuelAnomaly, Vehicle, Trip, ExpenseType

  logger = logging.getLogger(__name__)


  async def get_last_fuel_odometer_before(
      session: AsyncSession, vehicle_id: int, before_dt: datetime
  ) -> int | None:
      """Return the odometer of the FUEL expense immediately before before_dt for this vehicle."""
      result = await session.execute(
          select(Expense)
          .join(Trip, Expense.trip_id == Trip.id)
          .where(Trip.vehicle_id == vehicle_id)
          .where(Expense.expense_type == ExpenseType.FUEL.value)
          .where(Expense.odometer_reading.isnot(None))
          .where(Expense.created_at < before_dt)
          .order_by(Expense.created_at.desc())
          .limit(1)
      )
      expense = result.scalars().first()
      return expense.odometer_reading if expense else None


  async def count_fuel_expenses_for_vehicle(
      session: AsyncSession, vehicle_id: int, exclude_expense_id: int = None
  ) -> int:
      """Count FUEL expenses with odometer for a vehicle (used for minimum 2 fill-ups check)."""
      q = (
          select(sql_func.count())
          .select_from(Expense)
          .join(Trip, Expense.trip_id == Trip.id)
          .where(Trip.vehicle_id == vehicle_id)
          .where(Expense.expense_type == ExpenseType.FUEL.value)
          .where(Expense.odometer_reading.isnot(None))
      )
      if exclude_expense_id is not None:
          q = q.where(Expense.id != exclude_expense_id)
      result = await session.execute(q)
      return result.scalar() or 0


  async def check_fuel_anomaly_after_expense(
      session: AsyncSession,
      expense: Expense,
      vehicle: Vehicle,
  ) -> FuelAnomaly | None:
      """
      Called after a FUEL expense is committed. Calculates actual consumption and
      creates a FuelAnomaly record if consumption exceeds norm by > 20%.
      Returns the FuelAnomaly if one was created, else None.

      Requirements:
      - ALERT-01: compute liters / km * 100
      - ALERT-02: threshold = norm * 1.20 (20% over norm)
      - ALERT-03: minimum 2 prior fill-ups required
      """
      if expense.expense_type != ExpenseType.FUEL.value:
          return None
      if vehicle.fuel_norm_per_100km is None:
          return None  # No norm configured for this vehicle
      if expense.liters is None or expense.odometer_reading is None:
          return None  # Missing data for calculation

      # ALERT-03: require at least 2 prior fill-ups
      prior_count = await count_fuel_expenses_for_vehicle(
          session, vehicle.id, exclude_expense_id=expense.id
      )
      if prior_count < 2:
          return None

      # ALERT-01: get previous odometer to compute km driven
      prev_odo = await get_last_fuel_odometer_before(session, vehicle.id, expense.created_at)
      if prev_odo is None:
          return None
      km_driven = expense.odometer_reading - prev_odo
      if km_driven <= 0:
          return None

      actual_per_100km = (expense.liters / km_driven) * 100

      # ALERT-02: check against threshold (norm + 20%)
      threshold = vehicle.fuel_norm_per_100km * 1.20
      if actual_per_100km <= threshold:
          return None

      excess_percent = (
          (actual_per_100km - vehicle.fuel_norm_per_100km) / vehicle.fuel_norm_per_100km
      ) * 100

      anomaly = FuelAnomaly(
          expense_id=expense.id,
          vehicle_id=vehicle.id,
          trip_id=expense.trip_id,
          actual_per_100km=actual_per_100km,
          norm_per_100km=vehicle.fuel_norm_per_100km,
          threshold_per_100km=threshold,
          excess_percent=excess_percent,
          is_false_alarm=False,
          notified=False,
      )
      session.add(anomaly)
      await session.commit()
      logger.info(
          f"Fuel anomaly created: vehicle {vehicle.id}, {actual_per_100km:.1f} l/100km "
          f"vs norm {vehicle.fuel_norm_per_100km:.1f} (+{excess_percent:.0f}%)"
      )
      return anomaly


  async def run_anomaly_digest() -> None:
      """
      ALERT-04: Hourly APScheduler job — batch sends unnotified FuelAnomaly records
      to the director's Telegram chat. Marks them notified after successful send.
      """
      from src.main import ptb_app  # deferred import — avoids circular import
      from src.core.config import settings

      if ptb_app is None or not settings.DIRECTOR_TG_ID:
          return

      async with async_session() as session:
          result = await session.execute(
              select(FuelAnomaly)
              .where(FuelAnomaly.notified == False)
              .where(FuelAnomaly.is_false_alarm == False)
              .order_by(FuelAnomaly.created_at.asc())
          )
          anomalies = result.scalars().all()

          if not anomalies:
              return

          lines = [f"Аномалии расхода топлива ({len(anomalies)} новых):"]
          for a in anomalies:
              lines.append(
                  f"- Борт {a.vehicle_id}, рейс {a.trip_id}: "
                  f"{a.actual_per_100km:.1f} л/100км "
                  f"(норма {a.norm_per_100km:.1f}, превышение +{a.excess_percent:.0f}%)"
              )
          message = "\n".join(lines)

          try:
              await ptb_app.bot.send_message(
                  chat_id=settings.DIRECTOR_TG_ID,
                  text=message,
              )
              for a in anomalies:
                  a.notified = True
                  session.add(a)
              await session.commit()
              logger.info(f"Anomaly digest sent: {len(anomalies)} anomalies")
          except Exception as e:
              logger.error(f"Failed to send anomaly digest to director: {e}")
  ```

  Step B — Update src/main.py to add APScheduler:
  Read src/main.py. Add the following:

  1. New import at top:
     ```python
     from apscheduler.schedulers.asyncio import AsyncIOScheduler
     from src.services.anomaly import run_anomaly_digest
     ```

  2. Create scheduler at module level (after imports, before lifespan):
     ```python
     scheduler = AsyncIOScheduler(timezone="UTC")
     ```

  3. In the lifespan function, add scheduler setup BEFORE the `async with ptb_app:` block (so it starts independently of PTB):
     ```python
     scheduler.add_job(run_anomaly_digest, 'interval', hours=1, id='anomaly_digest')
     scheduler.start()  # NOTE: do NOT await — APScheduler 3.x start() is synchronous
     ```

  4. After the yield (in shutdown), add:
     ```python
     scheduler.shutdown(wait=False)
     ```

  Step C — Update antigravity_modules/expense_flow.py to call anomaly check after FUEL expense save:
  Read the current process_final_expense() function. After the successful `create_expense()` call (when expense is not None) and only for FUEL type, add the anomaly check:
  ```python
  # Anomaly check for FUEL expenses (ALERT-01 to ALERT-03)
  if expense is not None and expense.expense_type == ExpenseType.FUEL.value:
      from src.services.anomaly import check_fuel_anomaly_after_expense
      async with async_session() as session:
          # Re-fetch expense and vehicle in a new session for anomaly check
          from sqlalchemy import select as sa_select
          from src.db.models import Trip, Vehicle
          trip_result = await session.get(Trip, expense.trip_id)
          if trip_result:
              vehicle_result = await session.get(Vehicle, trip_result.vehicle_id)
              if vehicle_result:
                  exp_result = await session.get(Expense, expense.id)
                  if exp_result:
                      await check_fuel_anomaly_after_expense(session, exp_result, vehicle_result)
  ```
  NOTE: The anomaly check must run in its own session after the expense is committed. The expense object from the original create_expense() session may be detached. Using session.get() with the committed expense.id fetches a fresh attached instance.
  </action>
  <verify>
  Run: `python -m py_compile src/services/anomaly.py` — no syntax errors
  Run: `python -c "from src.services.anomaly import check_fuel_anomaly_after_expense, run_anomaly_digest; print('ok')"` — no ImportError
  Run: `python -m py_compile src/main.py` — no syntax errors
  Run: `python -c "from src.main import scheduler; print(scheduler)"` — should show AsyncIOScheduler object
  </verify>
  <done>src/services/anomaly.py exists with check_fuel_anomaly_after_expense() (ALERT-01 to -03 logic: compute liters/km, 20% threshold, 2 fill-up minimum) and run_anomaly_digest() (ALERT-04: batch Telegram send to DIRECTOR_TG_ID). src/main.py has AsyncIOScheduler started before PTB in lifespan, shutdown after yield. expense_flow.py calls anomaly check after successful FUEL expense commit.</done>
</task>

<task type="auto">
  <name>Task 2: Add anomaly feed page to web panel</name>
  <files>src/web/panel.py, src/web/templates/anomalies.html</files>
  <action>
  Step A — Create src/web/templates/anomalies.html (new file):
  Check anomalies.html does not exist, then create. Follow the same template pattern as expenses.html from plan 02-03. The page lists active (non-false-alarm) anomalies:
  ```html
  {% extends "base.html" %}
  {% block title %}Аномалии расхода{% endblock %}
  {% block content %}
  <h1>Аномалии расхода топлива</h1>
  {% if not anomalies %}
  <p>Нет активных аномалий.</p>
  {% else %}
  <table>
    <thead>
      <tr>
        <th>Дата</th>
        <th>Борт ID</th>
        <th>Рейс</th>
        <th>Факт (л/100км)</th>
        <th>Норма (л/100км)</th>
        <th>Превышение</th>
        <th>Статус</th>
      </tr>
    </thead>
    <tbody>
      {% for anomaly in anomalies %}
      <tr id="anomaly-{{ anomaly.id }}">
        <td>{{ anomaly.created_at.strftime('%d.%m %H:%M') if anomaly.created_at else "—" }}</td>
        <td>{{ anomaly.vehicle_id }}</td>
        <td>{{ anomaly.trip_id }}</td>
        <td>{{ "%.1f"|format(anomaly.actual_per_100km) }}</td>
        <td>{{ "%.1f"|format(anomaly.norm_per_100km) }}</td>
        <td>+{{ "%.0f"|format(anomaly.excess_percent) }}%</td>
        <td>
          {% if not anomaly.is_false_alarm %}
          <form hx-post="/panel/anomalies/{{ anomaly.id }}/dismiss"
                hx-target="#anomaly-{{ anomaly.id }}"
                hx-swap="outerHTML"
                style="display:inline">
            <button type="submit">Ложная тревога</button>
          </form>
          {% else %}
          <span>Ложная тревога</span>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}
  {% endblock %}
  ```
  NOTE: Check how expenses.html from plan 02-03 is structured (extends vs standalone). Follow the same pattern. If templates are standalone (no extends), reproduce the full HTML structure including nav and header.

  Step B — Update src/web/panel.py to add anomaly routes:
  Read panel.py (it was updated in plan 02-03). Add these two routes at the end:

  ```python
  @router.get("/anomalies", response_class=HTMLResponse)
  async def list_anomalies(
      request: Request,
      current_user: dict = Depends(get_current_user_from_cookie),
  ):
      async with async_session() as session:
          result = await session.execute(
              select(FuelAnomaly)
              .where(FuelAnomaly.is_false_alarm == False)
              .order_by(FuelAnomaly.created_at.desc())
          )
          anomalies = result.scalars().all()
      return templates.TemplateResponse(
          "anomalies.html",
          {"request": request, "anomalies": anomalies, "user": current_user},
      )


  @router.post("/anomalies/{anomaly_id}/dismiss", response_class=HTMLResponse)
  async def dismiss_anomaly(
      request: Request,
      anomaly_id: int,
      current_user: dict = Depends(get_current_user_from_cookie),
  ):
      async with async_session() as session:
          result = await session.execute(
              select(FuelAnomaly).where(FuelAnomaly.id == anomaly_id)
          )
          anomaly = result.scalars().first()
          if anomaly:
              anomaly.is_false_alarm = True
              session.add(anomaly)
              await session.commit()
              await session.refresh(anomaly)
      # Return a replacement row showing "false alarm" state
      dismissed_row = f'<tr id="anomaly-{anomaly_id}"><td colspan="7"><em>Отмечена как ложная тревога</em></td></tr>'
      return HTMLResponse(content=dismissed_row)
  ```

  Also add FuelAnomaly to the imports in panel.py:
  ```python
  from src.db.models import Driver, Vehicle, Expense, Trip, FuelAnomaly
  ```

  And add a navigation link to /panel/anomalies in base.html (alongside existing nav links):
  ```html
  <a href="/panel/anomalies">Аномалии</a>
  ```
  </action>
  <verify>
  Run: `python -m py_compile src/web/panel.py` — no syntax errors

  Run: `python -c "from src.web.panel import list_anomalies, dismiss_anomaly; print('routes ok')"` — no ImportError

  Run: `python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('src/web/templates')); env.get_template('anomalies.html'); print('template ok')"` — should print "template ok"
  </verify>
  <done>anomalies.html exists as a template rendering a table of active (non-false-alarm) FuelAnomaly records. Each row has a "ложная тревога" HTMX button (hx-post + hx-target + hx-swap="outerHTML"). GET /panel/anomalies returns anomalies.html with active anomalies. POST /panel/anomalies/{id}/dismiss sets is_false_alarm=True and returns a replacement row fragment. base.html nav includes /panel/anomalies link. FuelAnomaly imported in panel.py.</done>
</task>

</tasks>

<verification>
1. `python -m py_compile src/services/anomaly.py` — no errors
2. `python -m py_compile src/main.py` — no errors
3. `python -c "from src.main import scheduler; print(type(scheduler).__name__)"` — prints AsyncIOScheduler
4. `python -m py_compile src/web/panel.py` — no errors
5. `python -c "from src.web.panel import list_anomalies, dismiss_anomaly"` — no ImportError
6. `grep "run_anomaly_digest" src/main.py` — APScheduler job registered
7. `grep "check_fuel_anomaly_after_expense" antigravity_modules/expense_flow.py` — anomaly check wired into FUEL flow
</verification>

<success_criteria>
- check_fuel_anomaly_after_expense(): computes liters/km*100, creates FuelAnomaly if > 20% over norm AND >= 2 prior fill-ups exist
- run_anomaly_digest(): queries FuelAnomaly WHERE notified=False AND is_false_alarm=False, sends one batch Telegram message to DIRECTOR_TG_ID, marks all as notified
- APScheduler AsyncIOScheduler starts in FastAPI lifespan before PTB block, scheduler.start() is NOT awaited, scheduler.shutdown(wait=False) on exit
- FUEL expense save in expense_flow.py calls check_fuel_anomaly_after_expense() after expense is committed
- GET /panel/anomalies shows active anomalies with excess percentage and "false alarm" button
- POST /panel/anomalies/{id}/dismiss sets is_false_alarm=True, returns HTMX row fragment
</success_criteria>

<output>
After completion, create `.planning/phases/02-expense-control/02-04-SUMMARY.md`
</output>
