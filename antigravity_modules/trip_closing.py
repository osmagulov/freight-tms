import logging
import re
import uuid
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
from src.db.models import TripDocument
from antigravity_modules.expense_crud import get_active_trip_for_driver, close_trip_db
from antigravity_modules.translations import get_text, get_main_menu

logger = logging.getLogger(__name__)

AWAITING_END_ODOMETER = 1
AWAITING_DELIVERY_STATUS = 2
AWAITING_CLOSING_DOCS = 3

# Delivery status keyboard button labels (hardcoded — translations.py updated in Plan 02)
_DELIVERY_LABELS = {
    "DELIVERED": {"ru": "✅ ДОСТАВЛЕНО", "kk": "✅ ЖЕТКІЗІЛДІ"},
    "PARTIAL": {"ru": "⚠️ ЧАСТИЧНО", "kk": "⚠️ ІШІНАРА"},
    "FAILED": {"ru": "❌ НЕ ДОСТАВЛЕНО", "kk": "❌ ЖЕТКІЗІЛМЕДІ"},
}

# Maps button text back to delivery status value
_LABEL_TO_STATUS: dict[str, str] = {}
for _status, _langs in _DELIVERY_LABELS.items():
    for _label in _langs.values():
        _LABEL_TO_STATUS[_label] = _status


def _delivery_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """Return a 3-button reply keyboard for delivery status."""
    delivered = _DELIVERY_LABELS["DELIVERED"].get(lang, _DELIVERY_LABELS["DELIVERED"]["ru"])
    partial = _DELIVERY_LABELS["PARTIAL"].get(lang, _DELIVERY_LABELS["PARTIAL"]["ru"])
    failed = _DELIVERY_LABELS["FAILED"].get(lang, _DELIVERY_LABELS["FAILED"]["ru"])
    keyboard = [
        [KeyboardButton(delivered)],
        [KeyboardButton(partial)],
        [KeyboardButton(failed)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


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
        context.user_data['vehicle_id'] = trip.vehicle_id
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

    # Ask driver to confirm delivery outcome
    ask_msg = {
        "ru": "📦 Как завершилась доставка?",
        "kk": "📦 Жеткізу қалай аяқталды?",
    }.get(lang, "📦 Как завершилась доставка?")

    await update.message.reply_text(
        ask_msg,
        reply_markup=_delivery_keyboard(lang)
    )
    return AWAITING_DELIVERY_STATUS


async def receive_delivery_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    text = update.message.text.strip()

    delivery_status = _LABEL_TO_STATUS.get(text)
    if not delivery_status:
        ask_msg = {
            "ru": "⚠️ Нажмите одну из кнопок ниже.",
            "kk": "⚠️ Төмендегі батырмалардың бірін басыңыз.",
        }.get(lang, "⚠️ Нажмите одну из кнопок ниже.")
        await update.message.reply_text(ask_msg, reply_markup=_delivery_keyboard(lang))
        return AWAITING_DELIVERY_STATUS

    context.user_data['delivery_status'] = delivery_status

    await update.message.reply_text(
        get_text(lang, "close_trip_ask_doc"),
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_CLOSING_DOCS


async def receive_closing_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')

    # Detect file type: photo or document (PDF)
    tg_file_id: str | None = None
    mime_type: str = "image/jpeg"

    if update.message.photo:
        tg_file_id = update.message.photo[-1].file_id
        mime_type = "image/jpeg"
    elif update.message.document:
        doc = update.message.document
        tg_file_id = doc.file_id
        mime_type = doc.mime_type or "application/octet-stream"
    else:
        await update.message.reply_text(get_text(lang, "close_trip_doc_error"))
        return AWAITING_CLOSING_DOCS

    trip_id = context.user_data.get('trip_id')
    end_odometer = context.user_data.get('end_odometer')
    start_odometer = context.user_data.get('start_odometer', 0)
    delivery_status = context.user_data.get('delivery_status', 'DELIVERED')
    vehicle_id = context.user_data.get('vehicle_id')

    diff = end_odometer - start_odometer

    # Upload document to R2
    r2_url: str | None = None
    try:
        from src.services.r2 import upload_to_r2
        tg_file = await update.message.bot.get_file(tg_file_id)
        file_bytes = await tg_file.download_as_bytearray()
        key = f"trip-docs/{trip_id}/{uuid.uuid4()}"
        r2_url = await upload_to_r2(bytes(file_bytes), key, content_type=mime_type)
    except Exception as exc:
        logger.error(f"R2 upload failed for trip {trip_id} closing doc: {exc}")
        # Graceful degradation: continue without R2 URL (tg_file_id kept as fallback)

    async with async_session() as session:
        # Save TripDocument record
        doc_record = TripDocument(
            trip_id=trip_id,
            file_type="closing_doc",
            r2_url=r2_url,
            tg_file_id=tg_file_id,
        )
        session.add(doc_record)

        # Close the trip atomically (sets status, delivery_status, vehicle AVAILABLE)
        await close_trip_db(
            session=session,
            trip_id=trip_id,
            end_odometer=end_odometer,
            delivery_status=delivery_status,
            vehicle_id=vehicle_id,
        )

    await update.message.reply_text(
        get_text(lang, "close_trip_success", diff=diff),
        reply_markup=get_main_menu(lang, False)  # No active trip after close
    )

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_close_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    await update.message.reply_text(get_text(lang, "close_trip_cancelled"), reply_markup=get_main_menu(lang, True))  # They still have the trip open
    context.user_data.clear()
    return ConversationHandler.END

def get_trip_closing_conversation_handler() -> ConversationHandler:
    # Build all delivery status button regexes for the filter
    all_labels = list(_LABEL_TO_STATUS.keys())
    delivery_pattern = re.compile("|".join(re.escape(label) for label in all_labels))

    return ConversationHandler(
        entry_points=[
            CommandHandler("close_trip", close_trip_handler),
            MessageHandler(filters.Regex(re.compile(r"ЗАВЕРШИТЬ РЕЙС|РЕЙСТІ АЯҚТАУ", re.IGNORECASE)), close_trip_handler)
        ],
        states={
            AWAITING_END_ODOMETER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_end_odometer)],
            AWAITING_DELIVERY_STATUS: [MessageHandler(filters.Regex(delivery_pattern), receive_delivery_status)],
            AWAITING_CLOSING_DOCS: [MessageHandler(filters.PHOTO | filters.Document.ALL, receive_closing_docs)],
        },
        fallbacks=[CommandHandler("cancel", cancel_close_trip)],
        name="trip_closing",
        persistent=True,
    )
