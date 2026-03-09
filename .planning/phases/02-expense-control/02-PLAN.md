---
phase: 02-expense-control
plan: 02
type: execute
wave: 2
depends_on:
  - 02-01-PLAN.md
files_modified:
  - antigravity_modules/expense_flow.py
  - antigravity_modules/expense_crud.py
  - antigravity_modules/translations.py
  - src/services/fx.py
autonomous: true
requirements:
  - EXP-01
  - EXP-02
  - EXP-03
  - EXP-04
  - EXP-05
  - EXP-07
  - EXP-08

must_haves:
  truths:
    - "Driver selecting FUEL goes through: liters -> odometer (validated) -> station -> currency -> photo (optional) -> saves expense with liters, odometer_reading, station, fx_rate, amount_kzt"
    - "Odometer validation rejects values <= previous reading OR > previous + 5000 km, with specific error message each case"
    - "Driver selecting PER_DIEM goes through: amount -> currency -> city (stored in comment)"
    - "Driver selecting FINE goes through: amount -> currency -> photo (optional) -> reason in comment"
    - "Driver selecting REPAIR or OTHER goes through: sub-category prompt -> amount -> currency -> photo (optional) -> comment"
    - "Currency choices are KZT, RUB, EUR, USD (CNY removed)"
    - "Duplicate submission within same minute returns 'already submitted' message, not a crash"
    - "FX rate is looked up from static dict in src/services/fx.py and stored in expense.fx_rate"
  artifacts:
    - path: "src/services/fx.py"
      provides: "Static FX rate dict and get_fx_rate() function"
      contains: "FX_RATES_TO_KZT"
    - path: "antigravity_modules/expense_crud.py"
      provides: "Updated create_expense() with new fields + get_last_fuel_odometer() CRUD function"
      contains: "get_last_fuel_odometer"
    - path: "antigravity_modules/expense_flow.py"
      provides: "Refactored ConversationHandler with type-specific branches"
      contains: "AWAITING_FUEL_LITERS"
    - path: "antigravity_modules/translations.py"
      provides: "New string keys for fuel, per diem, fine flows"
      contains: "exp_ask_liters"
  key_links:
    - from: "expense_flow.py receive_expense_type()"
      to: "AWAITING_FUEL_LITERS state"
      via: "if expense_type == ExpenseType.FUEL: return AWAITING_FUEL_LITERS"
      pattern: "AWAITING_FUEL_LITERS"
    - from: "expense_flow.py receive_fuel_odometer()"
      to: "expense_crud.get_last_fuel_odometer()"
      via: "vehicle_id stored in context.user_data from add_expense_handler"
      pattern: "get_last_fuel_odometer"
    - from: "expense_flow.py process_final_expense()"
      to: "expense_crud.create_expense()"
      via: "all type-specific fields passed: liters, odometer_reading, station, fx_rate, amount_kzt, idempotency_minute"
      pattern: "create_expense"
---

<objective>
Refactor the existing expense_flow.py ConversationHandler to add type-specific branches for FUEL, PER_DIEM, FINE, and OTHER. Add odometer validation, static FX rate lookup, and idempotency. Update create_expense() CRUD to accept all new fields.

