import logging
import re
from datetime import datetime
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
from src.db.models import TripStatus, Trip
from sqlalchemy.future import select
from antigravity_modules.expense_crud import get_active_trip_for_driver
from antigravity_modules.translations import get_text, get_main_menu

logger = logging.getLogger(__name__)

AWAITING_END_ODOMETER = 1
AWAITING_CLOSING_DOCS = 2

async def close_trip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    
    async with async_session() as session:
        driver = await get_driver_by_tg_id(session, tg_id)
        if not driver:
            await update.message.reply_text(get_text("ru", "need_reg"))
            return ConversationHandler.END
            
        lang = driver.language
        context.user_data['lang'] = lang
        
        trip = await get_active_trip_for_driver(session, driver.id)
        if not trip:
            await update.message.reply_text(get_text(lang, "close_trip_no_trip"), reply_markup=get_main_menu(lang, False))
            return ConversationHandler.END
            
        context.user_data['trip_id'] = trip.id
        context.user_data['start_odometer'] = trip.start_odometer or 0
        
    await update.message.reply_text(
        get_text(lang, "close_trip_ask_odo"),
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_END_ODOMETER

async def receive_end_odometer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    odometer_text = update.message.text
    try:
        odometer = int(odometer_text)
        start_odometer = context.user_data.get('start_odometer', 0)
        if odometer < start_odometer:
            raise ValueError("Odometer must be greater than start")
    except ValueError:
        await update.message.reply_text(get_text(lang, "close_trip_odo_error"))
        return AWAITING_END_ODOMETER
        
    context.user_data['end_odometer'] = odometer
    
    await update.message.reply_text(
        get_text(lang, "close_trip_ask_doc")
    )
    return AWAITING_CLOSING_DOCS

async def receive_closing_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id 
    elif update.message.document:
        photo_id = update.message.document.file_id
    else:
        await update.message.reply_text(get_text(lang, "close_trip_doc_error"))
        return AWAITING_CLOSING_DOCS
        
    trip_id = context.user_data.get('trip_id')
    end_odometer = context.user_data.get('end_odometer')
    start_odometer = context.user_data.get('start_odometer', 0)
    
    diff = end_odometer - start_odometer
    
    async with async_session() as session:
        result = await session.execute(select(Trip).where(Trip.id == trip_id))
        trip = result.scalars().first()
        if trip:
            trip.status = TripStatus.COMPLETED
            trip.end_odometer = end_odometer
            trip.closing_document_id = photo_id
            trip.completed_at = datetime.utcnow()
            session.add(trip)
            await session.commit()
    
    await update.message.reply_text(
        get_text(lang, "close_trip_success", diff=diff),
        reply_markup=get_main_menu(lang, False) # Now no active trip
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_close_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    await update.message.reply_text(get_text(lang, "close_trip_cancelled"), reply_markup=get_main_menu(lang, True)) # They still have the trip open
    context.user_data.clear()
    return ConversationHandler.END

def get_trip_closing_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("close_trip", close_trip_handler),
            MessageHandler(filters.Regex(re.compile(r"ЗАВЕРШИТЬ РЕЙС|РЕЙСТІ АЯҚТАУ", re.IGNORECASE)), close_trip_handler)
        ],
        states={
            AWAITING_END_ODOMETER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_end_odometer)],
            AWAITING_CLOSING_DOCS: [MessageHandler(filters.PHOTO | filters.Document.ALL, receive_closing_docs)],
        },
        fallbacks=[CommandHandler("cancel", cancel_close_trip)],
        name="trip_closing",
        persistent=True,
    )
