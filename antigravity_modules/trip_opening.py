import logging
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from src.db.database import async_session
from src.db.crud import get_driver_by_tg_id
from antigravity_modules.expense_crud import get_planned_trip_for_driver, activate_trip
from antigravity_modules.translations import get_text, get_main_menu

logger = logging.getLogger(__name__)

# States for the trip-opening conversation (dispatcher-first model)
AWAITING_CONFIRMATION = 1
AWAITING_START_ODOMETER = 2


def _yes_no_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """Return a two-button Yes / No keyboard in the driver's language."""
    yes = get_text(lang, "btn_yes")
    no = get_text(lang, "btn_no")
    return ReplyKeyboardMarkup(
        [[KeyboardButton(yes), KeyboardButton(no)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def open_trip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: query the dispatcher-assigned PLANNED trip for this driver."""
    tg_id = update.effective_user.id

    async with async_session() as session:
        driver = await get_driver_by_tg_id(session, tg_id)
        if not driver:
            await update.message.reply_text("Сначала необходимо зарегистрироваться (/start).")
            return ConversationHandler.END

        lang = driver.language or "ru"
        context.user_data["lang"] = lang
        context.user_data["driver_id"] = driver.id

        trip = await get_planned_trip_for_driver(session, driver.id)
        if not trip:
            await update.message.reply_text(
                get_text(lang, "open_trip_no_planned"),
                reply_markup=get_main_menu(lang, has_active_trip=False),
            )
            return ConversationHandler.END

        # Store trip details in user_data for the confirmation and activation steps
        context.user_data["trip_id"] = trip.id
        context.user_data["vehicle_id"] = trip.vehicle_id

        # Build trip detail lines — use sensible fallbacks for optional fields
        route = trip.route_details or "—"
        cargo = trip.load_info or "—"
        client = trip.client_name or "—"
        departure = (
            trip.planned_departure.strftime("%d.%m.%Y %H:%M")
            if trip.planned_departure
            else "—"
        )

    await update.message.reply_text(
        get_text(
            lang,
            "open_trip_confirm_details",
            route=route,
            cargo=cargo,
            client=client,
            departure=departure,
        ),
        reply_markup=_yes_no_keyboard(lang),
    )
    return AWAITING_CONFIRMATION


async def receive_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Driver confirms or declines departure."""
    lang = context.user_data.get("lang", "ru")
    text = update.message.text.strip()

    yes_value = get_text(lang, "btn_yes")
    no_value = get_text(lang, "btn_no")

    if text == no_value:
        await update.message.reply_text(
            get_text(lang, "open_trip_cancelled"),
            reply_markup=get_main_menu(lang, has_active_trip=False),
        )
        context.user_data.clear()
        return ConversationHandler.END

    if text != yes_value:
        # Unrecognised input — re-ask
        await update.message.reply_text(
            get_text(lang, "open_trip_confirm_prompt"),
            reply_markup=_yes_no_keyboard(lang),
        )
        return AWAITING_CONFIRMATION

    await update.message.reply_text(
        get_text(lang, "open_trip_ask_odo"),
        reply_markup=ReplyKeyboardRemove(),
    )
    return AWAITING_START_ODOMETER


async def receive_start_odometer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive start odometer reading, activate the trip and vehicle."""
    lang = context.user_data.get("lang", "ru")
    odometer_text = update.message.text.strip()

    try:
        odometer = int(odometer_text)
        if odometer < 0:
            raise ValueError("negative odometer")
    except ValueError:
        await update.message.reply_text(get_text(lang, "open_trip_odo_error"))
        return AWAITING_START_ODOMETER

    trip_id = context.user_data.get("trip_id")
    vehicle_id = context.user_data.get("vehicle_id")

    async with async_session() as session:
        trip = await activate_trip(session, trip_id, odometer, vehicle_id)

    if not trip:
        logger.error(
            "activate_trip returned None for trip_id=%s driver=%s",
            trip_id,
            context.user_data.get("driver_id"),
        )
        await update.message.reply_text(
            get_text(lang, "open_trip_activate_error"),
            reply_markup=get_main_menu(lang, has_active_trip=False),
        )
        context.user_data.clear()
        return ConversationHandler.END

    route = trip.route_details or "—"
    await update.message.reply_text(
        get_text(lang, "open_trip_success", route=route, odometer=odometer),
        reply_markup=get_main_menu(lang, has_active_trip=True),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_trip_opening(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback /cancel handler."""
    lang = context.user_data.get("lang", "ru")
    await update.message.reply_text(
        get_text(lang, "open_trip_cancelled"),
        reply_markup=get_main_menu(lang, has_active_trip=False),
    )
    context.user_data.clear()
    return ConversationHandler.END


def get_trip_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("open_trip", open_trip_handler),
            MessageHandler(
                filters.Regex(re.compile(r"НАЧАТЬ РЕЙС|РЕЙСТІ БАСТАУ", re.IGNORECASE)),
                open_trip_handler,
            ),
        ],
        states={
            AWAITING_CONFIRMATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_confirmation)
            ],
            AWAITING_START_ODOMETER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_start_odometer)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_trip_opening)],
        name="trip_opening",
        persistent=True,
    )