Purpose: Drivers need dedicated flows per expense type. The existing single-path flow (type -> amount -> currency -> photo -> comment) is not sufficient — FUEL needs liters + odometer + station validation, PER_DIEM needs city, FINE needs reason routing.
Output: Refactored expense_flow.py with type-specific states, new src/services/fx.py, updated expense_crud.py, new translation strings.
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
@src/db/models.py
@src/services/fx.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create FX service and update expense CRUD</name>
  <files>src/services/fx.py, antigravity_modules/expense_crud.py</files>
  <action>
  Step A — Create src/services/fx.py (new file):
  ```python
  # Static FX rates — updated manually when rates need changing.
  # Rate = how many KZT per 1 unit of the foreign currency.
  # Last updated: 2026-03-09 (update this comment when rates are changed)
  FX_RATES_TO_KZT: dict[str, float] = {
      "KZT": 1.0,
      "RUB": 5.5,    # ~1 RUB = 5.5 KZT (approximate)
      "USD": 450.0,  # ~1 USD = 450 KZT (approximate)
      "EUR": 490.0,  # ~1 EUR = 490 KZT (approximate)
  }

  def get_fx_rate(currency: str) -> float:
      """Return KZT conversion rate for currency. Raises KeyError if currency not in table."""
      return FX_RATES_TO_KZT[currency.upper()]
  ```

  Step B — Update antigravity_modules/expense_crud.py:
  Read the file first. Make the following changes:

  1. Add new imports at top:
     ```python
     from sqlalchemy.exc import IntegrityError
     from datetime import datetime
     from src.db.models import ExpenseType, FuelAnomaly
     ```

  2. Add new CRUD function `get_last_fuel_odometer()` after `get_active_trip_for_driver()`:
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

  3. Add new CRUD function `count_fuel_expenses_for_vehicle()` after `get_last_fuel_odometer()`:
     ```python
     async def count_fuel_expenses_for_vehicle(
         session: AsyncSession, vehicle_id: int, exclude_expense_id: int = None
     ) -> int:
         """Count completed FUEL expenses for a vehicle (for anomaly detection minimum check)."""
         from sqlalchemy import func as sql_func
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
     ```

  4. Update the existing `create_expense()` function signature and body to accept and store all new Phase 2 fields. Replace the existing function with:
     ```python
     async def create_expense(
         session: AsyncSession,
         trip_id: int,
         expense_type: str,
         amount: float,
         currency: str,
         photo_file_id: str = None,
         card_photo_file_id: str = None,
         comment: str = None,
         photo_r2_url: str = None,
         # Phase 2 new fields
         liters: float = None,
         odometer_reading: int = None,
         station: str = None,
         fx_rate: float = None,
         amount_kzt: float = None,
         idempotency_minute: datetime = None,
     ) -> Expense | None:
         """Create expense. Returns None if duplicate detected (idempotency constraint)."""
         if idempotency_minute is None:
             now = datetime.utcnow()
             idempotency_minute = now.replace(second=0, microsecond=0)

         expense = Expense(
             trip_id=trip_id,
             expense_type=expense_type,
             amount=amount,
             currency=currency,
             photo_file_id=photo_file_id,
             card_photo_file_id=card_photo_file_id,
             comment=comment,
             photo_r2_url=photo_r2_url,
             status="PENDING",
             liters=liters,
             odometer_reading=odometer_reading,
             station=station,
             fx_rate=fx_rate,
             amount_kzt=amount_kzt,
             idempotency_minute=idempotency_minute,
         )
         try:
             session.add(expense)
             await session.commit()
             await session.refresh(expense)
             return expense
         except IntegrityError:
             await session.rollback()
             return None  # Duplicate — caller shows "already submitted" message
     ```
  </action>
  <verify>
  Run: `python -c "from src.services.fx import get_fx_rate; print(get_fx_rate('USD'), get_fx_rate('KZT'))"` — should print 450.0 1.0
  Run: `python -c "from antigravity_modules.expense_crud import get_last_fuel_odometer, count_fuel_expenses_for_vehicle, create_expense; print('ok')"` — no ImportError
  </verify>
  <done>src/services/fx.py exists with FX_RATES_TO_KZT dict and get_fx_rate() function. expense_crud.py has get_last_fuel_odometer(), count_fuel_expenses_for_vehicle(), and updated create_expense() with all Phase 2 fields and IntegrityError handling.</done>
</task>

