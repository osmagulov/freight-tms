import logging
from datetime import datetime
from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import async_session
from src.db.models import Expense, FuelAnomaly, Vehicle, Trip, ExpenseType

logger = logging.getLogger(__name__)


async def get_last_fuel_odometer_before(
    session: AsyncSession, vehicle_id: int, before_dt: datetime
) -> int | None:
    """Return the odometer of the FUEL expense immediately before before_dt for this vehicle."""
    result = await session.execute(
        select(Expense)
        .join(Trip, Expense.trip_id == Trip.id)
        .where(Trip.vehicle_id == vehicle_id)
        .where(Expense.expense_type == ExpenseType.FUEL.value)
        .where(Expense.odometer_reading.isnot(None))
        .where(Expense.created_at < before_dt)
        .order_by(Expense.created_at.desc())
        .limit(1)
    )
    expense = result.scalars().first()
    return expense.odometer_reading if expense else None


async def count_fuel_expenses_for_vehicle(
    session: AsyncSession, vehicle_id: int, exclude_expense_id: int = None
) -> int:
    """Count FUEL expenses with odometer for a vehicle (used for minimum 2 fill-ups check)."""
    q = (
        select(sql_func.count())
        .select_from(Expense)
        .join(Trip, Expense.trip_id == Trip.id)
        .where(Trip.vehicle_id == vehicle_id)
        .where(Expense.expense_type == ExpenseType.FUEL.value)
        .where(Expense.odometer_reading.isnot(None))
    )
    if exclude_expense_id is not None:
        q = q.where(Expense.id != exclude_expense_id)
    result = await session.execute(q)
    return result.scalar() or 0


async def check_fuel_anomaly_after_expense(
    session: AsyncSession,
    expense: Expense,
    vehicle: Vehicle,
) -> FuelAnomaly | None:
    """
    Called after a FUEL expense is committed. Calculates actual consumption and
    creates a FuelAnomaly record if consumption exceeds norm by > 20%.
    Returns the FuelAnomaly if one was created, else None.

    Requirements:
    - ALERT-01: compute liters / km * 100
    - ALERT-02: threshold = norm * 1.20 (20% over norm)
    - ALERT-03: minimum 2 prior fill-ups required
    """
    if expense.expense_type != ExpenseType.FUEL.value:
        return None
    if vehicle.fuel_norm_per_100km is None:
        return None  # No norm configured for this vehicle
    if expense.liters is None or expense.odometer_reading is None:
        return None  # Missing data for calculation

    # ALERT-03: require at least 2 prior fill-ups
    prior_count = await count_fuel_expenses_for_vehicle(
        session, vehicle.id, exclude_expense_id=expense.id
    )
    if prior_count < 2:
        return None

    # ALERT-01: get previous odometer to compute km driven
    prev_odo = await get_last_fuel_odometer_before(session, vehicle.id, expense.created_at)
    if prev_odo is None:
        return None
    km_driven = expense.odometer_reading - prev_odo
    if km_driven <= 0:
        return None

    actual_per_100km = (expense.liters / km_driven) * 100

    # ALERT-02: check against threshold (norm + 20%)
    threshold = vehicle.fuel_norm_per_100km * 1.20
    if actual_per_100km <= threshold:
        return None

    excess_percent = (
        (actual_per_100km - vehicle.fuel_norm_per_100km) / vehicle.fuel_norm_per_100km
    ) * 100

    anomaly = FuelAnomaly(
        expense_id=expense.id,
        vehicle_id=vehicle.id,
        trip_id=expense.trip_id,
        actual_per_100km=actual_per_100km,
        norm_per_100km=vehicle.fuel_norm_per_100km,
        threshold_per_100km=threshold,
        excess_percent=excess_percent,
        is_false_alarm=False,
        notified=False,
    )
    session.add(anomaly)
    await session.commit()
    logger.info(
        f"Fuel anomaly created: vehicle {vehicle.id}, {actual_per_100km:.1f} l/100km "
        f"vs norm {vehicle.fuel_norm_per_100km:.1f} (+{excess_percent:.0f}%)"
    )
    return anomaly


async def run_anomaly_digest() -> None:
    """
    ALERT-04: Hourly APScheduler job — batch sends unnotified FuelAnomaly records
    to the director's Telegram chat. Marks them notified after successful send.
    """
    from src.main import ptb_app  # deferred import — avoids circular import
    from src.core.config import settings

    if ptb_app is None or not settings.DIRECTOR_TG_ID:
        return

    async with async_session() as session:
        result = await session.execute(
            select(FuelAnomaly)
            .where(FuelAnomaly.notified == False)
            .where(FuelAnomaly.is_false_alarm == False)
            .order_by(FuelAnomaly.created_at.asc())
        )
        anomalies = result.scalars().all()

        if not anomalies:
            return

        lines = [f"Аномалии расхода топлива ({len(anomalies)} новых):"]
        for a in anomalies:
            lines.append(
                f"- Борт {a.vehicle_id}, рейс {a.trip_id}: "
                f"{a.actual_per_100km:.1f} л/100км "
                f"(норма {a.norm_per_100km:.1f}, превышение +{a.excess_percent:.0f}%)"
            )
        message = "\n".join(lines)

        try:
            await ptb_app.bot.send_message(
                chat_id=settings.DIRECTOR_TG_ID,
                text=message,
            )
            for a in anomalies:
                a.notified = True
                session.add(a)
            await session.commit()
            logger.info(f"Anomaly digest sent: {len(anomalies)} anomalies")
        except Exception as e:
            logger.error(f"Failed to send anomaly digest to director: {e}")
