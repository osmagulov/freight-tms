import logging
from datetime import datetime
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
from src.db.models import Trip, TripStatus
from antigravity_modules.translations import get_text, get_main_menu

logger = logging.getLogger(__name__)

# States for the New Trip conversation
AWAITING_ROUTE = 1
AWAITING_CARGO = 2
AWAITING_DOCUMENTS = 3
AWAITING_START_ODOMETER = 4

async def open_trip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    
    # Check if driver is registered and has a vehicle
    async with async_session() as session:
        driver = await get_driver_by_tg_id(session, tg_id)
        if not driver:
            await update.message.reply_text("Сначала необходимо зарегистрироваться (/start).")
            return ConversationHandler.END
            
        # In MVP, assume the driver is tied to the first vehicle or we prompt them
        # Let's just create a basic trip flow
        context.user_data['driver_id'] = driver.id
        context.user_data['lang'] = driver.language
        
        # NOTE: MVP doesn't have a rigid driver->vehicle relationship link in the db yet, 
        # so we'll just link the new trip to whatever vehicle we can query or ask. 
        # For now let's just use driver_id=1, vehicle_id=1 for testing if needed
        # We assume vehicle exists for the driver.
        
    lang = context.user_data.get('lang', 'ru')
    await update.message.reply_text(
        get_text(lang, "open_trip_ask_route"),
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_ROUTE

async def receive_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    route = update.message.text
    context.user_data['route'] = route
    lang = context.user_data.get('lang', 'ru')
    
    await update.message.reply_text(
        get_text(lang, "open_trip_ask_cargo")
    )
    return AWAITING_CARGO

async def receive_cargo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargo = update.message.text
    context.user_data['cargo'] = cargo
    lang = context.user_data.get('lang', 'ru')
    
    await update.message.reply_text(
        get_text(lang, "open_trip_ask_docs")
    )
    return AWAITING_DOCUMENTS

async def receive_documents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    # Capture the photo file ID
    if update.message.photo:
        # get the largest resolution photo
        photo_id = update.message.photo[-1].file_id 
    elif update.message.document:
        photo_id = update.message.document.file_id
    else:
        await update.message.reply_text(get_text(lang, "open_trip_docs_error"))
        return AWAITING_DOCUMENTS
        
    context.user_data['document_id'] = photo_id
    
    await update.message.reply_text(
        get_text(lang, "open_trip_ask_odo")
    )
    return AWAITING_START_ODOMETER

async def receive_start_odometer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    odometer_text = update.message.text
    try:
        odometer = int(odometer_text)
    except ValueError:
        await update.message.reply_text(get_text(lang, "open_trip_odo_error"))
        return AWAITING_START_ODOMETER
        
    route = context.user_data.get('route')
    cargo = context.user_data.get('cargo')
    document_id = context.user_data.get('document_id')
    driver_id = context.user_data.get('driver_id')
    
    # We create the Trip in DB. 
    # TODO: Connect actual vehicle id here correctly.
    async with async_session() as session:
        new_trip = Trip(
            driver_id=driver_id,
            vehicle_id=1, # Hardcoded for now until we have vehicle selection logic
            route_details=route,
            load_info=cargo,
            status=TripStatus.ACTIVE,
            start_odometer=odometer,
        )
        session.add(new_trip)
        await session.commit()
    
    await update.message.reply_text(
        get_text(lang, "open_trip_success", route=route, cargo=cargo, odometer=odometer),
        reply_markup=get_main_menu(lang, True) # Trip is now active
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    # If they cancelled opening, they probably don't have an active trip
    await update.message.reply_text(get_text(lang, "open_trip_cancelled"), reply_markup=get_main_menu(lang, False))
    context.user_data.clear()
    return ConversationHandler.END

def get_trip_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("open_trip", open_trip_handler),
            MessageHandler(filters.Regex(re.compile(r"НАЧАТЬ РЕЙС|РЕЙСТІ БАСТАУ", re.IGNORECASE)), open_trip_handler)
        ],
        states={
            AWAITING_ROUTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_route)],
            AWAITING_CARGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cargo)],
            AWAITING_DOCUMENTS: [MessageHandler(filters.PHOTO | filters.Document.ALL, receive_documents)],
            AWAITING_START_ODOMETER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_start_odometer)],
        },
        fallbacks=[CommandHandler("cancel", cancel_trip)],
        name="trip_opening",
        persistent=True,
    )