<task type="auto">
  <name>Task 2: Refactor expense_flow.py with type-specific branches and update translations</name>
  <files>antigravity_modules/expense_flow.py, antigravity_modules/translations.py</files>
  <action>
  Read both files first.

  Step A — Update antigravity_modules/translations.py:
  Add the following new string keys to the Russian and Kazakh dicts (add to the same structure the existing keys follow). Add after the existing expense-related keys:
  ```python
  # Fuel flow strings
  "exp_ask_liters": {
      "ru": "Сколько литров заправили? (введите число)",
      "kk": "Қанша литр құйдыңыз? (санды енгізіңіз)"
  },
  "exp_ask_odometer": {
      "ru": "Введите текущие показания одометра (км):",
      "kk": "Ағымдағы одометр көрсеткішін енгізіңіз (км):"
  },
  "exp_odo_too_low": {
      "ru": "Одометр должен быть больше предыдущего ({last} км). Введите снова:",
      "kk": "Одометр алдыңғы мәннен ({last} км) үлкен болуы керек. Қайта енгізіңіз:"
  },
  "exp_odo_too_high": {
      "ru": "Одометр слишком большой (разница более 5000 км). Проверьте показания и введите снова:",
      "kk": "Одометр тым үлкен (айырмашылық 5000 км-ден астам). Тексеріп, қайта енгізіңіз:"
  },
  "exp_odo_error": {
      "ru": "Неверный формат. Введите целое число (км):",
      "kk": "Дұрыс емес формат. Бүтін санды енгізіңіз (км):"
  },
  "exp_ask_station": {
      "ru": "Название заправочной станции:",
      "kk": "Жанармай бекетінің атауы:"
  },
  "exp_ask_city": {
      "ru": "Город (для суточных):",
      "kk": "Қала (тәуліктік үшін):"
  },
  "exp_ask_reason": {
      "ru": "Укажите причину/категорию (например: ремонт тормозов, штраф за скорость):",
      "kk": "Себепті/санатты көрсетіңіз (мысалы: тежегіш жөндеу, жылдамдық айыбы):"
  },
  "exp_ask_subcategory": {
      "ru": "Категория расхода (ремонт / запчасти / паром / таможня / другое):",
      "kk": "Шығын санаты (жөндеу / бөлшек / паром / кеден / басқа):"
  },
  "exp_duplicate": {
      "ru": "Такой расход уже зафиксирован в эту минуту. Если это ошибка, подождите минуту и попробуйте снова.",
      "kk": "Бұл шығын осы минутта жазылды. Егер бұл қате болса, бір минут күтіп, қайта көріңіз."
  },
  ```
  Check the existing translation structure in translations.py and follow the exact same pattern (it may use a flat dict per language or a nested dict). Adapt the format accordingly.

  Step B — Refactor antigravity_modules/expense_flow.py:
  Read the current file. Keep all existing function signatures where possible; extend them. Make the following changes:

  1. Add new state constants after the existing ones (AWAITING_EXPENSE_COMMENT = 6):
     ```python
     # Phase 2: type-specific states
     AWAITING_FUEL_LITERS = 7
     AWAITING_FUEL_ODOMETER = 8
     AWAITING_FUEL_STATION = 9
     AWAITING_DIEM_CITY = 10
     ```

  2. Add new import at top:
     ```python
     from src.services.fx import get_fx_rate
     from antigravity_modules.expense_crud import get_last_fuel_odometer
     ```

  3. Update `add_expense_handler()` to also store `vehicle_id` in context.user_data (after storing trip_id):
     ```python
     context.user_data['trip_id'] = trip.id
     context.user_data['vehicle_id'] = trip.vehicle_id  # needed for odometer validation
     ```

  4. Update `receive_expense_type()` to dispatch to type-specific first state:
     Replace the existing `return AWAITING_EXPENSE_AMOUNT` at the end with:
     ```python
     if expense_type == ExpenseType.FUEL:
         await update.message.reply_text(get_text(lang, "exp_ask_liters"), reply_markup=ReplyKeyboardRemove())
         return AWAITING_FUEL_LITERS
     elif expense_type == ExpenseType.PER_DIEM:
         await update.message.reply_text(get_text(lang, "exp_ask_amount"), reply_markup=ReplyKeyboardRemove())
         return AWAITING_EXPENSE_AMOUNT
     else:
         # FINE, REPAIR, OTHER: ask subcategory, then amount
         await update.message.reply_text(get_text(lang, "exp_ask_subcategory"), reply_markup=ReplyKeyboardRemove())
         return AWAITING_EXPENSE_COMMENT  # reuse comment state for subcategory on first pass
     ```
     NOTE: For simplicity, FINE/REPAIR/OTHER all go through amount -> currency -> photo (optional) -> comment/reason. The subcategory or reason is stored in the comment field. Redesign the dispatch to be:
     ```python
     if expense_type == ExpenseType.FUEL:
         await update.message.reply_text(get_text(lang, "exp_ask_liters"), reply_markup=ReplyKeyboardRemove())
         return AWAITING_FUEL_LITERS
     elif expense_type == ExpenseType.PER_DIEM:
         await update.message.reply_text(get_text(lang, "exp_ask_amount"), reply_markup=ReplyKeyboardRemove())
         return AWAITING_EXPENSE_AMOUNT  # then currency -> city in AWAITING_DIEM_CITY
     else:
         # FINE, REPAIR, OTHER — amount first, then currency, photo optional, comment = reason/subcategory
         await update.message.reply_text(get_text(lang, "exp_ask_amount"), reply_markup=ReplyKeyboardRemove())
         return AWAITING_EXPENSE_AMOUNT
     ```

  5. Update `receive_expense_currency()` to dispatch to city prompt for PER_DIEM, or to photo prompt for others:
     ```python
     async def receive_expense_currency(update, context):
         lang = context.user_data.get('lang', 'ru')
         currency = update.message.text.upper()
         context.user_data['currency'] = currency
         expense_type = context.user_data.get('expense_type')
         if expense_type == ExpenseType.PER_DIEM.value:
             await update.message.reply_text(get_text(lang, "exp_ask_city"), reply_markup=ReplyKeyboardRemove())
             return AWAITING_DIEM_CITY
         else:
             await update.message.reply_text(get_text(lang, "exp_ask_photo"), reply_markup=ReplyKeyboardRemove())
             return AWAITING_EXPENSE_PHOTO
     ```

  6. Update the currency keyboard in `receive_expense_amount()` to show KZT, RUB, USD, EUR (remove CNY):
     ```python
     keyboard = [
         [KeyboardButton("KZT"), KeyboardButton("RUB")],
         [KeyboardButton("USD"), KeyboardButton("EUR")]
     ]
     ```

  7. Add new handler functions before `process_final_expense()`:
     ```python
     async def receive_fuel_liters(update, context):
         lang = context.user_data.get('lang', 'ru')
         try:
             liters = float(update.message.text.replace(',', '.'))
             if liters <= 0:
                 raise ValueError
             context.user_data['liters'] = liters
         except ValueError:
             await update.message.reply_text(get_text(lang, "exp_ask_liters"))
             return AWAITING_FUEL_LITERS
         await update.message.reply_text(get_text(lang, "exp_ask_odometer"))
         return AWAITING_FUEL_ODOMETER

     async def receive_fuel_odometer(update, context):
         lang = context.user_data.get('lang', 'ru')
         try:
             new_odo = int(update.message.text.strip())
         except ValueError:
             await update.message.reply_text(get_text(lang, "exp_odo_error"))
             return AWAITING_FUEL_ODOMETER
         vehicle_id = context.user_data.get('vehicle_id')
         async with async_session() as session:
             last_odo = await get_last_fuel_odometer(session, vehicle_id) if vehicle_id else None
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

     async def receive_fuel_station(update, context):
         lang = context.user_data.get('lang', 'ru')
         context.user_data['station'] = update.message.text.strip()
         # After station, ask for amount
         await update.message.reply_text(get_text(lang, "exp_ask_amount"))
         return AWAITING_EXPENSE_AMOUNT

     async def receive_diem_city(update, context):
         lang = context.user_data.get('lang', 'ru')
         context.user_data['comment'] = update.message.text.strip()  # city stored in comment
         # PER_DIEM: no photo needed, go straight to final save
         await process_final_expense_direct(update, context)
         return ConversationHandler.END
     ```

  8. Update `process_final_expense()` to include all Phase 2 fields when calling `create_expense()`, and to handle the duplicate case:
     ```python
     async def process_final_expense(update, context):
         lang = context.user_data.get('lang', 'ru')
         comment = update.message.text
         if comment == "/skip_comment":
             comment = context.user_data.get('comment')  # preserve city/subcategory set earlier

         trip_id = context.user_data.get('trip_id')
         expense_type = context.user_data.get('expense_type')
         expense_type_name = context.user_data.get('expense_type_name', expense_type)
         amount = context.user_data.get('amount')
         currency = context.user_data.get('currency', 'KZT')
         photo_id = context.user_data.get('photo_id')
         card_photo_id = context.user_data.get('card_photo_id')
         photo_r2_url = context.user_data.get('photo_r2_url')
         # Phase 2 fields
         liters = context.user_data.get('liters')
         odometer_reading = context.user_data.get('odometer_reading')
         station = context.user_data.get('station')

         try:
             fx_rate = get_fx_rate(currency)
         except KeyError:
             fx_rate = 1.0  # fallback for unknown currency
         amount_kzt = amount * fx_rate if amount else None

         async with async_session() as session:
             expense = await create_expense(
                 session=session,
                 trip_id=trip_id,
                 expense_type=expense_type,
                 amount=amount,
                 currency=currency,
                 photo_file_id=photo_id,
                 card_photo_file_id=card_photo_id,
                 comment=comment,
                 photo_r2_url=photo_r2_url,
                 liters=liters,
                 odometer_reading=odometer_reading,
                 station=station,
                 fx_rate=fx_rate,
                 amount_kzt=amount_kzt,
             )

         if expense is None:
             await update.message.reply_text(get_text(lang, "exp_duplicate"), reply_markup=get_main_menu(lang, True))
             context.user_data.clear()
             return ConversationHandler.END

         await update.message.reply_text(
             get_text(lang, "exp_success", type=expense_type_name, amount=amount, currency=currency),
             reply_markup=get_main_menu(lang, True)
         )
         context.user_data.clear()
         return ConversationHandler.END
     ```

  9. Add a `process_final_expense_direct()` helper (for PER_DIEM that skips photo) — same logic as process_final_expense but called directly from receive_diem_city without an update message with comment text (use context.user_data.get('comment') directly).

  10. Update `get_expense_conversation_handler()` states dict to add the 4 new states:
     ```python
     AWAITING_FUEL_LITERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fuel_liters)],
     AWAITING_FUEL_ODOMETER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fuel_odometer)],
     AWAITING_FUEL_STATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fuel_station)],
     AWAITING_DIEM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_diem_city)],
     ```
  </action>
  <verify>
  Run: `python -c "from antigravity_modules.expense_flow import get_expense_conversation_handler, AWAITING_FUEL_LITERS, AWAITING_FUEL_ODOMETER; print('states ok:', AWAITING_FUEL_LITERS, AWAITING_FUEL_ODOMETER)"` — should print "states ok: 7 8"

  Run: `python -c "from antigravity_modules.translations import get_text; print(get_text('ru', 'exp_ask_liters'))"` — should print the Russian liters prompt string

  Run: `python -m py_compile antigravity_modules/expense_flow.py` — no syntax errors

  Run: `python -m py_compile antigravity_modules/translations.py` — no syntax errors
  </verify>
  <done>expense_flow.py has AWAITING_FUEL_LITERS (7), AWAITING_FUEL_ODOMETER (8), AWAITING_FUEL_STATION (9), AWAITING_DIEM_CITY (10) state constants. receive_fuel_liters, receive_fuel_odometer (with validation), receive_fuel_station, receive_diem_city handler functions exist. receive_expense_type() dispatches to correct state per expense type. process_final_expense() passes liters, odometer_reading, station, fx_rate, amount_kzt to create_expense() and handles None (duplicate) return. Currency keyboard shows KZT, RUB, USD, EUR only. translations.py has exp_ask_liters, exp_ask_odometer, exp_odo_too_low, exp_odo_too_high, exp_ask_station, exp_ask_city, exp_duplicate keys.</done>
