---
phase: 02-expense-control
verified: 2026-03-09T00:00:00Z
status: passed
score: 16/16 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Full FUEL expense bot flow end-to-end: liters -> invalid odometer (expect rejection) -> valid odometer -> station -> amount -> KZT -> save"
    expected: "Each step progresses correctly; invalid odometer shows specific Russian error; expense saved with all fuel fields populated"
    why_human: "Telegram ConversationHandler FSM behavior cannot be verified statically"
  - test: "Approve an expense at /panel/expenses; confirm row updates inline and driver receives Telegram notification"
    expected: "Table row swaps to APPROVED state without page reload; driver bot receives 'Расход одобрен: ...' message"
    why_human: "HTMX live behavior and cross-process Telegram notification require a running environment"
  - test: "Submit the same expense type and amount twice within the same minute"
    expected: "Second submission shows 'Такой расход уже зафиксирован в эту минуту...' — no crash, no silent duplicate"
    why_human: "UniqueConstraint violation requires a live database"
  - test: "APScheduler hourly anomaly digest: set DIRECTOR_TG_ID in Railway, trigger an anomaly, wait for next hour"
    expected: "Director receives one batched Telegram message; anomalies.notified set to True afterwards"
    why_human: "Requires configured env, running APScheduler, and a triggered anomaly condition"
---

# Phase 2: Expense Control Verification Report

