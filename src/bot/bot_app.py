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
from src.db.crud import get_driver_by_tg_id, create_driver, get_vehicle_by_plate, create_vehicle

logger = logging.getLogger(__name__)

# States for registration conversation
AWAITING_NAME = 1
AWAITING_PHONE = 2
AWAITING_VEHICLE = 3

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    
    async with async_session() as session:
        driver = await get_driver_by_tg_id(session, tg_id)
        if driver:
            await update.message.reply_text(
                f"С возвращением, {driver.name}! Вы уже зарегистрированы."
            )
            return ConversationHandler.END
            
    await update.message.reply_text(
        f"Привет, {user.first_name}! Я бот диспетчерской Freight TMS.\n"
        "Давайте зарегистрируем вас. Пожалуйста, отправьте ваше полное Имя и Фамилию."
    )
    return AWAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    context.user_data['name'] = name
    
    contact_button = KeyboardButton("Отправить номер телефона", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"Отлично, {name}. Теперь отправьте свой номер телефона, нажав на кнопку ниже (или напишите вручную).",
        reply_markup=reply_markup
    )
    return AWAITING_PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text
        
    context.user_data['phone'] = phone
    
    await update.message.reply_text(
        "Спасибо! И последнее: какой номер вашей машины? (например: 123ABC01)",
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_VEHICLE

async def receive_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.upper().strip()
    tg_id = update.effective_user.id
    name = context.user_data.get('name')
    phone = context.user_data.get('phone')
    
    async with async_session() as session:
        # Create or verify vehicle
        vehicle = await get_vehicle_by_plate(session, plate)
        if not vehicle:
            vehicle = await create_vehicle(session, plate)
            
        # Create driver
        driver = await create_driver(session, tg_id=tg_id, name=name, phone=phone)
        
        # Note: In a complete flow, we'll want to link Driver and Vehicle.
        # But MVP just registers them.
        
    await update.message.reply_text(
        f"✅ Регистрация завершена!\n\nИмя: {name}\nТелефон: {phone}\nМашина: {plate}\n\nТеперь вы можете начать свой первый рейс. Выберите действие в меню.",
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Регистрация отменена. Отправьте /start, чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def create_bot_app() -> Application:
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    
    registration_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_handler)],
        states={
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AWAITING_PHONE: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), receive_phone)
            ],
            AWAITING_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_vehicle)]
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        name="registration"
    )
    
    app.add_handler(registration_conv)
    
    return app
