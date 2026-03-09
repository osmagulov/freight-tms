import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from src.core.config import settings
from src.db.database import async_session
from src.db.crud import get_driver_by_tg_id, create_driver, get_vehicle_by_plate, create_vehicle, update_driver_language, link_driver_to_vehicle
from antigravity_modules.trip_opening import get_trip_conversation_handler, open_trip_handler
from antigravity_modules.expense_flow import get_expense_conversation_handler, add_expense_handler, expense_summary_handler
from antigravity_modules.location_flow import get_location_conversation_handler
from antigravity_modules.trip_closing import get_trip_closing_conversation_handler
from antigravity_modules.translations import get_text, get_main_menu
from antigravity_modules.expense_crud import get_active_trip_for_driver

logger = logging.getLogger(__name__)

# States for registration conversation
AWAITING_LANGUAGE = 1
AWAITING_NAME = 2
AWAITING_PHONE = 3
AWAITING_VEHICLE = 4

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🇷🇺 Русский"), KeyboardButton("🇰🇿 Қазақша")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Привет! Я бот диспетчерской Freight TMS.\nВыберите язык / Тілді таңдаңыз:",
        reply_markup=reply_markup
    )
    return AWAITING_LANGUAGE

async def receive_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    lang_code = "kk" if "Қазақша" in text else "ru"
    context.user_data['lang'] = lang_code
    
    user = update.effective_user
    tg_id = user.id
    
    async with async_session() as session:
        driver = await get_driver_by_tg_id(session, tg_id)
        if driver:
            await update_driver_language(session, tg_id, lang_code)
            
            trip = await get_active_trip_for_driver(session, driver.id)
            has_active_trip = trip is not None
            
            await update.message.reply_text(
                get_text(lang_code, "welcome_back", name=driver.name),
                reply_markup=get_main_menu(lang_code, has_active_trip)
            )
            return ConversationHandler.END
            
    await update.message.reply_text(
        get_text(lang_code, "ask_name"),
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    context.user_data['name'] = name
    
    lang = context.user_data.get('lang', 'ru')
    contact_button = KeyboardButton(get_text(lang, "btn_phone"), request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        get_text(lang, "ask_phone", name=name),
        reply_markup=reply_markup
    )
    return AWAITING_PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text
        
    context.user_data['phone'] = phone
    lang = context.user_data.get('lang', 'ru')
    
    await update.message.reply_text(
        get_text(lang, "ask_vehicle"),
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_VEHICLE

async def receive_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.upper().strip()
    tg_id = update.effective_user.id
    name = context.user_data.get('name')
    phone = context.user_data.get('phone')
    
    async with async_session() as session:
        # Create or look up vehicle by license plate
        vehicle = await get_vehicle_by_plate(session, plate)
        if not vehicle:
            vehicle = await create_vehicle(session, plate)

        # Create driver record
        lang = context.user_data.get('lang', 'ru')
        driver = await create_driver(session, tg_id=tg_id, name=name, phone=phone, language=lang)

        # Link driver to vehicle (fixes REG-02: driver.vehicle_id FK was previously never set)
        await link_driver_to_vehicle(session, driver.id, vehicle.id)

    await update.message.reply_text(
        get_text(lang, "reg_success", name=name, phone=phone, plate=plate),
        reply_markup=get_main_menu(lang, False)
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    # Can't know if has_active_trip without query, but registration means usually no trip 
    await update.message.reply_text(
        get_text(lang, "reg_cancelled"),
        reply_markup=get_main_menu(lang, False)
    )
    return ConversationHandler.END

async def menu_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    
    async with async_session() as session:
        driver = await get_driver_by_tg_id(session, tg_id)
        if not driver:
            await update.message.reply_text(get_text("ru", "need_reg"))
            return
            
        lang = driver.language
        trip = await get_active_trip_for_driver(session, driver.id)
        has_active_trip = trip is not None
        
        await update.message.reply_text(
            "Меню / Мәзір:",
            reply_markup=get_main_menu(lang, has_active_trip)
        )

def register_handlers(app: Application) -> None:
    """Register all ConversationHandlers and command handlers onto a PTB Application instance.
    Called from main.py lifespan so that PicklePersistence is already attached to the app."""
    app.add_handler(CommandHandler("menu", menu_command_handler))

    registration_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_handler)],
        states={
            AWAITING_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_language)],
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AWAITING_PHONE: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), receive_phone)
            ],
            AWAITING_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_vehicle)]
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        name="registration",
        persistent=True,
    )

    app.add_handler(registration_conv)
    app.add_handler(get_trip_conversation_handler())
    app.add_handler(get_expense_conversation_handler())
    app.add_handler(CommandHandler("my_expenses", expense_summary_handler))
    app.add_handler(get_location_conversation_handler())
    app.add_handler(get_trip_closing_conversation_handler())


def create_bot_app() -> Application:
    """Build a standalone PTB Application for local testing (polling mode, no persistence)."""
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    register_handlers(app)
    return app
