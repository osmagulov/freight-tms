from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, Float, Enum, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from src.db.database import Base

class DriverStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class VehicleStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    ON_TRIP = "ON_TRIP"
    MAINTENANCE = "MAINTENANCE"

class TripStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class ExpenseType(str, enum.Enum):
    FUEL = "FUEL"
    PER_DIEM = "PER_DIEM"
    FINE = "FINE"
    REPAIR = "REPAIR"
    OTHER = "OTHER"

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    language = Column(String, default="ru", nullable=False)
    status = Column(String, default=DriverStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trips = relationship("Trip", back_populates="driver")

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default=VehicleStatus.AVAILABLE)
    
    trips = relationship("Trip", back_populates="vehicle")

class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    
    route_details = Column(String, nullable=True)
    load_info = Column(String, nullable=True)
    status = Column(String, default=TripStatus.PLANNED)
    
    start_odometer = Column(Integer, nullable=True)
    end_odometer = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    driver = relationship("Driver", back_populates="trips")
    vehicle = relationship("Vehicle", back_populates="trips")
    expenses = relationship("Expense", back_populates="trip")

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    expense_type = Column(String, nullable=False)
    
    amount = Column(Float, nullable=False)
    currency = Column(String, default="RUB")
    photo_file_id = Column(String, nullable=True)
    comment = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip", back_populates="expenses")
