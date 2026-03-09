import logging
import uuid
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import re
from src.db.database import async_session
from src.db.crud import get_driver_by_tg_id
from src.db.models import ExpenseType
from antigravity_modules.expense_crud import get_active_trip_for_driver, create_expense, get_last_fuel_odometer
from antigravity_modules.translations import get_text, get_main_menu
from src.services.r2 import upload_photo_to_r2
from src.services.fx import get_fx_rate

logger = logging.getLogger(__name__)

AWAITING_EXPENSE_TYPE = 1
AWAITING_EXPENSE_AMOUNT = 2
AWAITING_EXPENSE_CURRENCY = 3
AWAITING_EXPENSE_PHOTO = 4
AWAITING_EXPENSE_CARD_PHOTO = 5
AWAITING_EXPENSE_COMMENT = 6

# Phase 2: type-specific states
AWAITING_FUEL_LITERS = 7
AWAITING_FUEL_ODOMETER = 8
AWAITING_FUEL_STATION = 9
AWAITING_DIEM_CITY = 10

async def add_expense_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id

    async with async_session() as session:
        driver = await get_driver_by_tg_id(session, tg_id)
        if not driver:
            await update.message.reply_text(get_text("ru", "need_reg")) # fallback to ru
            return ConversationHandler.END

        lang = driver.language
        context.user_data['lang'] = lang

        trip = await get_active_trip_for_driver(session, driver.id)
        if not trip:
            await update.message.reply_text(get_text(lang, "exp_no_trip"))
            return ConversationHandler.END

        context.user_data['trip_id'] = trip.id
        context.user_data['vehicle_id'] = trip.vehicle_id  # needed for odometer validation

    keyboard = [
        [KeyboardButton(get_text(lang, "exp_type_fuel")), KeyboardButton(get_text(lang, "exp_type_diem"))],
        [KeyboardButton(get_text(lang, "exp_type_fine")), KeyboardButton(get_text(lang, "exp_type_repair"))],
        [KeyboardButton(get_text(lang, "exp_type_other"))]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        get_text(lang, "exp_ask_type"),
        reply_markup=reply_markup
    )
    return AWAITING_EXPENSE_TYPE

async def receive_expense_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lang = context.user_data.get('lang', 'ru')

    type_map = {
        get_text(lang, "exp_type_fuel"): ExpenseType.FUEL,
        get_text(lang, "exp_type_diem"): ExpenseType.PER_DIEM,
        get_text(lang, "exp_type_fine"): ExpenseType.FINE,
        get_text(lang, "exp_type_repair"): ExpenseType.REPAIR,
        get_text(lang, "exp_type_other"): ExpenseType.OTHER,
    }

    expense_type = type_map.get(text, ExpenseType.OTHER)
    context.user_data['expense_type'] = expense_type.value
    context.user_data['expense_type_name'] = text

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

