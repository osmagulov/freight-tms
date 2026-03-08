import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.models import Trip, Expense, ExpenseType

logger = logging.getLogger(__name__)

async def get_active_trip_for_driver(session: AsyncSession, driver_id: int) -> Trip | None:
    result = await session.execute(
        select(Trip)
        .where(Trip.driver_id == driver_id)
        .where(Trip.status == "ACTIVE")
    )
    return result.scalars().first()

async def create_expense(
    session: AsyncSession,
    trip_id: int,
    expense_type: str,
    amount: float,
    currency: str = "RUB",
    photo_file_id: str = None,
    card_photo_file_id: str = None,
    comment: str = None,
    photo_r2_url: str = None,
) -> Expense:
    expense = Expense(
        trip_id=trip_id,
        expense_type=expense_type,
        amount=amount,
        currency=currency,
        photo_file_id=photo_file_id,
        photo_r2_url=photo_r2_url,
        card_photo_file_id=card_photo_file_id,
        comment=comment
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense
