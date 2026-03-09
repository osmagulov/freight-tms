# Phase 2: Expense Control - Research

**Researched:** 2026-03-09
**Domain:** PTB ConversationHandler (expense flows), HTMX inline approval, APScheduler anomaly detection, multi-currency, idempotency
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXP-01 | Driver submits fuel expense: liters + odometer + receipt photo + station name | New FUEL conversation states; odometer stored as Float in new `liters` + `odometer_reading` + `station` fields on Expense |
| EXP-02 | System validates odometer: new > previous AND < previous + 5000 km | CRUD query for last FUEL expense on this vehicle; validation in receive_fuel_odometer handler |
| EXP-03 | Driver submits per diem: amount + currency + city | New PER_DIEM branch in conversation: amount → currency → city; city stored in `comment` or new `city` field |
| EXP-04 | Driver submits fine: photo + amount + reason | New FINE branch: photo (optional per decision) → amount → reason in comment |
| EXP-05 | Driver submits other expenses: category + amount + optional photo | REPAIR/OTHER/PARTS/FERRY/CUSTOMS sub-types or single OTHER type with comment; re-uses existing OTHER flow |
| EXP-06 | Driver sees expense summary: pending / approved / trip total | New bot command `/my_expenses`; SQLAlchemy groupBy on status, SUM(amount) by status for active trip |
| EXP-07 | Multi-currency support KZT/RUB/EUR/USD with rate at submission time | Static FX dict in code; rate stored in new `fx_rate` Float column; `amount_kzt` = amount * fx_rate for normalization |
| EXP-08 | Duplicate prevention: idempotency key = driver + type + amount + minute | DB UniqueConstraint on (trip_id, expense_type, amount, idempotency_minute); catch IntegrityError in create_expense |
| EAPPR-01 | Dispatcher sees approval queue: driver, type, amount, photo | New FastAPI route GET /panel/expenses; SQLAlchemy query Expense JOIN Trip JOIN Driver WHERE status=PENDING |
| EAPPR-02 | Dispatcher approves/rejects with comment via HTMX inline (no page reload) | POST /panel/expenses/{id}/approve and /reject; return `<tr>` fragment with hx-swap="outerHTML"; HTMX loaded in base.html |
| EAPPR-03 | Driver gets bot notification on approval/rejection | FastAPI route calls `await ptb_app.bot.send_message(chat_id=driver.tg_id, text=...)` using global ptb_app from main.py |
| ALERT-01 | System calculates fuel consumption (liters / km) at each fill-up | Pure Python function: liters / (new_odometer - prev_odometer) * 100; called after FUEL expense saved |
| ALERT-02 | Alert when consumption > norm + 20% | Threshold = vehicle.fuel_norm_per_100km * 1.20; compare actual to threshold |
| ALERT-03 | Alert requires minimum 2 prior fill-ups | COUNT previous FUEL expenses for vehicle in CRUD; skip if count < 2 |
| ALERT-04 | Director gets Telegram digest notification hourly | APScheduler AsyncIOScheduler in FastAPI lifespan; hourly cron job collects unnotified alerts, sends batch to DIRECTOR_TG_ID |
| FLEET-03 | Dispatcher sees anomaly feed with "false alarm" button | New GET /panel/anomalies; FuelAnomaly model with `is_false_alarm` bool; HTMX inline toggle via POST /panel/anomalies/{id}/dismiss |
</phase_requirements>

---

## Summary

Phase 2 builds on a fully-deployed Phase 1 foundation: FastAPI + PTB webhook running on Railway, PostgreSQL via asyncpg, Cloudflare R2 for photos, and JWT-authenticated web panel. The brownfield expense flow (`antigravity_modules/expense_flow.py`) already handles a generic multi-step conversation — but it is missing all Phase 2 requirements: no odometer capture, no station name, no per-diem city, no approval status, no FX rate storage, no idempotency, no fuel-specific sub-flow, and no multi-type routing.

The implementation splits into four parallel workstreams after the database migration is in place: (1) PTB bot flows for expense types, (2) HTMX web approval queue, (3) APScheduler anomaly detection, and (4) bot notification wiring. The biggest dependency risk is the schema migration — all workstreams need the new columns before they can be tested end-to-end.

Key architectural fact: `ptb_app` is a module-level global in `src/main.py`. FastAPI route handlers and APScheduler jobs can call `ptb_app.bot.send_message(...)` directly without any additional wiring — this is already the established pattern in this codebase.

**Primary recommendation:** Write one Alembic migration first (adds 7 new columns + 2 new tables), then parallelize the four workstreams: PTB expense flows, HTMX approval panel, APScheduler anomaly scheduler, and the notification integration.

---

## Brownfield Audit: What Exists vs What Is Missing

### Existing Expense Flow — Complete Inventory

| Component | File | What It Does | Gap vs Phase 2 |
|-----------|------|-------------|----------------|
| `get_expense_conversation_handler()` | `expense_flow.py` | ConversationHandler: type → amount → currency → photo → card_photo → comment | Missing: type-specific branches (fuel needs odometer+liters+station; per diem needs city; fine needs reason routing); no status; no FX rate |
| `create_expense()` | `expense_crud.py` | INSERT into expenses with: trip_id, expense_type, amount, currency, photo_file_id, photo_r2_url, card_photo_file_id, comment | Missing: status, approved_by, approved_at, rejection_comment, liters, odometer_reading, station, city, fx_rate, idempotency_minute |
| `Expense` model | `models.py` | id, trip_id, expense_type, amount, currency, photo_file_id, photo_r2_url, card_photo_file_id, comment, created_at | Missing: status (PENDING/APPROVED/REJECTED), approval fields, fuel-specific fields, FX rate, idempotency column |
| `ExpenseType` enum | `models.py` | FUEL, PER_DIEM, FINE, REPAIR, OTHER | Missing: PARTS, FERRY, CUSTOMS (EXP-05 mentions these) — decision needed: add enum values or use OTHER+comment |
| `get_active_trip_for_driver()` | `expense_crud.py` | Queries Trip WHERE status=ACTIVE for a driver | Sufficient — no change needed |
| Currency keyboard | `expense_flow.py` line 93 | Shows RUB, KZT, CNY, USD, EUR | Phase 2 only needs KZT, RUB, EUR, USD (drop CNY per EXP-07) |
| Photo skip | `expense_flow.py` | `/skip_photo` command skips photo | Already optional — matches Phase 2 decision |
| `translations.py` | — | Russian/Kazakh strings for expense types | Missing: fuel-specific prompts (liters, odometer, station), per diem city prompt, fine reason prompt, approval notification strings |

