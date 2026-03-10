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
from src.db.models import LocationUpdate
from antigravity_modules.expense_crud import get_active_trip_for_driver
from antigravity_modules.translations import get_text, get_main_menu

logger = logging.getLogger(__name__)

AWAITING_LOCATION = 1


def _location_keyboard(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=get_text(lang, "loc_btn"), request_location=True)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


async def share_location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id

    async with async_session() as session:
        driver = await get_driver_by_tg_id(session, tg_id)
        if not driver:
            await update.message.reply_text(get_text("ru", "need_reg"))
            return ConversationHandler.END

        lang = driver.language
        context.user_data['lang'] = lang
        context.user_data['driver_id'] = driver.id

        trip = await get_active_trip_for_driver(session, driver.id)
        context.user_data['trip_id'] = trip.id if trip else None

    await update.message.reply_text(
        get_text(lang, "loc_ask"),
        reply_markup=_location_keyboard(lang),
    )
    return AWAITING_LOCATION


async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    location = update.message.location
    if not location:
        # User sent text instead of pressing the location button — resend the button
        await update.message.reply_text(
            get_text(lang, "loc_error"),
            reply_markup=_location_keyboard(lang),
        )
        return AWAITING_LOCATION

    driver_id = context.user_data.get('driver_id')
    trip_id = context.user_data.get('trip_id')

    async with async_session() as session:
        new_loc = LocationUpdate(
            driver_id=driver_id,
            trip_id=trip_id,
            latitude=location.latitude,
            longitude=location.longitude,
        )
        session.add(new_loc)
        await session.commit()

    has_trip = trip_id is not None
    await update.message.reply_text(
        get_text(lang, "loc_success"),
        reply_markup=get_main_menu(lang, has_trip),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    has_trip = context.user_data.get('trip_id') is not None
    await update.message.reply_text("Отменено.", reply_markup=get_main_menu(lang, has_trip))
    context.user_data.clear()
    return ConversationHandler.END


def get_location_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("location", share_location_handler),
            MessageHandler(
                filters.Regex(re.compile(r"ОТПРАВИТЬ ГЕОЛОКАЦИЮ|ГЕОЛОКАЦИЯ ЖІБЕРУ", re.IGNORECASE)),
                share_location_handler,
            ),
        ],
        states={
            AWAITING_LOCATION: [
                MessageHandler(filters.LOCATION, receive_location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_location),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_location)],
        name="location_flow",
        persistent=True,
        allow_reentry=True,  # allows re-triggering entry point if already in this conversation
    )
