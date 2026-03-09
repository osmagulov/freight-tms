import csv
import io
import logging
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.db.database import async_session
from src.db.models import Driver, Expense, FuelAnomaly, Trip, Vehicle
from src.web.auth import get_current_user_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/panel/director", tags=["director"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _parse_date_range(from_date: str | None, to_date: str | None):
    today = date.today()
    try:
        fd = datetime.strptime(from_date, "%Y-%m-%d") if from_date else datetime(today.year, today.month, 1)
    except ValueError:
        fd = datetime(today.year, today.month, 1)
    try:
        td = (
            datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            if to_date
            else datetime(today.year, today.month, today.day, 23, 59, 59)
        )
    except ValueError:
        td = datetime(today.year, today.month, today.day, 23, 59, 59)
    return fd, td


@router.get("", response_class=HTMLResponse)
async def director_summary(
    request: Request,
    from_date: str | None = None,
    to_date: str | None = None,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    from_dt, to_dt = _parse_date_range(from_date, to_date)
    fd_str = from_dt.strftime("%Y-%m-%d")
    td_str = to_dt.strftime("%Y-%m-%d")

    async with async_session() as session:
        summary_result = await session.execute(
            select(
                Expense.expense_type,
                func.count(Expense.id).label("cnt"),
                func.sum(func.coalesce(Expense.amount_kzt, Expense.amount)).label("total_kzt"),
            )
            .where(Expense.created_at >= from_dt, Expense.created_at <= to_dt)
            .group_by(Expense.expense_type)
            .order_by(Expense.expense_type)
        )
        summary = summary_result.all()

        trip_count_result = await session.execute(
            select(func.count(Trip.id)).where(
                Trip.created_at >= from_dt, Trip.created_at <= to_dt
            )
        )
        trip_count = trip_count_result.scalar() or 0

        drivers_result = await session.execute(
            select(Driver).where(Driver.status == "ACTIVE").order_by(Driver.name)
        )
        drivers = drivers_result.scalars().all()

        vehicles_result = await session.execute(
            select(Vehicle).order_by(Vehicle.license_plate)
        )
        vehicles = vehicles_result.scalars().all()

    grand_total = sum(row.total_kzt or 0 for row in summary)

    return templates.TemplateResponse(
        "director_summary.html",
        {
            "request": request,
            "user": current_user,
            "summary": summary,
            "trip_count": trip_count,
            "grand_total": grand_total,
            "from_date": fd_str,
            "to_date": td_str,
            "drivers": drivers,
            "vehicles": vehicles,
        },
    )


@router.get("/trucks", response_class=HTMLResponse)
async def director_trucks(
    request: Request,
    from_date: str | None = None,
    to_date: str | None = None,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    from_dt, to_dt = _parse_date_range(from_date, to_date)
    fd_str = from_dt.strftime("%Y-%m-%d")
    td_str = to_dt.strftime("%Y-%m-%d")

    async with async_session() as session:
        trips_result = await session.execute(
            select(Trip)
            .where(Trip.created_at >= from_dt, Trip.created_at <= to_dt)
            .options(
                selectinload(Trip.driver),
                selectinload(Trip.vehicle),
                selectinload(Trip.expenses),
            )
            .order_by(Trip.vehicle_id, Trip.created_at.desc())
        )
        trips = trips_result.scalars().all()

    by_vehicle: dict[str, list] = defaultdict(list)
    for t in trips:
        plate = t.vehicle.license_plate if t.vehicle else "—"
        total_kzt = sum(
            (e.amount_kzt if e.amount_kzt is not None else e.amount) for e in t.expenses
        )
        km = (t.end_odometer - t.start_odometer) if t.end_odometer and t.start_odometer else None
        by_vehicle[plate].append({"trip": t, "total_kzt": total_kzt, "km": km})

    vehicle_trips = sorted(by_vehicle.items())

    return templates.TemplateResponse(
        "director_trucks.html",
        {
            "request": request,
            "user": current_user,
            "vehicle_trips": vehicle_trips,
            "from_date": fd_str,
            "to_date": td_str,
        },
    )


@router.get("/export")
async def director_export(
    from_date: str | None = None,
    to_date: str | None = None,
    vehicle_id: int | None = None,
    driver_id: int | None = None,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    from_dt, to_dt = _parse_date_range(from_date, to_date)

    async with async_session() as session:
        stmt = (
            select(Expense)
            .join(Trip, Expense.trip_id == Trip.id)
            .where(Expense.created_at >= from_dt, Expense.created_at <= to_dt)
            .options(
                selectinload(Expense.trip).selectinload(Trip.driver),
                selectinload(Expense.trip).selectinload(Trip.vehicle),
            )
            .order_by(Expense.created_at.desc())
        )
        if vehicle_id:
            stmt = stmt.where(Trip.vehicle_id == vehicle_id)
        if driver_id:
            stmt = stmt.where(Trip.driver_id == driver_id)

        result = await session.execute(stmt)
        expenses = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Дата", "Борт", "Водитель", "Маршрут", "Тип",
        "Сумма", "Валюта", "Сумма KZT", "Статус", "Комментарий",
    ])
    for e in expenses:
        writer.writerow([
            e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
            e.trip.vehicle.license_plate if e.trip and e.trip.vehicle else "",
            e.trip.driver.name if e.trip and e.trip.driver else "",
            e.trip.route_details or "" if e.trip else "",
            e.expense_type,
            e.amount,
            e.currency,
            round(e.amount_kzt, 2) if e.amount_kzt else round(e.amount, 2),
            e.status,
            e.comment or "",
        ])

    # UTF-8 BOM for Excel compatibility
    content = "\ufeff" + output.getvalue()
    filename = f"expenses_{from_date or 'all'}_{to_date or 'all'}.csv"
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/anomalies", response_class=HTMLResponse)
async def director_anomalies(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(FuelAnomaly)
            .options(
                selectinload(FuelAnomaly.vehicle),
                selectinload(FuelAnomaly.trip).selectinload(Trip.driver),
            )
            .order_by(FuelAnomaly.created_at.desc())
        )
        anomalies = result.scalars().all()

    return templates.TemplateResponse(
        "director_anomalies.html",
        {"request": request, "user": current_user, "anomalies": anomalies},
    )


@router.get("/drivers", response_class=HTMLResponse)
async def director_driver_pick(
    request: Request,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(
            select(Driver).where(Driver.status == "ACTIVE").order_by(Driver.name)
        )
        drivers = result.scalars().all()

    return templates.TemplateResponse(
        "director_driver_pick.html",
        {"request": request, "user": current_user, "drivers": drivers},
    )


@router.get("/drivers/{driver_id}", response_class=HTMLResponse)
async def director_driver_history(
    request: Request,
    driver_id: int,
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        driver_result = await session.execute(
            select(Driver).where(Driver.id == driver_id)
        )
        driver = driver_result.scalars().first()
        if not driver:
            return RedirectResponse(url="/panel/director/drivers", status_code=302)

        all_drivers_result = await session.execute(
            select(Driver).where(Driver.status == "ACTIVE").order_by(Driver.name)
        )
        all_drivers = all_drivers_result.scalars().all()

        expenses_result = await session.execute(
            select(Expense)
            .join(Trip, Expense.trip_id == Trip.id)
            .where(Trip.driver_id == driver_id)
            .options(
                selectinload(Expense.trip).selectinload(Trip.vehicle),
            )
            .order_by(Expense.created_at.desc())
        )
        expenses = expenses_result.scalars().all()

    total_kzt = sum(
        (e.amount_kzt if e.amount_kzt is not None else e.amount) for e in expenses
    )

    return templates.TemplateResponse(
        "director_driver.html",
        {
            "request": request,
            "user": current_user,
            "driver": driver,
            "all_drivers": all_drivers,
            "expenses": expenses,
            "total_kzt": total_kzt,
        },
    )