### What Does NOT Exist (Must Be Built)

| Feature | Files to Create | Notes |
|---------|----------------|-------|
| Expense approval status | `models.py` migration | New columns on Expense table |
| FuelAnomaly model | `models.py` + migration | New table entirely |
| Type-specific bot sub-flows | `expense_flow.py` refactor | One ConversationHandler with branching after type selection |
| Odometer validation logic | `expense_crud.py` new function | Query last FUEL expense for same vehicle |
| Static FX table | `src/services/fx.py` (new) | Dict: currency → KZT rate |
| Expense summary bot command | `expense_flow.py` or new module | `/my_expenses` or button |
| Web approval queue | `src/web/panel.py` + template | GET /panel/expenses |
| HTMX inline approve/reject | `src/web/panel.py` POST endpoints | Returns `<tr>` fragment |
| Anomaly detection logic | `src/services/anomaly.py` (new) | Pure function: actual vs norm |
| APScheduler setup | `src/main.py` lifespan | Start/stop with FastAPI |
| Anomaly digest job | `src/services/anomaly.py` | Hourly cron, batch Telegram send |
| Anomaly feed page | `src/web/panel.py` + template | GET /panel/anomalies |
| DIRECTOR_TG_ID config | `src/core/config.py` | New setting |

---

## Standard Stack

### Core (Already Installed — No New pip Installs Needed)

| Library | Version (installed) | Purpose | Why |
|---------|---------------------|---------|-----|
| `python-telegram-bot` | 22.6 | PTB bot flows, `bot.send_message()` | Already used |
| `fastapi` | 0.135.1 | Web panel routes, HTMX endpoints | Already used |
| `SQLAlchemy` | 2.0.48 | ORM, async queries, UniqueConstraint | Already used |
| `alembic` | — (in req) | New schema migration for Phase 2 | Already configured |
| `APScheduler` | 3.11.2 | Hourly anomaly digest job | **Already installed in venv** |
| `jinja2` | — (in req) | Jinja2 templates for approval queue | Already used |

### New to Add to requirements.txt

| Library | Purpose | Notes |
|---------|---------|-------|
| `APScheduler>=3.10.0` | Anomaly digest scheduler | Already in venv (3.11.2), add to requirements.txt |

**Installation:**
```bash
pip install "APScheduler>=3.10.0"
echo "APScheduler>=3.10.0" >> requirements.txt
```

### HTMX — CDN Load (No pip Package)

Add to `base.html` `<head>`:
```html
<script src="https://unpkg.com/htmx.org@2.0.4" integrity="sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+" crossorigin="anonymous"></script>
```

HTMX 2.0.4 is the current stable (2024-2025). No Python package needed — loaded from CDN only.

### Static FX Table — No External Package

Use a plain Python dict in `src/services/fx.py`. Do NOT use any FX API library (decided: static table, not live API).

---

## Architecture Patterns

### Recommended New File Structure (additions only)

```
src/
├── services/
│   ├── r2.py                    # Existing
│   ├── fx.py                    # NEW: static FX rate table
│   └── anomaly.py               # NEW: anomaly detection + APScheduler job
├── web/
│   ├── panel.py                 # Extend: add expense queue + anomaly routes
│   └── templates/
│       ├── base.html            # Extend: add HTMX script tag
│       ├── expenses.html        # NEW: approval queue (full page)
│       ├── expense_row.html     # NEW: single <tr> fragment for HTMX swap
│       └── anomalies.html       # NEW: anomaly feed
├── db/
│   └── models.py                # Extend: Expense new columns, FuelAnomaly table
└── main.py                      # Extend: add APScheduler to lifespan

antigravity_modules/
└── expense_flow.py              # Refactor: add type-specific branches
    expense_crud.py              # Extend: add new CRUD functions
    translations.py              # Extend: add new string keys
```

### Pattern 1: Type-Specific Branches in Single ConversationHandler

**What:** After the driver picks expense type, branch into type-specific state sequences using a dispatch dict. All branches converge at `process_final_expense()`.

**Why:** A single `ConversationHandler` with `persistent=True, name="expense_flow"` is already registered. Adding a second ConversationHandler causes PTB state collision. Instead, add new state constants and branch at `receive_expense_type()`.

**New state constants needed:**
```python
# Existing
AWAITING_EXPENSE_TYPE = 1
AWAITING_EXPENSE_AMOUNT = 2
AWAITING_EXPENSE_CURRENCY = 3
AWAITING_EXPENSE_PHOTO = 4
AWAITING_EXPENSE_CARD_PHOTO = 5
AWAITING_EXPENSE_COMMENT = 6

# New for Phase 2
AWAITING_FUEL_LITERS = 7
AWAITING_FUEL_ODOMETER = 8
AWAITING_FUEL_STATION = 9
AWAITING_DIEM_CITY = 10
```

**Dispatch at receive_expense_type:**
```python
async def receive_expense_type(update, context):
    expense_type = type_map.get(text)
    context.user_data['expense_type'] = expense_type.value

    if expense_type == ExpenseType.FUEL:
        await update.message.reply_text(get_text(lang, "exp_ask_liters"))
        return AWAITING_FUEL_LITERS
    elif expense_type == ExpenseType.PER_DIEM:
        await update.message.reply_text(get_text(lang, "exp_ask_amount"))
        return AWAITING_EXPENSE_AMOUNT  # then → AWAITING_DIEM_CITY
    else:
        # FINE, REPAIR, OTHER: existing flow
        await update.message.reply_text(get_text(lang, "exp_ask_amount"))
        return AWAITING_EXPENSE_AMOUNT
```

