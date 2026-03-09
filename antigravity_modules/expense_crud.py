import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from src.db.models import Trip, Expense, ExpenseType, FuelAnomaly, TripStatus, Vehicle, VehicleStatus

logger = logging.getLogger(__name__)

async def get_active_trip_for_driver(session: AsyncSession, driver_id: int) -> Trip | None:
    result = await session.execute(
        select(Trip)
        .where(Trip.driver_id == driver_id)
        .where(Trip.status == "ACTIVE")
    )
    return result.scalars().first()

async def get_last_fuel_odometer(session: AsyncSession, vehicle_id: int) -> int | None:
    """Return the odometer reading of the most recent FUEL expense for this vehicle."""
    result = await session.execute(
        select(Expense)
        .join(Trip, Expense.trip_id == Trip.id)
        .where(Trip.vehicle_id == vehicle_id)
        .where(Expense.expense_type == ExpenseType.FUEL.value)
        .where(Expense.odometer_reading.isnot(None))
        .order_by(Expense.created_at.desc())
        .limit(1)
    )
    expense = result.scalars().first()
    return expense.odometer_reading if expense else None

async def count_fuel_expenses_for_vehicle(
    session: AsyncSession, vehicle_id: int, exclude_expense_id: int = None
) -> int:
    """Count completed FUEL expenses for a vehicle (for anomaly detection minimum check)."""
    from sqlalchemy import func as sql_func
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

async def create_expense(
    session: AsyncSession,
    trip_id: int,
    expense_type: str,
    amount: float,
    currency: str = "KZT",
    photo_file_id: str = None,
    card_photo_file_id: str = None,
    comment: str = None,
    photo_r2_url: str = None,
    # Phase 2 new fields
    liters: float = None,
    odometer_reading: int = None,
    station: str = None,
    fx_rate: float = None,
    amount_kzt: float = None,
    idempotency_minute: datetime = None,
) -> Expense | None:
    """Create expense. Returns None if duplicate detected (idempotency constraint)."""
    if idempotency_minute is None:
        now = datetime.utcnow()
        idempotency_minute = now.replace(second=0, microsecond=0)

    expense = Expense(
        trip_id=trip_id,
        expense_type=expense_type,
        amount=amount,
        currency=currency,
        photo_file_id=photo_file_id,
        card_photo_file_id=card_photo_file_id,
        comment=comment,
        photo_r2_url=photo_r2_url,
        status="PENDING",
        liters=liters,
        odometer_reading=odometer_reading,
        station=station,
        fx_rate=fx_rate,
        amount_kzt=amount_kzt,
        idempotency_minute=idempotency_minute,
    )
    try:
        session.add(expense)
        await session.commit()
        await session.refresh(expense)
        return expense
    except IntegrityError:
        await session.rollback()
        return None  # Duplicate — caller shows "already submitted" message


async def get_planned_trip_for_driver(session: AsyncSession, driver_id: int) -> Trip | None:
    """Return the single PLANNED trip assigned to this driver, or None if none exists."""
    result = await session.execute(
        select(Trip)
        .where(Trip.driver_id == driver_id)
        .where(Trip.status == TripStatus.PLANNED.value)
        .order_by(Trip.created_at.asc())
        .limit(1)
    )
    return result.scalars().first()


async def activate_trip(session: AsyncSession, trip_id: int, start_odometer: int, vehicle_id: int) -> Trip | None:
    """
    Set trip status to ACTIVE and vehicle status to ON_TRIP atomically.
    Returns the updated Trip on success, None if trip not found.
    """
    trip_result = await session.execute(
        select(Trip).where(Trip.id == trip_id)
    )
    trip = trip_result.scalars().first()
    if not trip:
        return None

    vehicle_result = await session.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id)
    )
    vehicle = vehicle_result.scalars().first()

    trip.status = TripStatus.ACTIVE.value
    trip.start_odometer = start_odometer

    if vehicle:
        vehicle.status = VehicleStatus.ON_TRIP.value

    await session.commit()
    await session.refresh(trip)
    return trip
