from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, Float, Enum, DateTime, Boolean, UniqueConstraint
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
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)

    trips = relationship("Trip", back_populates="driver")
    vehicle = relationship("Vehicle", back_populates="drivers")

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default=VehicleStatus.AVAILABLE)
    make = Column(String, nullable=True)
    model = Column(String, nullable=True)
    fuel_norm_per_100km = Column(Float, nullable=True)

    trips = relationship("Trip", back_populates="vehicle")
    drivers = relationship("Driver", back_populates="vehicle")

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

    closing_document_id = Column(String, nullable=True)

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
    currency = Column(String(3), default="RUB")
    photo_file_id = Column(String, nullable=True) # Receipt
    photo_r2_url = Column(String, nullable=True)  # R2 durable storage URL (replaces Telegram file_id for receipts)
    card_photo_file_id = Column(String, nullable=True) # Card/Terminal
    comment = Column(String, nullable=True)

    # Approval workflow (EAPPR-01, EAPPR-02)
    status = Column(String, default="PENDING", nullable=False)
    approved_by = Column(String, nullable=True)          # dispatcher username from JWT
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_comment = Column(String, nullable=True)

    # Fuel-specific fields (EXP-01, EXP-02)
    liters = Column(Float, nullable=True)
    odometer_reading = Column(Integer, nullable=True)
    station = Column(String, nullable=True)

    # Multi-currency normalization (EXP-07)
    fx_rate = Column(Float, nullable=True)               # rate to KZT at submission time
    amount_kzt = Column(Float, nullable=True)            # normalized amount in KZT

    # Idempotency (EXP-08)
    idempotency_minute = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            'trip_id', 'expense_type', 'amount', 'idempotency_minute',
            name='uq_expense_idempotent'
        ),
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip", back_populates="expenses")

class FuelAnomaly(Base):
    __tablename__ = "fuel_anomalies"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)

    actual_per_100km = Column(Float, nullable=False)
    norm_per_100km = Column(Float, nullable=False)
    threshold_per_100km = Column(Float, nullable=False)
    excess_percent = Column(Float, nullable=False)

    is_false_alarm = Column(Boolean, default=False, nullable=False)
    notified = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    expense = relationship("Expense")
    vehicle = relationship("Vehicle")
    trip = relationship("Trip")

class LocationUpdate(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True) # Optional, driver might be off trip

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    driver = relationship("Driver") # Basic relation for now