**ConversationHandler states extension:**
```python
states={
    # Existing states (unchanged)
    AWAITING_EXPENSE_TYPE: [...],
    AWAITING_EXPENSE_AMOUNT: [...],
    AWAITING_EXPENSE_CURRENCY: [...],
    AWAITING_EXPENSE_PHOTO: [...],
    AWAITING_EXPENSE_CARD_PHOTO: [...],
    AWAITING_EXPENSE_COMMENT: [...],

    # New fuel-specific states
    AWAITING_FUEL_LITERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fuel_liters)],
    AWAITING_FUEL_ODOMETER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fuel_odometer)],
    AWAITING_FUEL_STATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fuel_station)],
    AWAITING_DIEM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_diem_city)],
}
```

### Pattern 2: Odometer Validation (EXP-02)

**What:** After driver enters odometer for a FUEL expense, query the last fuel expense for the vehicle and validate:
1. new_odometer > last_odometer
2. new_odometer < last_odometer + 5000

**CRUD query for last fuel odometer:**
```python
async def get_last_fuel_odometer(session: AsyncSession, vehicle_id: int) -> int | None:
    """Return the odometer reading of the most recent FUEL expense for this vehicle."""
    result = await session.execute(
        select(Expense)
        .join(Trip, Expense.trip_id == Trip.id)
        .where(Trip.vehicle_id == vehicle_id)
        .where(Expense.expense_type == ExpenseType.FUEL.value)
        .where(Expense.odometer_reading.isnot(None))
        .order_by(Expense.created_at.desc())
        .limit(1)
    )
    expense = result.scalars().first()
    return expense.odometer_reading if expense else None
```

**Validation in handler:**
```python
async def receive_fuel_odometer(update, context):
    try:
        new_odo = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(get_text(lang, "exp_odo_error"))
        return AWAITING_FUEL_ODOMETER

    async with async_session() as session:
        # Need vehicle_id for the driver's active trip
        trip = await get_active_trip_for_driver(session, driver.id)
        last_odo = await get_last_fuel_odometer(session, trip.vehicle_id)

    if last_odo is not None:
        if new_odo <= last_odo:
            await update.message.reply_text(get_text(lang, "exp_odo_too_low", last=last_odo))
            return AWAITING_FUEL_ODOMETER
        if new_odo > last_odo + 5000:
            await update.message.reply_text(get_text(lang, "exp_odo_too_high"))
            return AWAITING_FUEL_ODOMETER

    context.user_data['odometer_reading'] = new_odo
    await update.message.reply_text(get_text(lang, "exp_ask_station"))
    return AWAITING_FUEL_STATION
```

**Critical:** The `vehicle_id` must be stored in `context.user_data` at the start of the expense flow (fetched alongside `trip_id` in `add_expense_handler`).

### Pattern 3: Static FX Table (EXP-07)

**What:** A plain dict maps currency code → KZT rate. Rate is snapshotted at submission time and stored in the `fx_rate` column. This is the decided approach — no live API.

**File: `src/services/fx.py`:**
```python
# Static FX rates — updated manually when dispatcher decides rates need changing.
# Rate = how many KZT per 1 unit of foreign currency.
# Last updated: 2026-03-09 (update this comment when rates are changed)
FX_RATES_TO_KZT: dict[str, float] = {
    "KZT": 1.0,
    "RUB": 5.5,    # ~1 RUB = 5.5 KZT (approximate)
    "USD": 450.0,  # ~1 USD = 450 KZT (approximate)
    "EUR": 490.0,  # ~1 EUR = 490 KZT (approximate)
}

def get_fx_rate(currency: str) -> float:
    """Return KZT rate for currency. Raises KeyError if currency not supported."""
    return FX_RATES_TO_KZT[currency.upper()]
```

**In `create_expense()`, add:**
```python
from src.services.fx import get_fx_rate

fx_rate = get_fx_rate(currency)
amount_kzt = amount * fx_rate
# Store fx_rate and amount_kzt on Expense
```

**Note:** Store actual exchange rates as entered, not hardcoded — the dispatcher updates the static dict file directly. The `fx_rate` column captures the rate at submission time for audit purposes.

### Pattern 4: Idempotency Key (EXP-08)

**What:** Duplicate prevention using a DB-level UniqueConstraint on (trip_id, expense_type, amount, idempotency_minute). The `idempotency_minute` is `datetime.now().replace(second=0, microsecond=0)`.

**Schema — add to Expense model:**
```python
from sqlalchemy import UniqueConstraint
from datetime import datetime

class Expense(Base):
    __tablename__ = "expenses"
    # ... existing columns ...
    idempotency_minute = Column(DateTime(timezone=True), nullable=True)  # truncated to minute

    __table_args__ = (
        UniqueConstraint(
            'trip_id', 'expense_type', 'amount', 'idempotency_minute',
            name='uq_expense_idempotent'
        ),
    )
```

**In `create_expense()` — catch IntegrityError:**
```python
from sqlalchemy.exc import IntegrityError
from datetime import datetime

async def create_expense(..., idempotency_minute: datetime = None) -> Expense | None:
    if idempotency_minute is None:
        now = datetime.utcnow()
        idempotency_minute = now.replace(second=0, microsecond=0)
    try:
        expense = Expense(..., idempotency_minute=idempotency_minute)
        session.add(expense)
        await session.commit()
        return expense
    except IntegrityError:
        await session.rollback()
        return None  # Caller checks for None and shows "already submitted" message
```

**In bot handler, check return value:**
```python
expense = await create_expense(session, ...)
if expense is None:
    await update.message.reply_text(get_text(lang, "exp_duplicate"))
    return ConversationHandler.END
```

### Pattern 5: HTMX Inline Approval Queue (EAPPR-01, EAPPR-02)

**What:** Approval queue page shows a table of PENDING expenses. Each row has "Approve" and "Reject" buttons that use HTMX `hx-post` to submit a form. The server returns a new `<tr>` fragment that replaces the row in place using `hx-swap="outerHTML"`.

