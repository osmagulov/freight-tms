# src/web/panel.py
import logging
from pathlib import Path

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.orm import selectinload

from src.db.database import async_session
from src.db.models import Driver, DriverDocument, Expense, FuelAnomaly, LocationUpdate, RepairStatus, Trip, TripDocument, TripStatus, Vehicle, VehicleDocument, VehicleRepair, VehicleStatus
from src.services.r2 import save_uploaded_file
from datetime import date as date_type
from src.web.auth import (
    create_access_token,
    get_current_user_from_cookie,
    hash_password,
    verify_password,
)
from src.core.config import settings

logger = logging.getLogger(__name__)


async def notify_driver_expense_decision(expense: Expense, approved: bool, rejection_comment: str = None) -> None:
    """Send Telegram message to driver about expense approval or rejection."""
    from src.main import ptb_app  # deferred import — ptb_app is set at lifespan startup
    if ptb_app is None:
        return
    try:
        driver_tg_id = expense.trip.driver.tg_id
        if approved:
            text = f"Расход одобрен: {expense.expense_type} {expense.amount} {expense.currency}"
        else:
            text = f"Расход отклонен: {expense.expense_type} {expense.amount} {expense.currency}"
            if rejection_comment:
                text += f"\nПричина: {rejection_comment}"
        await ptb_app.bot.send_message(chat_id=driver_tg_id, text=text)
    except Exception as e:
        logger.error(f"Failed to notify driver: {e}")


async def notify_driver_trip_assignment(trip: Trip, open_repairs: list = None) -> None:
    """Send Telegram message to driver about new trip assignment."""
    from src.main import ptb_app  # deferred import — ptb_app is set at lifespan startup
    if ptb_app is None:
        return
    try:
        driver_tg_id = trip.driver.tg_id
        if not driver_tg_id:
            return  # dispatcher-created driver, no Telegram account
        text = (
            f"Вам назначен новый рейс #{trip.id}!\n"
            f"Маршрут: {trip.route_details or '—'}\n"
            f"Груз: {trip.load_info or '—'}\n"
            f"Клиент: {trip.client_name or '—'}"
        )
        if open_repairs:
            priority_labels = {"CRITICAL": "Критический", "HIGH": "Высокий", "NORMAL": "Нормальный", "LOW": "Низкий"}
            repairs_text = "\n".join(
                f"• {r.description} ({priority_labels.get(r.priority, r.priority)})"
                for r in open_repairs
            )
            text += f"\n\n⚠️ Внимание! На борту есть неисправности:\n{repairs_text}"
        await ptb_app.bot.send_message(chat_id=driver_tg_id, text=text)
    except Exception as e:
        logger.error(f"Failed to notify driver about trip assignment: {e}")



