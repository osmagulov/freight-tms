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
import re
from src.db.database import async_session
from src.db.crud import get_driver_by_tg_id
from src.db.models import ExpenseType
from antigravity_modules.expense_crud import get_active_trip_for_driver, create_expense
from antigravity_modules.translations import get_text, get_main_menu

logger = logging.getLogger(__name__)

AWAITING_EXPENSE_TYPE = 1
AWAITING_EXPENSE_AMOUNT = 2
AWAITING_EXPENSE_CURRENCY = 3
AWAITING_EXPENSE_PHOTO = 4
AWAITING_EXPENSE_CARD_PHOTO = 5
AWAITING_EXPENSE_COMMENT = 6

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
    
    await update.message.reply_text(
        get_text(lang, "exp_ask_amount"),
        reply_markup=ReplyKeyboardRemove()
    )
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
        [KeyboardButton("RUB"), KeyboardButton("KZT")],
        [KeyboardButton("CNY"), KeyboardButton("USD"), KeyboardButton("EUR")]
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
    
    await update.message.reply_text(
        get_text(lang, "exp_ask_photo"),
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_EXPENSE_PHOTO

async def receive_expense_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    if update.message.photo:
        context.user_data['photo_id'] = update.message.photo[-1].file_id
    elif update.message.document:
        context.user_data['photo_id'] = update.message.document.file_id
    # If text is /skip_photo skip it, but python-telegram-bot routes commands differently
    # Let's handle it manually or gracefully skip
        
    await update.message.reply_text(
        get_text(lang, "exp_ask_card_photo")
    )
    return AWAITING_EXPENSE_CARD_PHOTO
    
async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    context.user_data['photo_id'] = None
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

async def process_final_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    comment = update.message.text
    if comment == "/skip_comment":
        comment = None
        
    trip_id = context.user_data.get('trip_id')
    expense_type = context.user_data.get('expense_type')
    expense_type_name = context.user_data.get('expense_type_name', expense_type)
    amount = context.user_data.get('amount')
    currency = context.user_data.get('currency')
    photo_id = context.user_data.get('photo_id')
    card_photo_id = context.user_data.get('card_photo_id')
    
    async with async_session() as session:
        await create_expense(
            session=session,
            trip_id=trip_id,
            expense_type=expense_type,
            amount=amount,
            currency=currency,
            photo_file_id=photo_id,
            card_photo_file_id=card_photo_id,
            comment=comment
        )
        
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
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_expense)],
        name="expense_flow",
        persistent=True,
    )