**HTMX attribute pattern per HTMX official docs:**
```html
<!-- expense_row.html — the row fragment returned by both GET (queue) and POST (approve/reject) -->
<tr id="expense-{{ expense.id }}">
    <td>{{ expense.trip.driver.name }}</td>
    <td>{{ expense.expense_type }}</td>
    <td>{{ expense.amount }} {{ expense.currency }}</td>
    <td>
        {% if expense.photo_r2_url %}
        <a href="{{ expense.photo_r2_url }}" target="_blank">Фото</a>
        {% else %}нет{% endif %}
    </td>
    <td>
        {% if expense.status == "PENDING" %}
        <form hx-post="/panel/expenses/{{ expense.id }}/approve"
              hx-target="#expense-{{ expense.id }}"
              hx-swap="outerHTML"
              style="display:inline">
            <button type="submit" class="btn btn-approve">Одобрить</button>
        </form>
        <form hx-post="/panel/expenses/{{ expense.id }}/reject"
              hx-target="#expense-{{ expense.id }}"
              hx-swap="outerHTML"
              style="display:inline">
            <input name="comment" placeholder="Причина" style="width:120px">
            <button type="submit" class="btn btn-reject">Отклонить</button>
        </form>
        {% else %}
        <span class="badge-{{ expense.status | lower }}">{{ expense.status }}</span>
        {% if expense.rejection_comment %}— {{ expense.rejection_comment }}{% endif %}
        {% endif %}
    </td>
</tr>
```

**FastAPI route returning row fragment (EAPPR-02):**
```python
@router.post("/expenses/{expense_id}/approve", response_class=HTMLResponse)
async def approve_expense(
    request: Request,
    expense_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        expense = await session.get(Expense, expense_id)
        if expense:
            expense.status = "APPROVED"
            expense.approved_at = datetime.utcnow()
            session.add(expense)
            await session.commit()
            await session.refresh(expense)
            # Eager load relationships for template
            await session.refresh(expense, ["trip"])
        # Send bot notification (EAPPR-03) — see Pattern 6
        await notify_driver_expense_decision(expense, approved=True)
    return templates.TemplateResponse(
        "expense_row.html",
        {"request": request, "expense": expense}
    )
```

**Critical HTMX table row swap caveat:** `<tr>` elements cannot be returned bare — they must be wrapped in `<template>` or returned from a Jinja2 template that renders only the `<tr>` tag. The `hx-target="#expense-{{ expense.id }}"` + `hx-swap="outerHTML"` replaces the entire row. Do NOT use `innerHTML` as swap strategy for `<tr>` elements.

**Add HTMX to base.html:**
```html
<!-- Add in <head> of base.html -->
<script src="https://unpkg.com/htmx.org@2.0.4" integrity="sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+" crossorigin="anonymous"></script>
```

### Pattern 6: Bot Notification from FastAPI Route (EAPPR-03)

**What:** After approve/reject, the FastAPI route sends a Telegram message to the driver. The `ptb_app` global in `src/main.py` exposes `.bot` which can call `.send_message()` directly.

**Access pattern (established in this codebase):**
```python
# In src/web/panel.py — import ptb_app from main
from src.main import ptb_app

async def notify_driver_expense_decision(expense: Expense, approved: bool) -> None:
    """Send Telegram message to driver about expense approval/rejection."""
    if ptb_app is None:
        return  # App starting up, skip notification
    try:
        driver_tg_id = expense.trip.driver.tg_id
        if approved:
            text = f"✅ Расход одобрен: {expense.expense_type} {expense.amount} {expense.currency}"
        else:
            text = f"❌ Расход отклонен: {expense.expense_type} {expense.amount} {expense.currency}"
            if expense.rejection_comment:
                text += f"\nПричина: {expense.rejection_comment}"
        await ptb_app.bot.send_message(chat_id=driver_tg_id, text=text)
    except Exception as e:
        logger.error(f"Failed to notify driver {driver_tg_id}: {e}")
        # Do not raise — notification failure should not fail the approval
```

**Circular import warning:** `src/web/panel.py` imports from `src/main.py` for `ptb_app`. This creates a potential circular import (`main.py` imports `panel_router` from `panel.py`). **Solution:** Move `ptb_app` to a separate `src/bot/state.py` module:

```python
# src/bot/state.py — thin module holding the global bot reference
from telegram.ext import Application

ptb_app: Application | None = None
```

Then `main.py` sets `state.ptb_app = ptb_app` after building, and `panel.py` imports from `src.bot.state`. This is the clean pattern to avoid circular imports.

### Pattern 7: APScheduler Anomaly Digest (ALERT-01 — ALERT-04)

**What:** AsyncIOScheduler (v3 API, already installed as 3.11.2) starts in FastAPI lifespan alongside PTB. Runs an async job every hour that queries FuelAnomaly records with `notified=False`, batches them, sends one Telegram message to DIRECTOR_TG_ID, then marks them notified.

**Integration in `src/main.py` lifespan:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.services.anomaly import run_anomaly_digest

scheduler = AsyncIOScheduler(timezone="UTC")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing ptb_app setup ...

    # Start APScheduler
    scheduler.add_job(run_anomaly_digest, 'interval', hours=1, id='anomaly_digest')
    scheduler.start()

    async with ptb_app:
        # ... existing webhook setup ...
        yield

    # Shutdown
    scheduler.shutdown(wait=False)
```

**APScheduler 3.x AsyncIOScheduler key facts (HIGH confidence):**
- `AsyncIOScheduler` runs on the same asyncio event loop as FastAPI/Uvicorn
- `add_job(func, 'interval', hours=1)` — func can be an async coroutine
- `scheduler.start()` is synchronous (not awaited) — this is correct for v3
- `scheduler.shutdown(wait=False)` — pass `wait=False` to avoid blocking during FastAPI shutdown

**Anomaly detection logic in `src/services/anomaly.py`:**
```python
async def check_fuel_anomaly_after_expense(
    session: AsyncSession,
    expense: Expense,
    vehicle: Vehicle,
) -> FuelAnomaly | None:
    """
    Called immediately after a FUEL expense is saved.
    Returns a FuelAnomaly record if anomaly detected, else None.
    """
    if expense.expense_type != ExpenseType.FUEL.value:
        return None
    if vehicle.fuel_norm_per_100km is None:
        return None  # No norm set, can't calculate anomaly

    # Count prior fill-ups for this vehicle (ALERT-03: need >= 2)
    prior_count = await count_fuel_expenses_for_vehicle(session, vehicle.id, exclude_id=expense.id)
    if prior_count < 2:
        return None  # Not enough data for reliable anomaly detection

    # Calculate consumption: liters per 100 km
    if expense.liters is None or expense.odometer_reading is None:
        return None
    prev_odo = await get_last_fuel_odometer_before(session, vehicle.id, expense.created_at)
    if prev_odo is None:
        return None
    km_driven = expense.odometer_reading - prev_odo
    if km_driven <= 0:
        return None
    actual_per_100km = (expense.liters / km_driven) * 100

    # ALERT-02: threshold = norm + 20%
    threshold = vehicle.fuel_norm_per_100km * 1.20
    if actual_per_100km <= threshold:
        return None

    # Create FuelAnomaly record
    anomaly = FuelAnomaly(
        expense_id=expense.id,
        vehicle_id=vehicle.id,
        trip_id=expense.trip_id,
        actual_per_100km=actual_per_100km,
        norm_per_100km=vehicle.fuel_norm_per_100km,
        threshold_per_100km=threshold,
        excess_percent=((actual_per_100km - vehicle.fuel_norm_per_100km) / vehicle.fuel_norm_per_100km) * 100,
        is_false_alarm=False,
        notified=False,
    )
    session.add(anomaly)
    await session.commit()
    return anomaly
