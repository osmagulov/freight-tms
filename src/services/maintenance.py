import logging
from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import async_session
from src.db.models import Vehicle, Trip, Expense, ExpenseType

logger = logging.getLogger(__name__)

async def get_vehicle_current_odometer(session: AsyncSession, vehicle_id: int) -> int:
    """
    Calculates the most recent odometer reading for a vehicle from all available sources:
    1. Trip (end_odometer)
    2. Expense (odometer_reading)
    """
    # Max from Trips
    trip_res = await session.execute(
        select(sql_func.max(Trip.end_odometer))
        .where(Trip.vehicle_id == vehicle_id)
    )
    max_trip = trip_res.scalar() or 0

    # Max from Expenses
    exp_res = await session.execute(
        select(sql_func.max(Expense.odometer_reading))
        .join(Trip, Expense.trip_id == Trip.id)
        .where(Trip.vehicle_id == vehicle_id)
        .where(Expense.expense_type == ExpenseType.FUEL.value)
    )
    max_exp = exp_res.scalar() or 0

    return max(max_trip, max_exp)

async def get_maintenance_dashboard_data(session: AsyncSession):
    """Returns a list of vehicles with maintenance progress data."""
    result = await session.execute(select(Vehicle).order_by(Vehicle.license_plate))
    vehicles = result.scalars().all()
    
    dashboard = []
    for v in vehicles:
        current_odo = await get_vehicle_current_odometer(session, v.id)
        # Ensure we don't go below the last maintenance record
        effective_odo = max(current_odo, v.last_maintenance_odometer or 0)
        
        km_since_last = effective_odo - (v.last_maintenance_odometer or 0)
        interval = v.maintenance_interval_km or 60000
        remaining = max(0, interval - km_since_last)
        progress_pct = min(100, (km_since_last / interval) * 100) if interval > 0 else 0
        
        dashboard.append({
            "id": v.id,
            "plate": v.license_plate,
            "model": f"{v.make or ''} {v.model or ''}".strip(),
            "last_maint_odo": v.last_maintenance_odometer or 0,
            "current_odo": effective_odo,
            "km_since_last": km_since_last,
            "interval": interval,
            "remaining": remaining,
            "progress_pct": round(progress_pct, 1),
            "is_critical": remaining < 1000,
            "is_warning": remaining < 2500 and remaining >= 1000
        })
        
    # Sort by urgency (remaining KM ascending)
    dashboard.sort(key=lambda x: x['remaining'])
    return dashboard

async def run_maintenance_alert_check():
    """
    Background job to notify about upcoming maintenance.
    Sends alerts to the director if any vehicle has < 1000 km remaining.
    """
    from src.core.config import settings
    director_tg_id = getattr(settings, "DIRECTOR_TG_ID", None)
    if not director_tg_id:
        return

    async with async_session() as session:
        data = await get_maintenance_dashboard_data(session)
        critical = [v for v in data if v['is_critical']]
        
        if not critical:
            return

        lines = ["⚠️ *Внимание! Рекомендуется Техническое Обслуживание:*"]
        for v in critical:
            lines.append(
                f"• *{v['plate']}* ({v['model']}): осталось {v['remaining']} км "
                f"(Пробег: {v['current_odo']} км, интервал {v['interval']} км)"
            )
            
        text = "\n".join(lines)
        
        from src.main import ptb_app  # deferred import
        if ptb_app:
            try:
                await ptb_app.bot.send_message(chat_id=director_tg_id, text=text, parse_mode="Markdown")
                logger.info(f"Maintenance alerts sent for {len(critical)} vehicles")
            except Exception as e:
                logger.error(f"Failed to send maintenance alerts: {e}")
