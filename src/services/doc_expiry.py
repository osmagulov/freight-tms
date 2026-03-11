import logging
from datetime import date, timedelta

from sqlalchemy import select

from src.core.config import settings
from src.db.database import async_session
from src.db.models import Driver, DriverDocument, Vehicle, VehicleDocument

logger = logging.getLogger(__name__)

DRIVER_DOC_LABELS = {
    "driver_license": "ВУ",
    "passport": "Паспорт",
    "medical": "Мед. справка",
    "contract": "Контракт",
    "other": "Документ",
}

VEHICLE_DOC_LABELS = {
    "registration": "Техпаспорт",
    "insurance": "Страховка",
    "inspection": "Техосмотр",
    "customs": "Таможня",
    "other": "Документ",
}


async def run_doc_expiry_check():
    director_tg_id = getattr(settings, "DIRECTOR_TG_ID", None)
    if not director_tg_id:
        return

    today = date.today()
    deadline = today + timedelta(days=30)
    lines = []

    async with async_session() as session:
        driver_docs = await session.execute(
            select(DriverDocument, Driver)
            .join(Driver, DriverDocument.driver_id == Driver.id)
            .where(DriverDocument.expires_at != None)
            .where(DriverDocument.expires_at <= deadline)
            .order_by(DriverDocument.expires_at)
        )
        for doc, driver in driver_docs.all():
            days = (doc.expires_at - today).days
            label = DRIVER_DOC_LABELS.get(doc.doc_type, "Документ")
            name = driver.name or f"Водитель #{driver.id}"
            if days < 0:
                lines.append(f"🔴 {label} — {name} (истёк {abs(days)} дн. назад)")
            elif days == 0:
                lines.append(f"🔴 {label} — {name} (истекает сегодня!)")
            else:
                lines.append(f"{'🔴' if days <= 7 else '🟡'} {label} — {name} (через {days} дн.)")

        vehicle_docs = await session.execute(
            select(VehicleDocument, Vehicle)
            .join(Vehicle, VehicleDocument.vehicle_id == Vehicle.id)
            .where(VehicleDocument.expires_at != None)
            .where(VehicleDocument.expires_at <= deadline)
            .order_by(VehicleDocument.expires_at)
        )
        for doc, vehicle in vehicle_docs.all():
            days = (doc.expires_at - today).days
            label = VEHICLE_DOC_LABELS.get(doc.doc_type, "Документ")
            plate = vehicle.license_plate
            if days < 0:
                lines.append(f"🔴 {label} — {plate} (истёк {abs(days)} дн. назад)")
            elif days == 0:
                lines.append(f"🔴 {label} — {plate} (истекает сегодня!)")
            else:
                lines.append(f"{'🔴' if days <= 7 else '🟡'} {label} — {plate} (через {days} дн.)")

    if not lines:
        return

    from src.main import ptb_app  # deferred import — avoids circular import
    if ptb_app is None:
        return

    text = "⚠️ *Документы истекают:*\n\n" + "\n".join(lines)
    try:
        await ptb_app.bot.send_message(chat_id=director_tg_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Doc expiry notification failed: {e}")