```

**Digest job:**
```python
async def run_anomaly_digest() -> None:
    """Hourly job: send batch Telegram alert to director for unnotified anomalies."""
    from src.bot.state import ptb_app
    from src.core.config import settings

    if ptb_app is None or not settings.DIRECTOR_TG_ID:
        return

    async with async_session() as session:
        result = await session.execute(
            select(FuelAnomaly)
            .where(FuelAnomaly.notified == False)
            .where(FuelAnomaly.is_false_alarm == False)
        )
        anomalies = result.scalars().all()

        if not anomalies:
            return

        lines = [f"🚨 Аномалии расхода топлива ({len(anomalies)}):"]
        for a in anomalies:
            lines.append(
                f"• Борт {a.vehicle_id}, рейс {a.trip_id}: "
                f"{a.actual_per_100km:.1f} л/100км "
                f"(норма {a.norm_per_100km:.1f}, превышение {a.excess_percent:.0f}%)"
            )
        message = "\n".join(lines)

        try:
            await ptb_app.bot.send_message(
                chat_id=settings.DIRECTOR_TG_ID,
                text=message
            )
            # Mark all as notified
            for a in anomalies:
                a.notified = True
                session.add(a)
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to send anomaly digest: {e}")
```

### Pattern 8: Expense Summary in Bot (EXP-06)

**What:** Driver can request expense summary showing pending/approved totals. Implemented as a bot command or keyboard button triggering a simple async CRUD query.

```python
async def expense_summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    async with async_session() as session:
        driver = await get_driver_by_tg_id(session, tg_id)
        trip = await get_active_trip_for_driver(session, driver.id)
        if not trip:
            await update.message.reply_text(get_text(lang, "exp_no_trip"))
            return

        result = await session.execute(
            select(Expense.status, func.sum(Expense.amount_kzt), func.count())
            .where(Expense.trip_id == trip.id)
            .group_by(Expense.status)
        )
        rows = result.all()

    # Format summary message
    summary_lines = [f"📊 Расходы по рейсу:"]
    total_kzt = 0
    for status, sum_kzt, count in rows:
        summary_lines.append(f"  {status}: {count} поз. / {sum_kzt:.0f} KZT")
        total_kzt += (sum_kzt or 0)
    summary_lines.append(f"  ИТОГО: {total_kzt:.0f} KZT")
    await update.message.reply_text("\n".join(summary_lines))
```

### Anti-Patterns to Avoid

- **Adding a second ConversationHandler for FUEL** — PTB routes updates to the first matching handler; a second "expense_fuel" handler would conflict with the existing "expense_flow" handler
- **Calling `scheduler.start()` inside `async with ptb_app:`** — scheduler should be outside the ptb_app context manager to start independently; if PTB fails to set webhook, scheduler still runs
- **Importing `ptb_app` from `main.py` in `panel.py`** — creates circular import; use `src/bot/state.py` as intermediary module
- **Awaiting `scheduler.start()`** — APScheduler 3.x `start()` is synchronous; do not `await` it
- **Storing FX rate from live API** — decided against; always use `src/services/fx.py` static dict
- **Returning bare `<tr>` from HTMX endpoint** — must use Jinja2 `TemplateResponse` with a template that renders only the `<tr>` element; bare HTML strings with `<tr>` cause DOM parser issues in some browsers

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Scheduling hourly anomaly job | Custom asyncio task with sleep loop | `APScheduler AsyncIOScheduler` 3.11.2 | Already installed; handles missed jobs, error recovery, graceful shutdown |
| DB-level duplicate prevention | Application-level "check before insert" | `UniqueConstraint` + catch `IntegrityError` | Race condition safe; app-level checks fail under concurrent requests |
| HTMX row swap | JavaScript fetch + DOM manipulation | `hx-post` + `hx-target` + `hx-swap="outerHTML"` | Zero JS; server returns complete `<tr>` fragment |
| Telegram notification from scheduler | New Bot() instance per job | `ptb_app.bot` from `src/bot/state.py` | Reuse the existing initialized bot; avoid rate limits from multiple bot instances |
| Currency conversion at display time | Always convert on read | Store `fx_rate` + `amount_kzt` at write time | Rate changes later; audit requires rate-at-submission |

---

## Common Pitfalls

### Pitfall 1: vehicle_id Not Stored in context.user_data at Start of Expense Flow

**What goes wrong:** `receive_fuel_odometer()` needs `vehicle_id` to query `get_last_fuel_odometer()`. Currently `add_expense_handler()` only stores `trip_id` in context.

**Why it happens:** The original flow didn't need vehicle-level data; only trip_id was required to link the expense.

**How to avoid:** In `add_expense_handler()`, after fetching the active trip, also store `vehicle_id`:
```python
context.user_data['trip_id'] = trip.id
context.user_data['vehicle_id'] = trip.vehicle_id  # ADD THIS
```

**Warning signs:** `KeyError: 'vehicle_id'` in `receive_fuel_odometer`; or odometer validation skipping because vehicle_id is None.

### Pitfall 2: APScheduler 3.x start() is Synchronous — Do NOT await It

**What goes wrong:** `await scheduler.start()` raises `TypeError: object NoneType can't be used in 'await' expression` or silently does nothing.