</task>

</tasks>

<verification>
1. `python -m py_compile antigravity_modules/expense_flow.py` — no errors
2. `python -c "from src.services.fx import get_fx_rate; print(get_fx_rate('USD'))"` — prints 450.0
3. `python -c "from antigravity_modules.expense_flow import AWAITING_FUEL_LITERS; print(AWAITING_FUEL_LITERS)"` — prints 7
4. `python -c "from antigravity_modules.expense_crud import get_last_fuel_odometer, count_fuel_expenses_for_vehicle"` — no ImportError
5. `python -c "from antigravity_modules.translations import get_text; get_text('ru', 'exp_ask_liters')"` — returns string without KeyError
</verification>

<success_criteria>
- FUEL expense flow: liters -> odometer (with validation against previous reading) -> station -> amount -> currency -> photo (optional) -> saved with all fuel fields
- Odometer validation: rejects new_odo <= last_odo with specific message, rejects new_odo > last_odo + 5000 with specific message
- PER_DIEM flow: amount -> currency -> city (stored in comment)
- FINE/REPAIR/OTHER flow: amount -> currency -> photo (optional) -> reason/comment
- Currency keyboard: KZT, RUB, USD, EUR (CNY removed)
- Duplicate within same minute: create_expense() returns None, bot replies with exp_duplicate message
- FX rate looked up from src/services/fx.py static dict, stored in expense.fx_rate; amount_kzt computed and stored
</success_criteria>

<output>
After completion, create `.planning/phases/02-expense-control/02-02-SUMMARY.md`
</output>