router = APIRouter(prefix="/panel", tags=["panel"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return RedirectResponse(url="/panel/drivers", status_code=302)


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(default="admin"),
    password: str = Form(default="admin"),
):
    return RedirectResponse(url="/panel/drivers", status_code=302)


@router.get("/logout")
async def logout():
    return RedirectResponse(url="/panel/drivers", status_code=302)


@router.get("/drivers", response_class=HTMLResponse)
async def list_drivers(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(Driver, Vehicle)
            .outerjoin(Vehicle, Driver.vehicle_id == Vehicle.id)
            .order_by(Driver.created_at.desc())
        )
        rows = result.all()  # List of (Driver, Vehicle|None) tuples
    return templates.TemplateResponse(
        "drivers.html",
        {"request": request, "rows": rows, "user": current_user},
    )


@router.post("/drivers/{driver_id}/activate")
async def activate_driver(
    driver_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        if driver and driver.status != "ACTIVE":
            driver.status = "ACTIVE"
            session.add(driver)
            await session.commit()
    return RedirectResponse(url="/panel/drivers", status_code=302)


@router.get("/vehicles/{vehicle_id}/edit", response_class=HTMLResponse)
async def vehicle_edit_form(
    request: Request,
    vehicle_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
        vehicle = result.scalars().first()
    if not vehicle:
        return RedirectResponse(url="/panel/drivers", status_code=302)
    return templates.TemplateResponse(
        "vehicle_edit.html",
        {"request": request, "vehicle": vehicle, "user": current_user},
    )


@router.post("/vehicles/{vehicle_id}/edit")
async def vehicle_edit_submit(
    request: Request,
    vehicle_id: int,
    make: str = Form(default=""),
    model: str = Form(default=""),
    year: str = Form(default=""),
    fuel_norm_per_100km: str = Form(default=""),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
        vehicle = result.scalars().first()
        if vehicle:
            vehicle.make = make.strip() or None
            vehicle.model = model.strip() or None
            vehicle.year = int(year) if year.strip() else None
            vehicle.fuel_norm_per_100km = float(fuel_norm_per_100km) if fuel_norm_per_100km.strip() else None
            session.add(vehicle)
            await session.commit()
    return RedirectResponse(url="/panel/drivers", status_code=302)


@router.get("/expenses", response_class=HTMLResponse)
async def list_expenses(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(Expense)
            .join(Trip, Expense.trip_id == Trip.id)
            .join(Driver, Trip.driver_id == Driver.id)
            .where(Expense.status == "PENDING")
            .order_by(Expense.created_at.desc())
            .options(
                selectinload(Expense.trip).selectinload(Trip.driver)
            )
        )
        expenses = result.scalars().all()
    return templates.TemplateResponse(
        "expenses.html",
        {"request": request, "expenses": expenses, "user": current_user},
    )


@router.post("/expenses/{expense_id}/approve", response_class=HTMLResponse)
async def approve_expense(
    request: Request,
    expense_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(Expense)
            .where(Expense.id == expense_id)
            .options(selectinload(Expense.trip).selectinload(Trip.driver))
        )
        expense = result.scalars().first()
        if expense:
            expense.status = "APPROVED"
            expense.approved_by = current_user.get("sub", "dispatcher")
            expense.approved_at = datetime.utcnow()
            session.add(expense)
            await session.commit()
            await session.refresh(expense)
    await notify_driver_expense_decision(expense, approved=True)
    return templates.TemplateResponse(
        "expense_row.html",
        {"request": request, "expense": expense},
    )


@router.post("/expenses/{expense_id}/reject", response_class=HTMLResponse)
async def reject_expense(
    request: Request,
    expense_id: int,
    comment: str = Form(default=""),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(Expense)
            .where(Expense.id == expense_id)
            .options(selectinload(Expense.trip).selectinload(Trip.driver))
        )
        expense = result.scalars().first()
        if expense:
            expense.status = "REJECTED"
            expense.rejection_comment = comment or None
            expense.approved_by = current_user.get("sub", "dispatcher")
            expense.approved_at = datetime.utcnow()
            session.add(expense)
            await session.commit()
            await session.refresh(expense)
    await notify_driver_expense_decision(expense, approved=False, rejection_comment=comment)
    return templates.TemplateResponse(
        "expense_row.html",
        {"request": request, "expense": expense},
    )


@router.get("/anomalies", response_class=HTMLResponse)
async def list_anomalies(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(FuelAnomaly)
            .where(FuelAnomaly.is_false_alarm == False)
            .order_by(FuelAnomaly.created_at.desc())
        )
        anomalies = result.scalars().all()
    return templates.TemplateResponse(
        "anomalies.html",
        {"request": request, "anomalies": anomalies, "user": current_user},
    )


@router.post("/anomalies/{anomaly_id}/dismiss", response_class=HTMLResponse)
async def dismiss_anomaly(
    request: Request,
    anomaly_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(FuelAnomaly).where(FuelAnomaly.id == anomaly_id)
        )
        anomaly = result.scalars().first()
        if anomaly:
            anomaly.is_false_alarm = True
            session.add(anomaly)
            await session.commit()
            await session.refresh(anomaly)
    # Return a replacement row showing "false alarm" state
    dismissed_row = f'<tr id="anomaly-{anomaly_id}"><td colspan="7"><em>Отмечена как ложная тревога</em></td></tr>'
    return HTMLResponse(content=dismissed_row)


@router.get("/trips", response_class=HTMLResponse)
async def list_trips(
    request: Request,
    driver_id: int | None = None,
    vehicle_id: int | None = None,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        stmt = (
            select(Trip)
            .options(selectinload(Trip.driver), selectinload(Trip.vehicle))
            .order_by(Trip.created_at.desc())
        )
        if driver_id is not None:
            stmt = stmt.where(Trip.driver_id == driver_id)
        if vehicle_id is not None:
            stmt = stmt.where(Trip.vehicle_id == vehicle_id)
        result = await session.execute(stmt)
        trips = result.scalars().all()

        drivers_result = await session.execute(
            select(Driver).order_by(Driver.name)
        )
        drivers = drivers_result.scalars().all()

        vehicles_result = await session.execute(
            select(Vehicle).order_by(Vehicle.license_plate)
        )
        vehicles = vehicles_result.scalars().all()

    return templates.TemplateResponse(
        "trips_list.html",
        {
            "request": request,
            "trips": trips,
            "drivers": drivers,
            "vehicles": vehicles,
            "filter_driver_id": driver_id,
            "filter_vehicle_id": vehicle_id,
            "user": current_user,
        },
    )


@router.get("/trips/create", response_class=HTMLResponse)
async def create_trip_form(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        drivers_result = await session.execute(
            select(Driver).order_by(Driver.name)
        )
        drivers = drivers_result.scalars().all()

        vehicles_result = await session.execute(
            select(Vehicle).order_by(Vehicle.license_plate)
        )
        vehicles = vehicles_result.scalars().all()

    return templates.TemplateResponse(
        "trips_create.html",
        {
            "request": request,
            "drivers": drivers,
            "vehicles": vehicles,
            "TripStatus": TripStatus,
            "user": current_user
        },
    )


@router.post("/trips/create")
async def create_trip_submit(
    request: Request,
    driver_id: int = Form(),
    vehicle_id: int = Form(),
    status: str = Form(default="PLANNED"),
    route_details: str = Form(default=""),
    load_info: str = Form(default=""),
    client_name: str = Form(default=""),
    planned_departure: str = Form(default=""),
    planned_arrival: str = Form(default=""),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    from datetime import datetime as dt

    def parse_dt(value: str):
        if not value:
            return None
        try:
            return dt.fromisoformat(value)
        except ValueError:
            return None

    async with async_session() as session:
        trip = Trip(
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            route_details=route_details or None,
            load_info=load_info or None,
            client_name=client_name or None,
            planned_departure=parse_dt(planned_departure),
            planned_arrival=parse_dt(planned_arrival),
            status=status,
        )
        session.add(trip)
        await session.commit()
        await session.refresh(trip)
        # Eager-load driver for notification
        result = await session.execute(
            select(Trip)
            .where(Trip.id == trip.id)
            .options(selectinload(Trip.driver), selectinload(Trip.vehicle))
        )
        trip = result.scalars().first()

        # Load open repairs for this vehicle to include in notification
        repairs_result = await session.execute(
            select(VehicleRepair)
            .where(VehicleRepair.vehicle_id == vehicle_id)
            .where(VehicleRepair.status.in_([RepairStatus.OPEN, RepairStatus.IN_PROGRESS]))
            .order_by(VehicleRepair.created_at.desc())
        )
        open_repairs = repairs_result.scalars().all()

    await notify_driver_trip_assignment(trip, open_repairs=open_repairs)
    return RedirectResponse(url=f"/panel/trips/{trip.id}", status_code=302)


@router.get("/trips/{trip_id}", response_class=HTMLResponse)
async def trip_detail(
    request: Request,
    trip_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(Trip)
            .where(Trip.id == trip_id)
            .options(
                selectinload(Trip.driver),
                selectinload(Trip.vehicle),
                selectinload(Trip.expenses),
                selectinload(Trip.documents),
            )
        )
        trip = result.scalars().first()
        if not trip:
            return RedirectResponse(url="/panel/trips", status_code=302)

        # Load location pings for this trip
        locations_result = await session.execute(
            select(LocationUpdate)
            .where(LocationUpdate.trip_id == trip_id)
            .order_by(LocationUpdate.created_at.desc())
        )
        locations = locations_result.scalars().all()

        # Load open/in-progress repairs for this vehicle
        repairs_result = await session.execute(
            select(VehicleRepair)
            .where(VehicleRepair.vehicle_id == trip.vehicle_id)
            .where(VehicleRepair.status.in_([RepairStatus.OPEN, RepairStatus.IN_PROGRESS]))
            .order_by(VehicleRepair.created_at.desc())
        )
        open_repairs = repairs_result.scalars().all()

    # Calculate total expenses in KZT
    total_kzt = sum(
        (e.amount_kzt if e.amount_kzt is not None else e.amount)
        for e in trip.expenses
    )

    return templates.TemplateResponse(
        "trip_detail.html",
        {
            "request": request,
            "trip": trip,
            "locations": locations,
            "total_kzt": total_kzt,
            "open_repairs": open_repairs,
            "user": current_user,
        },
    )


@router.get("/trips/{trip_id}/edit", response_class=HTMLResponse)
async def trip_edit_form(
    request: Request,
    trip_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(Trip).where(Trip.id == trip_id)
        )
        trip = result.scalars().first()
        if not trip:
            return RedirectResponse(url="/panel/trips", status_code=302)

        drivers_result = await session.execute(
            select(Driver).order_by(Driver.name)
        )
        drivers = drivers_result.scalars().all()

        vehicles_result = await session.execute(
            select(Vehicle).order_by(Vehicle.license_plate)
        )
        vehicles = vehicles_result.scalars().all()

    return templates.TemplateResponse(
        "trip_edit.html",
        {
            "request": request,
            "trip": trip,
            "drivers": drivers,
            "vehicles": vehicles,
            "TripStatus": TripStatus,
            "user": current_user,
        },
    )


@router.post("/trips/{trip_id}/edit")
async def trip_edit_submit(
    request: Request,
    trip_id: int,
    driver_id: int = Form(),
    vehicle_id: int = Form(),
    status: str = Form(),
    delivery_status: str = Form(default=""),
    route_details: str = Form(default=""),
    load_info: str = Form(default=""),
    client_name: str = Form(default=""),
    planned_departure: str = Form(default=""),
    planned_arrival: str = Form(default=""),
    start_odometer: str = Form(default=""),
    end_odometer: str = Form(default=""),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    from datetime import datetime as dt

    def parse_dt(value: str):
        if not value:
            return None
        try:
            return dt.fromisoformat(value)
        except ValueError:
            return None

    def parse_int(value: str):
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async with async_session() as session:
        result = await session.execute(select(Trip).where(Trip.id == trip_id))
        trip = result.scalars().first()
        if not trip:
            return RedirectResponse(url="/panel/trips", status_code=302)

        trip.driver_id = driver_id
        trip.vehicle_id = vehicle_id
        trip.status = status
        trip.delivery_status = delivery_status.strip() or None
        trip.route_details = route_details.strip() or None
        trip.load_info = load_info.strip() or None
        trip.client_name = client_name.strip() or None
        trip.planned_departure = parse_dt(planned_departure)
        trip.planned_arrival = parse_dt(planned_arrival)
        trip.start_odometer = parse_int(start_odometer)
        trip.end_odometer = parse_int(end_odometer)

        session.add(trip)
        await session.commit()

    return RedirectResponse(url=f"/panel/trips/{trip.id}", status_code=302)


@router.get("/trips/{trip_id}/expenses/add", response_class=HTMLResponse)
async def add_trip_expense_form(
    request: Request,
    trip_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    from src.db.models import ExpenseType
    async with async_session() as session:
        result = await session.execute(select(Trip).where(Trip.id == trip_id))
        trip = result.scalars().first()
        if not trip:
            return RedirectResponse(url="/panel/trips", status_code=302)

    return templates.TemplateResponse(
        "expense_add.html",
        {
            "request": request,
            "trip": trip,
            "ExpenseType": ExpenseType,
            "user": current_user,
        },
    )


@router.post("/trips/{trip_id}/expenses/add")
async def add_trip_expense_submit(
    request: Request,
    trip_id: int,
    expense_type: str = Form(),
    amount: float = Form(),
    currency: str = Form(),
    status: str = Form(),
    comment: str = Form(default=""),
    liters: float = Form(default=None),
    odometer_reading: int = Form(default=None),
    station: str = Form(default=""),
    receipt_file: UploadFile = File(default=None),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    import uuid
    # Static FX rates to KZT
    FX_RATES: dict[str, float] = {
        "KZT": 1.0,
        "RUB": 5.2,
        "USD": 450.0,
        "EUR": 490.0,
        "TRY": 13.5,
        "CNY": 65.0,
    }
    fx_rate = FX_RATES.get(currency, 1.0)
    amount_kzt = round(amount * fx_rate, 2)

    receipt_url = None
    if receipt_file and receipt_file.filename:
        file_bytes = await receipt_file.read()
        if file_bytes:
            ext = receipt_file.filename.split('.')[-1] if '.' in receipt_file.filename else 'jpg'
            key = f"expenses/receipt_{uuid.uuid4()}.{ext}"
            content_type = receipt_file.content_type or "image/jpeg"
            receipt_url = await save_uploaded_file(file_bytes, key, content_type)

    async with async_session() as session:
        result = await session.execute(select(Trip).where(Trip.id == trip_id))
        trip = result.scalars().first()
        if not trip:
            return RedirectResponse(url="/panel/trips", status_code=302)

        expense = Expense(
            trip_id=trip.id,
            expense_type=expense_type,
            amount=amount,
            currency=currency,
            fx_rate=fx_rate,
            amount_kzt=amount_kzt,
            comment=comment.strip() or None,
            photo_r2_url=receipt_url,
            status=status,
        )
        if expense_type == "FUEL":
            expense.liters = liters
            expense.odometer_reading = odometer_reading
            expense.station = station.strip() or None

        if status == "APPROVED":
            expense.approved_by = current_user.get("sub", "dispatcher")
            expense.approved_at = datetime.utcnow()

        session.add(expense)
        await session.commit()

    return RedirectResponse(url=f"/panel/trips/{trip.id}", status_code=302)


@router.post("/trips/{trip_id}/documents")
async def add_trip_document(
    request: Request,
    trip_id: int,
    file_type: str = Form(...),
    doc_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    import uuid
    async with async_session() as session:
        result = await session.execute(select(Trip).where(Trip.id == trip_id))
        trip = result.scalars().first()
        if not trip or not doc_file.filename:
            return RedirectResponse(url=f"/panel/trips/{trip_id}", status_code=302)

        file_bytes = await doc_file.read()
        ext = doc_file.filename.rsplit(".", 1)[-1].lower() if "." in doc_file.filename else "pdf"
        content_type = "application/pdf" if ext == "pdf" else "image/jpeg"
        key = f"trip_docs/{trip_id}/{uuid.uuid4()}.{ext}"
        r2_url = await save_uploaded_file(file_bytes, key, content_type)

        doc = TripDocument(
            trip_id=trip_id,
            file_type=file_type,
            r2_url=r2_url,
        )
        session.add(doc)
        await session.commit()
    return RedirectResponse(url=f"/panel/trips/{trip_id}", status_code=302)


@router.get("/fleet", response_class=HTMLResponse)
async def fleet_dashboard(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        vehicles_result = await session.execute(
            select(Vehicle)
            .options(
                selectinload(Vehicle.trips).selectinload(Trip.driver),
                selectinload(Vehicle.drivers),
                selectinload(Vehicle.repairs),
            )
            .order_by(Vehicle.license_plate)
        )
        vehicles = vehicles_result.scalars().all()

    # For each vehicle, find active trip and open repair count — Python-side filter
    vehicle_data = []
    for vehicle in vehicles:
        active_trip = next(
            (t for t in vehicle.trips if t.status == TripStatus.ACTIVE),
            None,
        )
        open_repairs = sum(
            1 for r in vehicle.repairs
            if r.status in (RepairStatus.OPEN, RepairStatus.IN_PROGRESS)
        )
        vehicle_data.append({"vehicle": vehicle, "active_trip": active_trip, "open_repairs": open_repairs})

    return templates.TemplateResponse(
        "fleet.html",
        {
            "request": request,
            "vehicle_data": vehicle_data,
            "VehicleStatus": VehicleStatus,
            "user": current_user,
        },
    )


async def _get_fleet_markers(session) -> list[dict]:
    """Return latest location for each driver with an active trip."""
    active_trips_result = await session.execute(
        select(Trip)
        .where(Trip.status == TripStatus.ACTIVE)
        .options(selectinload(Trip.driver), selectinload(Trip.vehicle))
    )
    active_trips = active_trips_result.scalars().all()

    if not active_trips:
        return []

    driver_ids = [t.driver_id for t in active_trips]

    # Latest LocationUpdate per driver
    subq = (
        select(
            LocationUpdate.driver_id,
            func.max(LocationUpdate.created_at).label("max_ts"),
        )
        .where(LocationUpdate.driver_id.in_(driver_ids))
        .group_by(LocationUpdate.driver_id)
        .subquery()
    )
    locs_result = await session.execute(
        select(LocationUpdate).join(
            subq,
            (LocationUpdate.driver_id == subq.c.driver_id)
            & (LocationUpdate.created_at == subq.c.max_ts),
        )
    )
    latest_locations = {loc.driver_id: loc for loc in locs_result.scalars().all()}

    markers = []
    for trip in active_trips:
        loc = latest_locations.get(trip.driver_id)
        if loc:
            markers.append(
                {
                    "lat": loc.latitude,
                    "lng": loc.longitude,
                    "driver_name": trip.driver.name or "—",
                    "plate": trip.vehicle.license_plate,
                    "updated_at": loc.created_at.strftime("%d.%m %H:%M")
                    if loc.created_at
                    else "—",
                }
            )
    return markers


@router.get("/map", response_class=HTMLResponse)
async def fleet_map(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        markers = await _get_fleet_markers(session)
    return templates.TemplateResponse(
        "map.html",
        {"request": request, "markers": markers, "user": current_user},
    )


@router.get("/map/markers")
async def fleet_map_markers(
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        markers = await _get_fleet_markers(session)
    return JSONResponse(content=markers)


# ── Vehicle Add ────────────────────────────────────────────────────────────

@router.get("/vehicles/add", response_class=HTMLResponse)
async def vehicle_add_form(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    return templates.TemplateResponse(
        "vehicle_add.html",
        {"request": request, "user": current_user},
    )


@router.post("/vehicles/add")
async def vehicle_add_submit(
    request: Request,
    license_plate: str = Form(),
    make: str = Form(default=""),
    model: str = Form(default=""),
    year: str = Form(default=""),
    fuel_norm_per_100km: str = Form(default=""),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    plate = license_plate.upper().strip()
    async with async_session() as session:
        existing = await session.execute(select(Vehicle).where(Vehicle.license_plate == plate))
        if existing.scalars().first():
            return templates.TemplateResponse(
                "vehicle_add.html",
                {"request": request, "user": current_user, "error": f"Борт {plate} уже существует"},
                status_code=400,
            )
        vehicle = Vehicle(
            license_plate=plate,
            make=make.strip() or None,
            model=model.strip() or None,
            year=int(year) if year.strip() else None,
            fuel_norm_per_100km=float(fuel_norm_per_100km) if fuel_norm_per_100km.strip() else None,
        )
        session.add(vehicle)
        await session.commit()
    return RedirectResponse(url="/panel/fleet", status_code=302)


# ── Driver Add ─────────────────────────────────────────────────────────────

@router.get("/drivers/add", response_class=HTMLResponse)
async def driver_add_form(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        vehicles_result = await session.execute(select(Vehicle).order_by(Vehicle.license_plate))
        vehicles = vehicles_result.scalars().all()
    return templates.TemplateResponse(
        "driver_add.html",
        {"request": request, "vehicles": vehicles, "user": current_user},
    )


@router.post("/drivers/add")
async def driver_add_submit(
    request: Request,
    name: str = Form(),
    phone: str = Form(default=""),
    iin: str = Form(default=""),
    vehicle_id: str = Form(default=""),
    password: str = Form(default=""),
    passport_file: UploadFile = File(default=None),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    passport_url = None
    if passport_file and passport_file.filename:
        file_bytes = await passport_file.read()
        if file_bytes:
            ext = passport_file.filename.rsplit(".", 1)[-1].lower()
            content_type = "application/pdf" if ext == "pdf" else "image/jpeg"
            key = f"passports/driver_{int(datetime.utcnow().timestamp())}_{passport_file.filename}"
            passport_url = await save_uploaded_file(file_bytes, key, content_type)

    vid = int(vehicle_id) if vehicle_id.strip() else None
    async with async_session() as session:
        driver = Driver(
            tg_id=None,
            name=name.strip(),
            phone=phone.strip() or None,
            iin=iin.strip() or None,
            passport_r2_url=passport_url,
            vehicle_id=vid,
            password_hash=hash_password(password) if password else None,
            status="ACTIVE",
        )
        session.add(driver)
        await session.commit()
    return RedirectResponse(url="/panel/drivers", status_code=302)


# ── Driver Edit ────────────────────────────────────────────────────────────

@router.get("/drivers/{driver_id}/edit", response_class=HTMLResponse)
async def driver_edit_form(
    request: Request,
    driver_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        if not driver:
            return RedirectResponse(url="/panel/drivers", status_code=302)
        vehicles_result = await session.execute(select(Vehicle).order_by(Vehicle.license_plate))
        vehicles = vehicles_result.scalars().all()
    return templates.TemplateResponse(
        "driver_edit.html",
        {"request": request, "driver": driver, "vehicles": vehicles, "user": current_user},
    )


@router.post("/drivers/{driver_id}/edit")
async def driver_edit_submit(
    request: Request,
    driver_id: int,
    name: str = Form(default=""),
    phone: str = Form(default=""),
    iin: str = Form(default=""),
    vehicle_id: str = Form(default=""),
    password: str = Form(default=""),
    passport_file: UploadFile = File(default=None),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        if not driver:
            return RedirectResponse(url="/panel/drivers", status_code=302)

        if name.strip():
            driver.name = name.strip()
        if phone.strip():
            driver.phone = phone.strip()
        if iin.strip():
            driver.iin = iin.strip()
        if password.strip():
            driver.password_hash = hash_password(password)
        driver.vehicle_id = int(vehicle_id) if vehicle_id.strip() else None

        if passport_file and passport_file.filename:
            file_bytes = await passport_file.read()
            if file_bytes:
                ext = passport_file.filename.rsplit(".", 1)[-1].lower()
                content_type = "application/pdf" if ext == "pdf" else "image/jpeg"
                key = f"passports/driver_{driver_id}_{int(datetime.utcnow().timestamp())}.{ext}"
                driver.passport_r2_url = await save_uploaded_file(file_bytes, key, content_type)

        session.add(driver)
        await session.commit()
    return RedirectResponse(url="/panel/drivers", status_code=302)


# ── Repairs ────────────────────────────────────────────────────────────────

@router.get("/repairs", response_class=HTMLResponse)
async def list_repairs(
    request: Request,
    vehicle_id: int | None = None,
    status: str | None = None,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        stmt = (
            select(VehicleRepair)
            .options(
                selectinload(VehicleRepair.vehicle),
                selectinload(VehicleRepair.trip),
            )
            .order_by(VehicleRepair.created_at.desc())
        )
        if vehicle_id:
            stmt = stmt.where(VehicleRepair.vehicle_id == vehicle_id)
        if status:
            stmt = stmt.where(VehicleRepair.status == status)
        result = await session.execute(stmt)
        repairs = result.scalars().all()

        vehicles_result = await session.execute(select(Vehicle).order_by(Vehicle.license_plate))
        vehicles = vehicles_result.scalars().all()

    open_count = sum(1 for r in repairs if r.status == RepairStatus.OPEN)
    in_progress_count = sum(1 for r in repairs if r.status == RepairStatus.IN_PROGRESS)

    return templates.TemplateResponse(
        "repairs.html",
        {
            "request": request,
            "repairs": repairs,
            "vehicles": vehicles,
            "open_count": open_count,
            "in_progress_count": in_progress_count,
            "filter_vehicle_id": vehicle_id,
            "filter_status": status,
            "user": current_user,
            "RepairStatus": RepairStatus,
        },
    )


@router.post("/repairs")
async def create_repair(
    request: Request,
    vehicle_id: int = Form(),
    description: str = Form(),
    priority: str = Form(default="NORMAL"),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        repair = VehicleRepair(
            vehicle_id=vehicle_id,
            description=description.strip(),
            priority=priority,
            status=RepairStatus.OPEN,
            reported_by=current_user.get("sub", "dispatcher"),
        )
        session.add(repair)
        await session.commit()
    return RedirectResponse(url="/panel/repairs", status_code=302)


@router.post("/repairs/{repair_id}/start")
async def repair_start(
    repair_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(VehicleRepair).where(VehicleRepair.id == repair_id))
        repair = result.scalars().first()
        if repair and repair.status == RepairStatus.OPEN:
            repair.status = RepairStatus.IN_PROGRESS
            session.add(repair)
            await session.commit()
    return RedirectResponse(url="/panel/repairs", status_code=302)


@router.get("/repairs/{repair_id}/act", response_class=HTMLResponse)
async def repair_act(
    request: Request,
    repair_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    """Generate a printable breakdown act for a repair."""
    async with async_session() as session:
        result = await session.execute(
            select(VehicleRepair)
            .where(VehicleRepair.id == repair_id)
            .options(selectinload(VehicleRepair.vehicle))
        )
        repair = result.scalars().first()
        if not repair:
            raise HTTPException(status_code=404, detail="Repair not found")

    return templates.TemplateResponse(
        "repair_act.html",
        {"request": request, "repair": repair, "user": current_user},
    )


@router.post("/repairs/{repair_id}/resolve")
async def repair_resolve(
    repair_id: int,
    resolution_notes: str = Form(default=""),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(VehicleRepair).where(VehicleRepair.id == repair_id))
        repair = result.scalars().first()
        if repair and repair.status != RepairStatus.RESOLVED:
            repair.status = RepairStatus.RESOLVED
            repair.resolved_by = current_user.get("sub", "dispatcher")
            repair.resolution_notes = resolution_notes.strip() or None
            repair.resolved_at = datetime.utcnow()
            session.add(repair)
            await session.commit()
    return RedirectResponse(url="/panel/repairs", status_code=302)


# ── Document expiry helper ────────────────────────────────────────────────────

def doc_expiry_status(expires_at) -> str:
    if not expires_at:
        return "ok"
    days = (expires_at - date_type.today()).days
    if days < 0:
        return "expired"
    if days <= 7:
        return "critical"
    if days <= 30:
        return "warning"
    return "ok"


DRIVER_DOC_LABELS = {
    "driver_license": "Водительское удостоверение",
    "passport": "Паспорт",
    "medical": "Медицинская справка",
    "contract": "Трудовой договор",
    "other": "Другой документ",
}

VEHICLE_DOC_LABELS = {
    "registration": "Техпаспорт",
    "insurance": "Страховой полис",
    "inspection": "Техосмотр",
    "customs": "Таможенные документы",
    "other": "Другой документ",
}


# ── Driver Documents ──────────────────────────────────────────────────────────

@router.get("/drivers/{driver_id}/documents", response_class=HTMLResponse)
async def driver_documents_get(
    request: Request,
    driver_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        docs_result = await session.execute(
            select(DriverDocument).where(DriverDocument.driver_id == driver_id)
            .order_by(DriverDocument.uploaded_at.desc())
        )
        docs = docs_result.scalars().all()
    return templates.TemplateResponse("driver_documents.html", {
        "request": request,
        "driver": driver,
        "docs": docs,
        "doc_expiry_status": doc_expiry_status,
        "DRIVER_DOC_LABELS": DRIVER_DOC_LABELS,
    })


@router.post("/drivers/{driver_id}/documents")
async def driver_documents_post(
    request: Request,
    driver_id: int,
    doc_type: str = Form(...),
    title: str = Form(""),
    expires_at: str = Form(""),
    doc_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    import uuid
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        if not driver or not doc_file.filename:
            return RedirectResponse(url=f"/panel/drivers/{driver_id}/documents", status_code=302)

        file_bytes = await doc_file.read()
        ext = doc_file.filename.rsplit(".", 1)[-1].lower() if "." in doc_file.filename else "pdf"
        content_type = "application/pdf" if ext == "pdf" else "image/jpeg"
        key = f"driver_docs/{driver_id}/{uuid.uuid4()}.{ext}"
        r2_url = await save_uploaded_file(file_bytes, key, content_type)

        expires = None
        if expires_at.strip():
            try:
                from datetime import date as dt_date
                expires = dt_date.fromisoformat(expires_at.strip())
            except ValueError:
                pass

        doc = DriverDocument(
            driver_id=driver_id,
            doc_type=doc_type,
            title=title.strip() or None,
            r2_url=r2_url,
            expires_at=expires,
        )
        session.add(doc)
        await session.commit()
    return RedirectResponse(url=f"/panel/drivers/{driver_id}/documents", status_code=302)


@router.post("/drivers/{driver_id}/documents/{doc_id}/delete")
async def driver_document_delete(
    request: Request,
    driver_id: int,
    doc_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(DriverDocument).where(DriverDocument.id == doc_id, DriverDocument.driver_id == driver_id)
        )
        doc = result.scalars().first()
        if doc:
            await session.delete(doc)
            await session.commit()
    return RedirectResponse(url=f"/panel/drivers/{driver_id}/documents", status_code=302)


# ── Vehicle Documents ─────────────────────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}/documents", response_class=HTMLResponse)
async def vehicle_documents_get(
    request: Request,
    vehicle_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
        vehicle = result.scalars().first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        docs_result = await session.execute(
            select(VehicleDocument).where(VehicleDocument.vehicle_id == vehicle_id)
            .order_by(VehicleDocument.uploaded_at.desc())
        )
        docs = docs_result.scalars().all()
    return templates.TemplateResponse("vehicle_documents.html", {
        "request": request,
        "vehicle": vehicle,
        "docs": docs,
        "doc_expiry_status": doc_expiry_status,
        "VEHICLE_DOC_LABELS": VEHICLE_DOC_LABELS,
    })


@router.post("/vehicles/{vehicle_id}/documents")
async def vehicle_documents_post(
    request: Request,
    vehicle_id: int,
    doc_type: str = Form(...),
    title: str = Form(""),
    expires_at: str = Form(""),
    doc_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    import uuid
    async with async_session() as session:
        result = await session.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
        vehicle = result.scalars().first()
        if not vehicle or not doc_file.filename:
            return RedirectResponse(url=f"/panel/vehicles/{vehicle_id}/documents", status_code=302)

        file_bytes = await doc_file.read()
        ext = doc_file.filename.rsplit(".", 1)[-1].lower() if "." in doc_file.filename else "pdf"
        content_type = "application/pdf" if ext == "pdf" else "image/jpeg"
        key = f"vehicle_docs/{vehicle_id}/{uuid.uuid4()}.{ext}"
        r2_url = await save_uploaded_file(file_bytes, key, content_type)

        expires = None
        if expires_at.strip():
            try:
                from datetime import date as dt_date
                expires = dt_date.fromisoformat(expires_at.strip())
            except ValueError:
                pass

        doc = VehicleDocument(
            vehicle_id=vehicle_id,
            doc_type=doc_type,
            title=title.strip() or None,
            r2_url=r2_url,
            expires_at=expires,
        )
        session.add(doc)
        await session.commit()
    return RedirectResponse(url=f"/panel/vehicles/{vehicle_id}/documents", status_code=302)


@router.post("/vehicles/{vehicle_id}/documents/{doc_id}/delete")
async def vehicle_document_delete(
    request: Request,
    vehicle_id: int,
    doc_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(VehicleDocument).where(VehicleDocument.id == doc_id, VehicleDocument.vehicle_id == vehicle_id)
        )
        doc = result.scalars().first()
        if doc:
            await session.delete(doc)
            await session.commit()
    return RedirectResponse(url=f"/panel/vehicles/{vehicle_id}/documents", status_code=302)


# ── Expiring Documents Dashboard ──────────────────────────────────────────────

@router.get("/documents/expiring", response_class=HTMLResponse)
async def documents_expiring(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    from datetime import timedelta
    today = date_type.today()
    deadline = today + timedelta(days=30)

    async with async_session() as session:
        driver_docs_res = await session.execute(
            select(DriverDocument, Driver)
            .join(Driver, DriverDocument.driver_id == Driver.id)
            .where(DriverDocument.expires_at != None)
            .where(DriverDocument.expires_at <= deadline)
            .order_by(DriverDocument.expires_at)
        )
        driver_docs = driver_docs_res.all()

        vehicle_docs_res = await session.execute(
            select(VehicleDocument, Vehicle)
            .join(Vehicle, VehicleDocument.vehicle_id == Vehicle.id)
            .where(VehicleDocument.expires_at != None)
            .where(VehicleDocument.expires_at <= deadline)
            .order_by(VehicleDocument.expires_at)
        )
        vehicle_docs = vehicle_docs_res.all()

    return templates.TemplateResponse("documents_expiring.html", {
        "request": request,
        "driver_docs": driver_docs,
        "vehicle_docs": vehicle_docs,
        "doc_expiry_status": doc_expiry_status,
        "DRIVER_DOC_LABELS": DRIVER_DOC_LABELS,
        "VEHICLE_DOC_LABELS": VEHICLE_DOC_LABELS,
        "today": today,
    })