**Why it happens:** In APScheduler v3 API, `AsyncIOScheduler.start()` is a synchronous method that registers itself on the current event loop. In APScheduler v4 (not installed here), the API changed to async. Version 3.11.2 is installed — use v3 API.

**How to avoid:**
```python
scheduler.start()   # CORRECT — no await
# NOT: await scheduler.start()
```

**Warning signs:** `TypeError` at startup or scheduler jobs never run.

### Pitfall 3: Circular Import When panel.py Imports from main.py

**What goes wrong:** `from src.main import ptb_app` in `panel.py` causes circular import because `main.py` already imports `panel_router` from `panel.py`.

**Why it happens:** Python's module system resolves circular imports partially — `ptb_app` may be `None` when `panel.py` first imports it.

**How to avoid:** Create `src/bot/state.py`:
```python
# src/bot/state.py
from telegram.ext import Application
ptb_app: Application | None = None
```
In `main.py` lifespan, set: `from src.bot import state; state.ptb_app = built_app`
In `panel.py`, import: `from src.bot.state import ptb_app`

**Warning signs:** `ImportError: cannot import name 'ptb_app'` or notifications always silently skipped (ptb_app is None).

### Pitfall 4: HTMX Cannot Swap Bare `<tr>` Tags Due to HTML Spec

**What goes wrong:** Browser silently discards returned `<tr>` fragment before HTMX can swap it, because `<tr>` cannot be parsed as a document fragment without `<tbody>/<table>` context.

**Why it happens:** The HTML parser requires `<tr>` to be inside `<tbody>` or `<table>`. When HTMX receives a response fragment, it uses an innerHTML parser which may reject or relocate bare `<tr>` elements.

**How to avoid:** Use a dedicated Jinja2 template (`expense_row.html`) that renders only `<tr id="expense-{{ expense.id }}">...</tr>` and return it via `TemplateResponse`. HTMX's `hx-swap="outerHTML"` on a `<tr>` target works correctly when the server returns a complete `<tr>` element (not just inner content).

**Warning signs:** Approve button clicks show a network response in DevTools (200 OK, correct HTML) but the row in the table doesn't change.

### Pitfall 5: FuelAnomaly Check Runs Before Expense is Committed

**What goes wrong:** `check_fuel_anomaly_after_expense()` is called before `session.commit()`, so the expense's `id` and `created_at` are not yet set, causing the "prior fill-up count" query to include the current expense and potentially trigger the 2-fill-up minimum incorrectly.

**Why it happens:** SQLAlchemy assigns auto-generated IDs and server-default timestamps only after a flush/commit.

**How to avoid:** Call anomaly check only after `session.commit()` and `session.refresh(expense)`. The CRUD function `create_expense()` should return the committed expense, then the caller runs anomaly check.

**Warning signs:** Anomaly detected on second fill-up instead of third (off-by-one on the minimum count).

### Pitfall 6: ExpenseType.PARTS / FERRY / CUSTOMS Not in Enum

**What goes wrong:** EXP-05 requires "repair, parts, ferry, customs" — but `ExpenseType` enum only has FUEL, PER_DIEM, FINE, REPAIR, OTHER. Storing "PARTS" as a string bypasses the enum.

**Why it happens:** The original design used OTHER as a catch-all. Phase 2 EXP-05 adds more specific categories.

**Decision needed before implementation:** Use OTHER + comment as the catch-all (simplest, no enum change needed) OR add PARTS, FERRY, CUSTOMS to the enum (requires migration, more buttons in bot).

**Recommendation:** Use OTHER + category stored in comment field. The bot asks "Which category?" and stores the answer as `comment = f"{category}: {user_comment}"`. No enum change needed. This avoids a migration for enum values and keeps the bot keyboard compact.

**Warning signs:** If enum values are added and migration is wrong, `IntegrityError` on insert due to enum constraint mismatch.

### Pitfall 7: Anomaly Digest Sends Individual Messages Instead of Batch

**What goes wrong:** A naive loop calling `ptb_app.bot.send_message()` per anomaly hits Telegram's rate limit of 30 messages/second or 20 messages/minute to the same chat.

**Why it happens:** If many anomalies accumulate over an hour (unlikely in MVP with <20 drivers, but possible), individual sends will be rate-limited.

