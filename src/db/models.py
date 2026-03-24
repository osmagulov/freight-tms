from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, Float, Enum, DateTime, Boolean, UniqueConstraint, Text, Date
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

class RepairStatus(str, enum.Enum):
    OPEN = "OPEN"           # Требует ремонта
    IN_PROGRESS = "IN_PROGRESS"  # В ремонте
    RESOLVED = "RESOLVED"   # Отремонтировано

class TripEventType(str, enum.Enum):
    BORDER_QUEUE_START = "BORDER_QUEUE_START" 
    BORDER_QUEUE_END = "BORDER_QUEUE_END"
    UNLOADING_START = "UNLOADING_START"
    UNLOADING_END = "UNLOADING_END"
    CUSTOMS_START = "CUSTOMS_START"
    CUSTOMS_END = "CUSTOMS_END"

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=True)  # NULL for dispatcher-created drivers
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    iin = Column(String(12), nullable=True)           # Individual Identification Number (Kazakhstan)
    passport_r2_url = Column(String, nullable=True)   # Passport scan on R2
    language = Column(String, default="ru", nullable=False)
    password_hash = Column(String, nullable=True)     # For PWA login
    fuel_card_number = Column(String, nullable=True)  # Saved fuel card number for auto-fill
    status = Column(String, default=DriverStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)

    trips = relationship("Trip", back_populates="driver", cascade="all, delete-orphan")
    vehicle = relationship("Vehicle", back_populates="drivers")
    documents = relationship("DriverDocument", back_populates="driver", cascade="all, delete-orphan", order_by="DriverDocument.uploaded_at.desc()")

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default=VehicleStatus.AVAILABLE)
    make = Column(String, nullable=True)
    model = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    fuel_norm_per_100km = Column(Float, nullable=True)

    # Predictive Maintenance
    maintenance_interval_km = Column(Integer, nullable=True, default=60000)
    last_maintenance_odometer = Column(Integer, nullable=True, default=0)

    trips = relationship("Trip", back_populates="vehicle", cascade="all, delete-orphan")
    drivers = relationship("Driver", back_populates="vehicle")
    repairs = relationship("VehicleRepair", back_populates="vehicle", cascade="all, delete-orphan", order_by="VehicleRepair.created_at.desc()")
    documents = relationship("VehicleDocument", back_populates="vehicle", cascade="all, delete-orphan", order_by="VehicleDocument.uploaded_at.desc()")

class VehicleRepair(Base):
    __tablename__ = "vehicle_repairs"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)  # If reported during a trip

    description = Column(Text, nullable=False)        # Что сломалось / что нужно починить
    status = Column(String, default=RepairStatus.OPEN, nullable=False)
    priority = Column(String, default="NORMAL")       # LOW / NORMAL / HIGH / CRITICAL

    reported_by = Column(String, nullable=True)       # dispatcher username or "driver"
    resolved_by = Column(String, nullable=True)
    resolution_notes = Column(Text, nullable=True)    # Что было сделано

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    vehicle = relationship("Vehicle", back_populates="repairs")
    trip = relationship("Trip")

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

    # Phase 3: Trip Management (TRIP-01, TRIP-04, TRIP-05)
    client_name = Column(String, nullable=True)
    planned_departure = Column(DateTime(timezone=True), nullable=True)
    planned_arrival = Column(DateTime(timezone=True), nullable=True)
    delivery_status = Column(String, nullable=True)

    # Financials (Analytics)
    price = Column(Float, nullable=True)             # Revenue / Rate from client
    price_currency = Column(String(3), default="KZT") # Currency for revenue

    driver = relationship("Driver", back_populates="trips")
    vehicle = relationship("Vehicle", back_populates="trips")
    expenses = relationship("Expense", back_populates="trip", cascade="all, delete-orphan")
    documents = relationship("TripDocument", back_populates="trip", cascade="all, delete-orphan")
    events = relationship("TripEvent", back_populates="trip", cascade="all, delete-orphan", order_by="TripEvent.created_at")

class TripEvent(Base):
    __tablename__ = "trip_events"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    event_type = Column(String, nullable=False)
    location_name = Column(String, nullable=True) # e.g. "Хоргос"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip", back_populates="events")

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


class DriverDocument(Base):
    __tablename__ = "driver_documents"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    doc_type = Column(String, nullable=False)   # driver_license | passport | medical | contract | other
    title = Column(String, nullable=True)       # Custom label (for "other" type)
    r2_url = Column(String, nullable=False)
    expires_at = Column(Date, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    driver = relationship("Driver", back_populates="documents")


class VehicleDocument(Base):
    __tablename__ = "vehicle_documents"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    doc_type = Column(String, nullable=False)   # registration | insurance | inspection | customs | other
    title = Column(String, nullable=True)
    r2_url = Column(String, nullable=False)
    expires_at = Column(Date, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="documents")


class TripDocument(Base):
    __tablename__ = "trip_documents"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)

    # Document classification and storage (TRIP-04, TRIP-05)
    file_type = Column(String, nullable=False)   # e.g. "waybill", "invoice", "cmr"
    r2_url = Column(String, nullable=True)       # Cloudflare R2 durable URL
    tg_file_id = Column(String, nullable=True)   # Telegram file_id for re-download

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip", back_populates="documents")