async def receive_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    try:
        amount = float(update.message.text.replace(',', '.'))
        context.user_data['amount'] = amount
    except ValueError:
        await update.message.reply_text(get_text(lang, "exp_ask_amount"))
        return AWAITING_EXPENSE_AMOUNT

    keyboard = [
        [KeyboardButton("KZT"), KeyboardButton("RUB")],
        [KeyboardButton("USD"), KeyboardButton("EUR")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        get_text(lang, "exp_ask_currency"),
        reply_markup=reply_markup
    )
    return AWAITING_EXPENSE_CURRENCY

async def receive_expense_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    currency = update.message.text.upper()
    context.user_data['currency'] = currency
    expense_type = context.user_data.get('expense_type')
    if expense_type == ExpenseType.PER_DIEM.value:
        await update.message.reply_text(get_text(lang, "exp_ask_city"), reply_markup=ReplyKeyboardRemove())
        return AWAITING_DIEM_CITY
    else:
        await update.message.reply_text(
            get_text(lang, "exp_ask_photo"),
            reply_markup=ReplyKeyboardRemove()
        )
        return AWAITING_EXPENSE_PHOTO

async def receive_expense_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')

    if update.message.photo:
        tg_file = await update.message.photo[-1].get_file()
    elif update.message.document:
        tg_file = await update.message.document.get_file()
    else:
        await update.message.reply_text(get_text(lang, "exp_ask_photo"))
        return AWAITING_EXPENSE_PHOTO

    # Download photo bytes from Telegram servers
    file_bytes = await tg_file.download_as_bytearray()

    # Generate unique R2 key: receipts/{trip_id}/{uuid}.jpg
    trip_id = context.user_data.get('trip_id', 'unknown')
    key = f"receipts/{trip_id}/{uuid.uuid4()}.jpg"

    # Upload to R2 (runs in thread executor, non-blocking)
    r2_url = await upload_photo_to_r2(bytes(file_bytes), key)
    context.user_data['photo_r2_url'] = r2_url
    # Keep legacy photo_id for backward compat during transition
    context.user_data['photo_id'] = tg_file.file_id

    await update.message.reply_text(
        get_text(lang, "exp_ask_card_photo")
    )
    return AWAITING_EXPENSE_CARD_PHOTO

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    context.user_data['photo_id'] = None
    context.user_data['photo_r2_url'] = None
    await update.message.reply_text(
        get_text(lang, "exp_ask_card_photo")
    )
    return AWAITING_EXPENSE_CARD_PHOTO

async def receive_card_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    if update.message.photo:
        context.user_data['card_photo_id'] = update.message.photo[-1].file_id
    elif update.message.document:
        context.user_data['card_photo_id'] = update.message.document.file_id

    await update.message.reply_text(
        get_text(lang, "exp_ask_comment")
    )
    return AWAITING_EXPENSE_COMMENT

async def skip_card_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    context.user_data['card_photo_id'] = None
    await update.message.reply_text(
        get_text(lang, "exp_ask_comment")
    )
    return AWAITING_EXPENSE_COMMENT

# Phase 2: Fuel-specific handlers

async def receive_fuel_liters(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def receive_fuel_odometer(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def receive_fuel_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    context.user_data['station'] = update.message.text.strip()
    # After station, ask for amount
    await update.message.reply_text(get_text(lang, "exp_ask_amount"))
    return AWAITING_EXPENSE_AMOUNT

# Phase 2: PER_DIEM city handler

async def receive_diem_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    context.user_data['comment'] = update.message.text.strip()  # city stored in comment
    # PER_DIEM: no photo needed, go straight to final save
    await process_final_expense_direct(update, context)
    return ConversationHandler.END

async def process_final_expense_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save expense directly (used by PER_DIEM flow that skips photo/comment steps)."""
    lang = context.user_data.get('lang', 'ru')
    comment = context.user_data.get('comment')

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
        return

    # Anomaly check for FUEL expenses (ALERT-01 to ALERT-03)
    if expense is not None and expense.expense_type == ExpenseType.FUEL.value:
        from src.services.anomaly import check_fuel_anomaly_after_expense
        from sqlalchemy import select as sa_select
        from src.db.models import Trip, Vehicle
        async with async_session() as session:
            # Re-fetch expense and vehicle in a new session for anomaly check
            trip_result = await session.get(Trip, expense.trip_id)
            if trip_result:
                vehicle_result = await session.get(Vehicle, trip_result.vehicle_id)
                if vehicle_result:
                    exp_result = await session.get(Expense, expense.id)
                    if exp_result:
                        await check_fuel_anomaly_after_expense(session, exp_result, vehicle_result)

    await update.message.reply_text(
        get_text(lang, "exp_success", type=expense_type_name, amount=amount, currency=currency),
        reply_markup=get_main_menu(lang, True)
    )
    context.user_data.clear()

async def process_final_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Anomaly check for FUEL expenses (ALERT-01 to ALERT-03)
    if expense is not None and expense.expense_type == ExpenseType.FUEL.value:
        from src.services.anomaly import check_fuel_anomaly_after_expense
        from sqlalchemy import select as sa_select
        from src.db.models import Trip, Vehicle
        async with async_session() as session:
            # Re-fetch expense and vehicle in a new session for anomaly check
            trip_result = await session.get(Trip, expense.trip_id)
            if trip_result:
                vehicle_result = await session.get(Vehicle, trip_result.vehicle_id)
                if vehicle_result:
                    exp_result = await session.get(Expense, expense.id)
                    if exp_result:
                        await check_fuel_anomaly_after_expense(session, exp_result, vehicle_result)

    await update.message.reply_text(
        get_text(lang, "exp_success", type=expense_type_name, amount=amount, currency=currency),
        reply_markup=get_main_menu(lang, True)
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    await update.message.reply_text(get_text(lang, "exp_cancelled"), reply_markup=get_main_menu(lang, True))
    context.user_data.clear()
    return ConversationHandler.END


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

        from sqlalchemy import func as sql_func, select as sa_select
        from src.db.models import Expense as ExpenseModel
        result = await session.execute(
            sa_select(
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


def get_expense_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("add_expense", add_expense_handler),
            MessageHandler(filters.Regex(re.compile(r"ДОБАВИТЬ РАСХОД|ШЫҒЫН ҚОСУ", re.IGNORECASE)), add_expense_handler)
        ],
        states={
            AWAITING_EXPENSE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_expense_type)],
            AWAITING_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_expense_amount)],
            AWAITING_EXPENSE_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_expense_currency)],
            AWAITING_EXPENSE_PHOTO: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_expense_photo),
                CommandHandler("skip_photo", skip_photo)
            ],
            AWAITING_EXPENSE_CARD_PHOTO: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_card_photo),
                CommandHandler("skip_card", skip_card_photo)
            ],
            AWAITING_EXPENSE_COMMENT: [
                MessageHandler(filters.TEXT, process_final_expense),
            ],
            AWAITING_FUEL_LITERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fuel_liters)],
            AWAITING_FUEL_ODOMETER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fuel_odometer)],
            AWAITING_FUEL_STATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fuel_station)],
            AWAITING_DIEM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_diem_city)],
        },
        fallbacks=[CommandHandler("cancel", cancel_expense)],
        name="expense_flow",
        persistent=True,
    )