**How to avoid:** Batch all unnotified anomalies into a single message (or at most 2-3 messages if content exceeds Telegram's 4096-char limit). The digest job already does this per Pattern 7 above.

---

## Schema Changes Required

### New Columns on Expense Table

```python
# Alembic migration additions to expenses table:
status = Column(String, default="PENDING", nullable=False)       # PENDING/APPROVED/REJECTED
approved_by = Column(String, nullable=True)                      # dispatcher username from JWT
approved_at = Column(DateTime(timezone=True), nullable=True)
rejection_comment = Column(String, nullable=True)

# Fuel-specific
liters = Column(Float, nullable=True)                            # EXP-01
odometer_reading = Column(Integer, nullable=True)                # EXP-01, EXP-02
station = Column(String, nullable=True)                          # EXP-01

# Multi-currency
fx_rate = Column(Float, nullable=True)                           # EXP-07: rate to KZT at submission
amount_kzt = Column(Float, nullable=True)                        # EXP-07: normalized amount

# Idempotency
idempotency_minute = Column(DateTime(timezone=True), nullable=True)  # EXP-08

# UniqueConstraint
__table_args__ = (
    UniqueConstraint('trip_id', 'expense_type', 'amount', 'idempotency_minute',
                     name='uq_expense_idempotent'),
)
```

### New FuelAnomaly Table

```python
class FuelAnomaly(Base):
    __tablename__ = "fuel_anomalies"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)

    actual_per_100km = Column(Float, nullable=False)
    norm_per_100km = Column(Float, nullable=False)
    threshold_per_100km = Column(Float, nullable=False)
    excess_percent = Column(Float, nullable=False)

    is_false_alarm = Column(Boolean, default=False, nullable=False)
    notified = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    expense = relationship("Expense")
    vehicle = relationship("Vehicle")
    trip = relationship("Trip")
```

### New Settings

```python
# Add to src/core/config.py Settings class:
DIRECTOR_TG_ID: int = 0   # Telegram user ID of director for anomaly digests
```

---

## Code Examples

### Expense Status Query for Approval Queue (EAPPR-01)

```python
# Source: SQLAlchemy 2.0 docs + codebase conventions
async def get_pending_expenses(session: AsyncSession) -> list[Expense]:
    result = await session.execute(
        select(Expense)
        .join(Trip, Expense.trip_id == Trip.id)
        .join(Driver, Trip.driver_id == Driver.id)
        .where(Expense.status == "PENDING")
        .options(
            selectinload(Expense.trip).selectinload(Trip.driver),
            selectinload(Expense.trip).selectinload(Trip.vehicle),
        )
        .order_by(Expense.created_at.desc())
    )
    return result.scalars().all()
```

Note: `selectinload` is required here — the template needs `expense.trip.driver.name` and `expense.trip.driver.tg_id`. Without eager loading, accessing these in Jinja2 (outside `async with session`) raises `MissingGreenlet` or `DetachedInstanceError`.

### Count Prior Fuel Expenses for Vehicle (ALERT-03)

```python
from sqlalchemy import func

async def count_fuel_expenses_for_vehicle(
    session: AsyncSession,
    vehicle_id: int,
    exclude_expense_id: int,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Expense)
        .join(Trip, Expense.trip_id == Trip.id)
        .where(Trip.vehicle_id == vehicle_id)
        .where(Expense.expense_type == ExpenseType.FUEL.value)
        .where(Expense.id != exclude_expense_id)
        .where(Expense.odometer_reading.isnot(None))
    )
    return result.scalar() or 0
```

### APScheduler in Lifespan (ALERT-04)

```python
# src/main.py — extend existing lifespan
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.services.anomaly import run_anomaly_digest

scheduler = AsyncIOScheduler(timezone="UTC")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ptb_app
    # ... existing ptb_app build code ...

    # Start anomaly scheduler (synchronous call — do NOT await)
    scheduler.add_job(run_anomaly_digest, 'interval', hours=1, id='anomaly_digest',
                      misfire_grace_time=300)  # 5-min grace: tolerate Railway cold start
    scheduler.start()

    async with ptb_app:
        # ... existing webhook setup ...
        yield

    await ptb_app.stop()
    scheduler.shutdown(wait=False)
```

### HTMX Approval Form (base HTML approach)

```html
<!-- expenses.html — full page (EAPPR-01) -->
{% extends "base.html" %}
{% block content %}
<h2>Расходы на одобрение</h2>
<table>
  <thead>
    <tr><th>Водитель</th><th>Тип</th><th>Сумма</th><th>Фото</th><th>Действие</th></tr>
  </thead>
  <tbody id="expenses-tbody">
    {% for expense in expenses %}
      {% include "expense_row.html" %}
    {% endfor %}
  </tbody>
</table>
{% endblock %}

<!-- expense_row.html — fragment returned by POST (EAPPR-02) -->
<tr id="expense-{{ expense.id }}">
  <td>{{ expense.trip.driver.name }}</td>
  <td>{{ expense.expense_type }}</td>
  <td>{{ expense.amount }} {{ expense.currency }}</td>
  <td>{% if expense.photo_r2_url %}<a href="{{ expense.photo_r2_url }}" target="_blank">📷</a>{% endif %}</td>
  <td>
    {% if expense.status == "PENDING" %}
    <form hx-post="/panel/expenses/{{ expense.id }}/approve"
          hx-target="#expense-{{ expense.id }}"
          hx-swap="outerHTML"
          style="display:inline">
      <button type="submit" class="btn">✓ Одобрить</button>
    </form>
    <form hx-post="/panel/expenses/{{ expense.id }}/reject"
          hx-target="#expense-{{ expense.id }}"
          hx-swap="outerHTML"
          style="display:inline">
      <input name="comment" placeholder="Причина отклонения" style="width:140px;padding:4px">
      <button type="submit" class="btn" style="background:#c0392b">✗ Отклонить</button>
    </form>
    {% else %}
    <span>{{ expense.status }}{% if expense.rejection_comment %}: {{ expense.rejection_comment }}{% endif %}</span>
    {% endif %}
  </td>
</tr>
```

---

## Wave Planning — Parallelization Map

The single blocking dependency is the Alembic migration (new columns + FuelAnomaly table). All waves below depend on it.

```
[WAVE 0] Database Migration — MUST COMPLETE FIRST, ~1 plan
  ├── Add new columns to expenses: status, approved_by, approved_at, rejection_comment,
  │   liters, odometer_reading, station, fx_rate, amount_kzt, idempotency_minute
  ├── Add UniqueConstraint uq_expense_idempotent to expenses
  ├── Create fuel_anomalies table (FuelAnomaly model)
  ├── Add DIRECTOR_TG_ID to Settings + config.py
  ├── Add APScheduler to requirements.txt
  └── Create src/bot/state.py (ptb_app global)
  BLOCKS: ALL other waves

[WAVE 1] Parallel — 3 plans can run simultaneously after WAVE 0:

  [PLAN A] Bot Expense Flows — ~2 plans
    ├── Plan A1: Refactor expense_flow.py — add fuel branch (liters, odometer, station)
    │   + add per diem city branch + add FX rate lookup + add idempotency key
    │   + add translations for new prompts (ru + kk)
    ├── Plan A2: Add expense summary command + update expense_crud.py
    │   (get_last_fuel_odometer, count_fuel_expenses, create_expense with new fields)
    DEPENDS ON: WAVE 0

  [PLAN B] HTMX Approval Queue — ~2 plans
    ├── Plan B1: Add HTMX to base.html + create expenses.html + expense_row.html templates
    │   + add GET /panel/expenses route + eager-loading CRUD query
    ├── Plan B2: Add POST /panel/expenses/{id}/approve and /reject routes
    │   + notification via ptb_app.bot.send_message + import from state.py
    DEPENDS ON: WAVE 0

  [PLAN C] APScheduler + Anomaly Detection — ~2 plans
    ├── Plan C1: Create src/services/anomaly.py — check_fuel_anomaly_after_expense() +
    │   run_anomaly_digest() + count/query helpers in expense_crud.py
    ├── Plan C2: Wire APScheduler into src/main.py lifespan + create anomaly feed page
    │   (GET /panel/anomalies + anomalies.html template + false-alarm HTMX dismiss)
    DEPENDS ON: WAVE 0

[WAVE 2] Integration — wire the pieces together
  [PLAN D] Hook anomaly check into FUEL expense save flow (calls check_fuel_anomaly_after_expense
           after create_expense returns committed expense)
  [PLAN E] Wire state.ptb_app into main.py (update lifespan to set state.ptb_app after build)
  DEPENDS ON: WAVE 1 A, B, C all complete
  NOTE: D and E are small (~30 min each) and can be done in one combined plan
```

**Recommended plan count:** 7-8 plans total for Phase 2 (Wave 0: 1, Wave 1: 6, Wave 2: 1 combined).

---

## Open Questions

1. **ExpenseType enum: add PARTS/FERRY/CUSTOMS or use OTHER + comment?**
   - What we know: EXP-05 lists "repair, parts, ferry, customs" as expense types; REPAIR exists; OTHER exists
   - What's unclear: Whether the bot needs separate buttons for PARTS vs FERRY vs CUSTOMS
   - Recommendation: Use `OTHER` + category stored in `comment`. Bot asks "What category?" with keyboard buttons (Parts, Ferry, Customs, Other) and stores selection + optional user comment as comment field. No enum migration needed.

2. **Expense approval notification text — language?**
   - What we know: Bot messages currently support ru + kk; EAPPR-03 just says "driver gets notification"
   - What's unclear: Which language should the notification be sent in?
   - Recommendation: Look up `driver.language` before sending notification; use `get_text(lang, "exp_approved_notification")` pattern consistent with existing translations.

3. **FX rate update process — who updates the static table?**
   - What we know: Static dict in `src/services/fx.py`; no admin UI for it
   - What's unclear: When rates need updating (weekly? monthly?), does the dispatcher edit code directly or is there a config mechanism?
   - Recommendation: Keep as code for Phase 2 (requires redeploy to update). Add a comment in the file noting the last-updated date and rate source. A config file (JSON in Railway volume) could be a Phase 3 enhancement if rates change frequently.

4. **Anomaly digest timing — UTC vs Kazakhstan time?**
   - What we know: APScheduler uses UTC by default; drivers operate in Kazakhstan time (UTC+5 or UTC+6)
   - What's unclear: Should the director receive digest at top of hour UTC or local business hours?
   - Recommendation: Set timezone to "Asia/Almaty" in `AsyncIOScheduler(timezone="Asia/Almaty")` and run at `hour=8` (8 AM Almaty) for a morning digest, rather than every hour. This reduces notification noise. If hourly is required by decision, keep `'interval', hours=1` with UTC.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact for Phase 2 |
|--------------|------------------|--------------|-------------------|
| Celery + Redis for background jobs | APScheduler AsyncIOScheduler | Decided pre-phase (Railway cost) | 3.11.2 already installed; add to requirements.txt only |
| `@app.on_event("startup")` | `@asynccontextmanager lifespan` | FastAPI 0.95+ | Already done in Phase 1; Phase 2 just extends lifespan |
| Polling bot (run_bot.py) | Webhook bot (src/main.py) | Phase 1 | ptb_app global already accessible; send_message works from routes |
| No expense approval | Inline HTMX approval | Phase 2 | HTMX 2.0.4 from CDN; no new pip package |

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection: `antigravity_modules/expense_flow.py`, `antigravity_modules/expense_crud.py`, `src/db/models.py`, `src/web/panel.py`, `src/main.py`, `src/core/config.py` — brownfield inventory and gap analysis
- `apscheduler.readthedocs.io/en/3.x/modules/schedulers/asyncio.html` — AsyncIOScheduler API: start() is sync, add_job accepts async coroutines (verified via venv install: 3.11.2)
- `htmx.org/examples/edit-row/` — HTMX inline row edit pattern: `hx-target="closest tr"`, `hx-swap="outerHTML"`
- `htmx.org/attributes/hx-swap/` — hx-swap strategy documentation
- `docs.sqlalchemy.org/en/20/core/constraints.html` — UniqueConstraint multi-column pattern with `__table_args__`
- Python venv inspection (`python -c "import apscheduler; print(apscheduler.__version__)"`) — confirmed 3.11.2 installed
- Python venv inspection (`python -c "import telegram; print(telegram.__version__)"`) — confirmed PTB 22.6 installed

### Secondary (MEDIUM confidence)

- `testdriven.io/blog/fastapi-htmx/` — HTMX with FastAPI/Jinja2 pattern (verified against HTMX official docs)
- `apscheduler.readthedocs.io/en/3.x/userguide.html` — APScheduler 3.x user guide (partial — confirmed scheduler.start() is not a coroutine from venv test)
- Phase 1 RESEARCH.md and SUMMARY files — established patterns for PTB bot.send_message, circular import risk from ptb_app global

### Tertiary (LOW confidence — flag for validation)

- Anomaly digest timezone recommendation (Asia/Almaty) — logic-derived, not validated against Railway's Railway-specific timezone handling
- HTMX 2.0.4 CDN SRI hash — verify against `https://unpkg.com/htmx.org@2.0.4` before deploy; CDN integrity hashes can change on patch releases

---

## Metadata

**Confidence breakdown:**
- Brownfield audit: HIGH — direct file inspection of all affected modules
- Schema changes: HIGH — derived from requirements, matches existing SQLAlchemy ORM pattern
- APScheduler 3.x integration: HIGH — confirmed installed version 3.11.2, verified API from docs
- HTMX row swap pattern: HIGH — from official HTMX examples + docs
- PTB send_message from FastAPI: HIGH — ptb_app global already established in this codebase
- Circular import warning: HIGH — standard Python import cycle; pattern well-known
- FX static table approach: HIGH — decided before Phase 2, no uncertainty
- Wave/parallelization plan: MEDIUM — depends on actual plan scope sizing by planner

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (APScheduler 3.x + HTMX 2.0 are stable; PTB 22.x API is stable)