**Phase Goal:** Drivers can submit all expense types through the bot and dispatchers can approve or reject them inline, with automated fuel anomaly detection alerting the director
**Verified:** 2026-03-09
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Expense model has all Phase 2 columns (status, approved_by, approved_at, rejection_comment, liters, odometer_reading, station, fx_rate, amount_kzt, idempotency_minute) | VERIFIED | `src/db/models.py` lines 95-111: all 10 columns present with correct types and nullability |
| 2 | FuelAnomaly table exists with all required columns and FK relationships | VERIFIED | `src/db/models.py` lines 124-144: FuelAnomaly model complete with expense_id/vehicle_id/trip_id FKs, all calculation fields, is_false_alarm, notified |
| 3 | UniqueConstraint uq_expense_idempotent on (trip_id, expense_type, amount, idempotency_minute) exists | VERIFIED | `src/db/models.py` lines 113-118: `__table_args__` with UniqueConstraint present |
| 4 | Alembic migration covers all Phase 2 schema changes | VERIFIED | `alembic/versions/15882711c59b_phase2_expense_control_schema.py`: 10 expense columns, unique constraint, full fuel_anomalies table including threshold_per_100km |
| 5 | Driver FUEL flow goes through liters -> odometer (validated) -> station -> amount -> currency -> photo | VERIFIED | `expense_flow.py`: AWAITING_FUEL_LITERS=7, AWAITING_FUEL_ODOMETER=8, AWAITING_FUEL_STATION=9; all handler functions present |
| 6 | Odometer validation rejects new_odo <= last_odo and new_odo > last_odo+5000 with specific messages | VERIFIED | `expense_flow.py` lines 216-222: both branches with exp_odo_too_low and exp_odo_too_high |
| 7 | PER_DIEM flow: amount -> currency -> city (stored in comment), no photo step | VERIFIED | `expense_flow.py`: receive_diem_city stores city in comment, calls process_final_expense_direct() skipping photo |
| 8 | FINE/REPAIR/OTHER flow: amount -> currency -> photo (optional) -> comment | VERIFIED | `expense_flow.py` receive_expense_type() routes all three to AWAITING_EXPENSE_AMOUNT |
| 9 | Currency keyboard shows KZT, RUB, USD, EUR only (CNY removed) | VERIFIED | `expense_flow.py` lines 106-109: 2x2 keyboard with exactly KZT/RUB/USD/EUR |
| 10 | Duplicate within same minute returns exp_duplicate message, not a crash | VERIFIED | `expense_crud.py`: IntegrityError caught, returns None; `expense_flow.py` checks None and replies exp_duplicate |
| 11 | FX rate looked up from static dict in src/services/fx.py and stored in expense.fx_rate and amount_kzt | VERIFIED | `src/services/fx.py`: FX_RATES_TO_KZT dict + get_fx_rate(); `expense_flow.py` passes fx_rate and amount_kzt to create_expense() |
| 12 | Dispatcher sees /panel/expenses queue and can approve/reject inline without page reload | VERIFIED | `panel.py`: GET /expenses + POST /approve + POST /reject; `expense_row.html` has hx-post + hx-target + hx-swap="outerHTML" |
| 13 | Driver receives Telegram notification after approve or reject | VERIFIED | `panel.py`: notify_driver_expense_decision() calls ptb_app.bot.send_message() after each POST |
| 14 | FUEL expense save triggers anomaly check; FuelAnomaly created if >20% over norm with 2+ prior fill-ups | VERIFIED | `anomaly.py`: check_fuel_anomaly_after_expense() implements ALERT-01/02/03; `expense_flow.py` calls it in both process_final_expense and process_final_expense_direct |
| 15 | APScheduler runs hourly anomaly digest to director | VERIFIED | `src/main.py`: AsyncIOScheduler started before PTB; scheduler.add_job(run_anomaly_digest, 'interval', hours=1); `anomaly.py` run_anomaly_digest() sends batch Telegram to DIRECTOR_TG_ID |
| 16 | Driver /my_expenses command shows pending/approved/rejected counts with KZT totals for active trip | VERIFIED | `expense_flow.py`: expense_summary_handler() with GROUP BY status query on amount_kzt; `bot_app.py`: CommandHandler('my_expenses', expense_summary_handler) registered |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/db/models.py` | Updated Expense + FuelAnomaly models | VERIFIED | All 10 Phase 2 Expense columns, UniqueConstraint __table_args__, FuelAnomaly class with all fields and FKs |
| `src/core/config.py` | DIRECTOR_TG_ID setting | VERIFIED | Line 28: `DIRECTOR_TG_ID: int = 0` present |
| `alembic/versions/15882711c59b_phase2_expense_control_schema.py` | Migration for all Phase 2 schema | VERIFIED | upgrade() adds 10 columns, unique constraint, creates fuel_anomalies; downgrade() reverses all |
| `src/services/fx.py` | Static FX rate dict and get_fx_rate() | VERIFIED | FX_RATES_TO_KZT with KZT/RUB/USD/EUR; get_fx_rate() raises KeyError for unknown currency |
| `antigravity_modules/expense_crud.py` | create_expense() with Phase 2 fields + get_last_fuel_odometer() + count_fuel_expenses_for_vehicle() | VERIFIED | All three functions present; IntegrityError handling in create_expense() |
| `antigravity_modules/expense_flow.py` | Refactored ConversationHandler with FUEL/DIEM/etc branches + expense_summary_handler | VERIFIED | States 7-10 present; all handler functions; summary handler; full ConversationHandler states dict |
| `antigravity_modules/translations.py` | exp_ask_liters, exp_ask_odometer, exp_odo_too_low/high, exp_ask_station, exp_ask_city, exp_duplicate, exp_summary_* keys | VERIFIED | All keys present in both ru and kk dicts |
| `src/web/panel.py` | GET /expenses, POST /approve, POST /reject, GET /anomalies, POST /dismiss | VERIFIED | All 5 routes present; selectinload eager loading; notify helper with deferred import |
| `src/web/templates/expenses.html` | Full approval queue page | VERIFIED | Extends base.html; table with {% include "expense_row.html" %} |
| `src/web/templates/expense_row.html` | tr fragment with hx-post approve/reject forms | VERIFIED | hx-post + hx-target="#expense-{id}" + hx-swap="outerHTML" on both forms |
| `src/web/templates/anomalies.html` | Anomaly feed with is_false_alarm condition and dismiss button | VERIFIED | Extends base.html; HTMX dismiss button per row |
| `src/web/templates/base.html` | HTMX 2.0.4 script tag + nav links for expenses and anomalies | VERIFIED | Line 7: htmx.org@2.0.4 script; lines 28-29: Расходы and Аномалии nav links present |
| `src/services/anomaly.py` | check_fuel_anomaly_after_expense() + run_anomaly_digest() | VERIFIED | Both functions substantive; ALERT-01 through ALERT-04 logic implemented; deferred ptb_app import |
| `src/main.py` | AsyncIOScheduler in lifespan with anomaly_digest job | VERIFIED | AsyncIOScheduler imported, instantiated at module level, started before PTB, shutdown after yield |
| `src/bot/bot_app.py` | CommandHandler('my_expenses', expense_summary_handler) registered | VERIFIED | Line 174: exact match |
| `requirements.txt` | APScheduler>=3.10.0 | VERIFIED | Line 16: APScheduler>=3.10.0 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `expense_flow.py` receive_expense_type() | AWAITING_FUEL_LITERS state | `if expense_type == ExpenseType.FUEL` | WIRED | Lines 86-88: dispatch present |
| `expense_flow.py` receive_fuel_odometer() | expense_crud.get_last_fuel_odometer() | vehicle_id from context.user_data | WIRED | Lines 213-215: vehicle_id retrieved, function called |
| `expense_flow.py` process_final_expense() | expense_crud.create_expense() | all Phase 2 fields passed | WIRED | Lines 337-352: liters, odometer_reading, station, fx_rate, amount_kzt all passed |
| `expense_flow.py` process_final_expense() | anomaly.check_fuel_anomaly_after_expense() | called after FUEL commit in new session | WIRED | Lines 359-372: FUEL type guard, session.get() re-fetch, call |
| `expense_flow.py` process_final_expense_direct() | anomaly.check_fuel_anomaly_after_expense() | same pattern as above | WIRED | Lines 291-303: both FUEL save paths covered |
| `src/main.py` lifespan | run_anomaly_digest | scheduler.add_job('interval', hours=1) | WIRED | Line 48: exact match |
| anomaly.py run_anomaly_digest() | DIRECTOR_TG_ID Telegram chat | ptb_app.bot.send_message() | WIRED | Lines 124, 149: guard on DIRECTOR_TG_ID != 0; send_message call |
| `expense_row.html` hx-post buttons | POST /panel/expenses/{id}/approve and /reject | HTMX hx-post + hx-target + hx-swap | WIRED | expense_row.html lines 17-29: correct attributes on both forms |
| `panel.py` approve_expense() | driver Telegram notification | notify_driver_expense_decision() | WIRED | Line 188: called after session.commit() and refresh |
| `bot_app.py` register_handlers() | expense_summary_handler | CommandHandler('my_expenses', ...) | WIRED | Line 174: registered |
| expense_summary_handler() | SQLAlchemy SUM(amount_kzt) GROUP BY status | sa_select with sql_func.count/sum | WIRED | Lines 406-414: GROUP BY query on amount_kzt |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| EXP-01 | 01-PLAN, 02-PLAN | Fuel expense: liters + odometer + photo + station | SATISFIED | expense_flow.py FUEL flow; all fields stored in create_expense() |
| EXP-02 | 01-PLAN, 02-PLAN | Odometer validation: new > previous AND < previous + 5000 | SATISFIED | expense_flow.py receive_fuel_odometer() lines 216-222 |
| EXP-03 | 02-PLAN | Per diem: amount + currency + city | SATISFIED | expense_flow.py PER_DIEM -> AWAITING_DIEM_CITY; city stored in comment |
| EXP-04 | 02-PLAN | Fine: photo + amount + reason | SATISFIED | expense_flow.py FINE type -> amount -> currency -> photo -> comment |
| EXP-05 | 02-PLAN | Other expenses: category + amount + photo optional | SATISFIED | expense_flow.py REPAIR/OTHER types -> amount -> currency -> photo -> comment |
| EXP-06 | 05-PLAN | Driver sees expense summary in bot | SATISFIED | expense_summary_handler() with /my_expenses registered |
| EXP-07 | 01-PLAN, 02-PLAN | Multi-currency: amount + currency + rate stored | SATISFIED | src/services/fx.py; fx_rate + amount_kzt in create_expense() |
| EXP-08 | 01-PLAN, 02-PLAN | Idempotency: duplicate within minute rejected | SATISFIED | UniqueConstraint 'uq_expense_idempotent'; IntegrityError -> None -> exp_duplicate message |
| EAPPR-01 | 01-PLAN, 03-PLAN | Dispatcher sees approval queue with driver, type, amount, photo | SATISFIED | GET /panel/expenses with selectinload(Expense.trip).selectinload(Trip.driver) |
| EAPPR-02 | 01-PLAN, 03-PLAN | HTMX inline approve/reject without page reload | SATISFIED | expense_row.html hx-post/hx-target/hx-swap; POST handlers return tr fragment |
| EAPPR-03 | 03-PLAN | Driver notified in bot on approve/reject | SATISFIED | notify_driver_expense_decision() called in both approve and reject routes |
| ALERT-01 | 01-PLAN, 04-PLAN | Compute actual fuel consumption (liters/km * 100) | SATISFIED | anomaly.py line 85: actual_per_100km = (expense.liters / km_driven) * 100 |
| ALERT-02 | 01-PLAN, 04-PLAN | Alert if >20% over norm | SATISFIED | anomaly.py line 88: threshold = vehicle.fuel_norm_per_100km * 1.20 |
| ALERT-03 | 01-PLAN, 04-PLAN | Minimum 2 prior fill-ups required | SATISFIED | anomaly.py lines 71-75: prior_count < 2 returns None |
| ALERT-04 | 01-PLAN, 04-PLAN | Director receives hourly Telegram digest | SATISFIED | run_anomaly_digest() batches; APScheduler interval=1 hour |
| FLEET-03 | 01-PLAN, 04-PLAN | Dispatcher sees anomaly feed with false alarm button | SATISFIED | GET /panel/anomalies; anomalies.html with HTMX dismiss button |

**All 16 requirements SATISFIED. No orphaned requirements.**

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `antigravity_modules/translations.py` | 22-23 | Duplicate key `exp_no_trip` in Russian dict | Info | Second definition wins (Python dict behavior); both are "no active trip" messages; no functional regression |
| `antigravity_modules/expense_flow.py` | 293 | `from sqlalchemy import select as sa_select` imported but not used in process_final_expense_direct() | Info | Unused import; harmless |

No blockers. No warnings.

### Human Verification Required

#### 1. Full FUEL Expense Bot Flow

**Test:** Send /add_expense in Telegram, select fuel type, enter 50 liters, enter an odometer value lower than the last reading, then enter a valid odometer, enter station name, amount, select KZT, skip photo, confirm save
**Expected:** Invalid odometer shows "Одометр должен быть больше предыдущего ({last} км). Введите снова:"; valid odometer proceeds to station; expense saved with liters/odometer/station/fx_rate/amount_kzt populated
**Why human:** Telegram ConversationHandler FSM behavior cannot be verified statically

#### 2. HTMX Inline Approval With Bot Notification

**Test:** Navigate to /panel/expenses (authenticated dispatcher), click Одобрить on a PENDING expense
**Expected:** The table row updates to show APPROVED status without page reload; the driver receives "Расход одобрен: [type] [amount] [currency]" in Telegram
**Why human:** HTMX live behavior and cross-process Telegram notification require a running environment

#### 3. Duplicate Prevention (EXP-08)

**Test:** In the bot, submit the same expense type and amount twice within the same clock minute
**Expected:** Second submission shows "Такой расход уже зафиксирован в эту минуту. Если это ошибка, подождите минуту и попробуйте снова." — no crash, no duplicate record in DB
**Why human:** UniqueConstraint violation requires a live PostgreSQL database

#### 4. APScheduler Hourly Anomaly Digest (ALERT-04)

**Test:** Set DIRECTOR_TG_ID in Railway env, create a fuel consumption anomaly condition (>20% over norm with 2+ prior fill-ups), wait for the next hour boundary
**Expected:** Director receives one Telegram message listing all unnotified anomalies with vehicle ID, trip ID, actual l/100km, norm, and excess %; anomaly records marked notified=True afterwards
**Why human:** Requires configured Railway env, running APScheduler, and a triggered anomaly condition in production

### Gaps Summary

No gaps. All 16 must-haves verified. All 16 requirements (EXP-01 through FLEET-03) satisfied. All key links wired. No blocker or warning anti-patterns.

Phase 2 goal is ACHIEVED: drivers can submit all expense types (FUEL with odometer validation, PER_DIEM, FINE, REPAIR, OTHER) through the bot; dispatchers can approve or reject inline via HTMX with immediate driver notification; fuel anomaly detection runs automatically with 20% threshold and 2-fill-up guard; the director receives hourly digest notifications.

---

_Verified: 2026-03-09_
_Verifier: Claude (gsd-verifier)_
