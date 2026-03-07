import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.models import Driver, Vehicle

logger = logging.getLogger(__name__)

async def get_driver_by_tg_id(session: AsyncSession, tg_id: int) -> Driver | None:
    result = await session.execute(select(Driver).where(Driver.tg_id == tg_id))
    return result.scalars().first()

async def create_driver(session: AsyncSession, tg_id: int, name: str, phone: str = None) -> Driver:
    driver = Driver(tg_id=tg_id, name=name, phone=phone)
    session.add(driver)
    await session.commit()
    await session.refresh(driver)
    return driver

async def get_vehicle_by_plate(session: AsyncSession, license_plate: str) -> Vehicle | None:
    result = await session.execute(select(Vehicle).where(Vehicle.license_plate == license_plate))
    return result.scalars().first()

async def create_vehicle(session: AsyncSession, license_plate: str) -> Vehicle:
    vehicle = Vehicle(license_plate=license_plate)
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    return vehicle
