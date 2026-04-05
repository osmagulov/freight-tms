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
from src.web.auth import require_admin

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
    current_user: dict = Depends(require_admin),
):
    from_dt, to_dt = _parse_date_range(from_date, to_date)
    fd_str = from_dt.strftime("%Y-%m-%d")
    td_str = to_dt.strftime("%Y-%m-%d")

    async with async_session() as session:
        # Category summary
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

        # Trip count
        trip_count_result = await session.execute(
            select(func.count(Trip.id)).where(
                Trip.created_at >= from_dt, Trip.created_at <= to_dt
            )
        )
        trip_count = trip_count_result.scalar() or 0

        # Active / completed trips
        active_trips_result = await session.execute(
            select(func.count(Trip.id)).where(Trip.status == "ACTIVE")
        )
        active_trips = active_trips_result.scalar() or 0

        # Total Revenue grouped by currency
        revenue_result = await session.execute(
            select(Trip.price_currency, func.sum(Trip.price).label("total"))
            .where(Trip.created_at >= from_dt, Trip.created_at <= to_dt, Trip.price.isnot(None))
            .group_by(Trip.price_currency)
        )
        revenue_by_currency = {row.price_currency or "KZT": row.total or 0 for row in revenue_result.all()}
        # Keep total_revenue for backward compat (sum of all, currency-agnostic)
        total_revenue = sum(revenue_by_currency.values())

        # Per-driver analytics
        driver_stats_result = await session.execute(
            select(
                Driver.id,
                Driver.name,
                func.count(func.distinct(Expense.trip_id)).label("trip_count"),
                func.count(Expense.id).label("expense_count"),
                func.sum(func.coalesce(Expense.amount_kzt, Expense.amount)).label("total_kzt"),
            )
            .join(Trip, Trip.driver_id == Driver.id)
            .join(Expense, Expense.trip_id == Trip.id)
            .where(Expense.created_at >= from_dt, Expense.created_at <= to_dt)
            .group_by(Driver.id, Driver.name)
            .order_by(func.sum(func.coalesce(Expense.amount_kzt, Expense.amount)).desc())
        )
        driver_stats = driver_stats_result.all()

        # Fuel-specific stats
        fuel_stats_result = await session.execute(
            select(
                func.count(Expense.id).label("cnt"),
                func.sum(func.coalesce(Expense.amount_kzt, Expense.amount)).label("total_kzt"),
                func.sum(Expense.liters).label("total_liters"),
            )
            .where(
                Expense.created_at >= from_dt,
                Expense.created_at <= to_dt,
                Expense.expense_type == "FUEL",
            )
        )
        fuel_row = fuel_stats_result.first()

        # Pending expenses count
        pending_result = await session.execute(
            select(func.count(Expense.id)).where(Expense.status == "PENDING")
        )
        pending_count = pending_result.scalar() or 0

        # Pending driver requests count
        from src.db.models import DriverRequest, RequestStatus
        prc_result = await session.execute(
            select(func.count(DriverRequest.id)).where(DriverRequest.status == RequestStatus.PENDING)
        )
        pending_requests_count = prc_result.scalar() or 0

        drivers_result = await session.execute(
            select(Driver).where(Driver.status == "ACTIVE").order_by(Driver.name)
        )
        drivers = drivers_result.scalars().all()

        vehicles_result = await session.execute(
            select(Vehicle).order_by(Vehicle.license_plate)
        )
        vehicles = vehicles_result.scalars().all()

        # Upcoming fuel needs: active + planned trips with planned_distance_km set
        fuel_plan_result = await session.execute(
            select(Trip, Vehicle)
            .join(Vehicle, Trip.vehicle_id == Vehicle.id)
            .where(
                Trip.status.in_(["ACTIVE", "PLANNED"]),
                Trip.planned_distance_km.isnot(None),
                Vehicle.fuel_norm_per_100km.isnot(None),
            )
            .order_by(Trip.planned_departure.asc().nullslast())
        )
        fuel_plan_rows = fuel_plan_result.all()
        fuel_plan = []
        total_planned_liters = 0
        for trip, vehicle in fuel_plan_rows:
            liters = round(trip.planned_distance_km * vehicle.fuel_norm_per_100km / 100)
            total_planned_liters += liters
            fuel_plan.append({
                "trip_id": trip.id,
                "route": trip.route_details or f"Рейс #{trip.id}",
                "plate": vehicle.license_plate,
                "trailer": vehicle.trailer_plate,
                "distance_km": trip.planned_distance_km,
                "liters": liters,
                "departure": trip.planned_departure,
                "status": trip.status,
            })

    grand_total = sum(row.total_kzt or 0 for row in summary)
    fuel_total_liters = fuel_row.total_liters if fuel_row and fuel_row.total_liters else 0
    fuel_total_kzt = fuel_row.total_kzt if fuel_row and fuel_row.total_kzt else 0
    fuel_count = fuel_row.cnt if fuel_row else 0
    avg_price_per_liter = round(fuel_total_kzt / fuel_total_liters, 1) if fuel_total_liters else 0

    return templates.TemplateResponse(request, "director_summary.html",
        {
            "request": request,
            "user": current_user,
            "summary": summary,
            "trip_count": trip_count,
            "active_trips": active_trips,
            "grand_total": grand_total,
            "from_date": fd_str,
            "to_date": td_str,
            "drivers": drivers,
            "vehicles": vehicles,
            "driver_stats": driver_stats,
            "fuel_total_liters": fuel_total_liters,
            "fuel_total_kzt": fuel_total_kzt,
            "fuel_count": fuel_count,
            "avg_price_per_liter": avg_price_per_liter,
            "pending_count": pending_count,
            "pending_requests_count": pending_requests_count,
            "total_revenue": total_revenue,
            "revenue_by_currency": revenue_by_currency,
            "total_profit": total_revenue - grand_total,
            "fuel_plan": fuel_plan,
            "total_planned_liters": total_planned_liters,
        },
    )


@router.get("/trucks", response_class=HTMLResponse)
async def director_trucks(
    request: Request,
    from_date: str | None = None,
    to_date: str | None = None,
    current_user: dict = Depends(require_admin),
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

    return templates.TemplateResponse(request, "director_trucks.html",
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
    current_user: dict = Depends(require_admin),
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
    safe_from = from_dt.strftime("%Y-%m-%d")
    safe_to = to_dt.strftime("%Y-%m-%d")
    filename = f"expenses_{safe_from}_{safe_to}.csv"
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/anomalies", response_class=HTMLResponse)
async def director_anomalies(
    request: Request,
    current_user: dict = Depends(require_admin),
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

    return templates.TemplateResponse(request, "director_anomalies.html",
        {"request": request, "user": current_user, "anomalies": anomalies},
    )


@router.get("/drivers", response_class=HTMLResponse)
async def director_driver_pick(
    request: Request,
    current_user: dict = Depends(require_admin),
):
    async with async_session() as session:
        result = await session.execute(
            select(Driver).where(Driver.status == "ACTIVE").order_by(Driver.name)
        )
        drivers = result.scalars().all()

    return templates.TemplateResponse(request, "director_driver_pick.html",
        {"request": request, "user": current_user, "drivers": drivers},
    )


@router.get("/drivers/{driver_id}", response_class=HTMLResponse)
async def director_driver_history(
    request: Request,
    driver_id: int,
    from_date: str | None = None,
    to_date: str | None = None,
    current_user: dict = Depends(require_admin),
):
    from_dt, to_dt = _parse_date_range(from_date, to_date)
    fd_str = from_dt.strftime("%Y-%m-%d")
    td_str = to_dt.strftime("%Y-%m-%d")

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
            .where(
                Trip.driver_id == driver_id,
                Expense.created_at >= from_dt,
                Expense.created_at <= to_dt,
            )
            .options(
                selectinload(Expense.trip).selectinload(Trip.vehicle),
            )
            .order_by(Expense.created_at.desc())
        )
        expenses = expenses_result.scalars().all()

        # Category breakdown for this driver
        cat_result = await session.execute(
            select(
                Expense.expense_type,
                func.count(Expense.id).label("cnt"),
                func.sum(func.coalesce(Expense.amount_kzt, Expense.amount)).label("total_kzt"),
            )
            .join(Trip, Expense.trip_id == Trip.id)
            .where(
                Trip.driver_id == driver_id,
                Expense.created_at >= from_dt,
                Expense.created_at <= to_dt,
            )
            .group_by(Expense.expense_type)
            .order_by(func.sum(func.coalesce(Expense.amount_kzt, Expense.amount)).desc())
        )
        categories = cat_result.all()

        # Trip count for this driver in period
        trip_count_result = await session.execute(
            select(func.count(Trip.id)).where(
                Trip.driver_id == driver_id,
                Trip.created_at >= from_dt,
                Trip.created_at <= to_dt,
            )
        )
        trip_count = trip_count_result.scalar() or 0

        # Fuel stats for this driver
        fuel_result = await session.execute(
            select(
                func.sum(Expense.liters).label("total_liters"),
                func.sum(func.coalesce(Expense.amount_kzt, Expense.amount)).label("fuel_kzt"),
                func.count(Expense.id).label("fuel_count"),
            )
            .join(Trip, Expense.trip_id == Trip.id)
            .where(
                Trip.driver_id == driver_id,
                Expense.expense_type == "FUEL",
                Expense.created_at >= from_dt,
                Expense.created_at <= to_dt,
            )
        )
        fuel_row = fuel_result.first()

    total_kzt = sum(
        (e.amount_kzt if e.amount_kzt is not None else e.amount) for e in expenses
    )
    avg_per_trip = round(total_kzt / trip_count) if trip_count > 0 else 0
    fuel_liters = fuel_row.total_liters if fuel_row and fuel_row.total_liters else 0
    fuel_kzt = fuel_row.fuel_kzt if fuel_row and fuel_row.fuel_kzt else 0
    fuel_count = fuel_row.fuel_count if fuel_row else 0

    return templates.TemplateResponse(request, "director_driver.html",
        {
            "request": request,
            "user": current_user,
            "driver": driver,
            "all_drivers": all_drivers,
            "expenses": expenses,
            "total_kzt": total_kzt,
            "categories": categories,
            "trip_count": trip_count,
            "avg_per_trip": avg_per_trip,
            "fuel_liters": fuel_liters,
            "fuel_kzt": fuel_kzt,
            "fuel_count": fuel_count,
            "from_date": fd_str,
            "to_date": td_str,
        },
    )


@router.get("/rating", response_class=HTMLResponse)
async def director_rating(
    request: Request,
    from_date: str | None = None,
    to_date: str | None = None,
    current_user: dict = Depends(require_admin),
):
    from_dt, to_dt = _parse_date_range(from_date, to_date)
    fd_str = from_dt.strftime("%Y-%m-%d")
    td_str = to_dt.strftime("%Y-%m-%d")

    async with async_session() as session:
        trips_result = await session.execute(
            select(Trip)
            .options(selectinload(Trip.driver), selectinload(Trip.expenses))
            .where(Trip.created_at >= from_dt, Trip.created_at <= to_dt)
            .where(Trip.status == "COMPLETED")
        )
        trips = trips_result.scalars().all()

        anomalies_result = await session.execute(
            select(FuelAnomaly).where(FuelAnomaly.created_at >= from_dt, FuelAnomaly.created_at <= to_dt)
        )
        anomalies = anomalies_result.scalars().all()

    # Aggregate by driver
    from collections import defaultdict
    driver_stats = defaultdict(lambda: {
        "name": "Unknown",
        "trips_count": 0,
        "total_km": 0,
        "total_fines_kzt": 0,
        "total_repairs_kzt": 0,
        "total_fuel_kzt": 0,
        "anomalies_count": 0,
        "expenses": 0
    })

    # Map anomalies to trip for easy lookup (or just use driver_id if anomaly had it, but anomaly has trip_id)
    anomaly_counts = defaultdict(int)
    for a in anomalies:
        anomaly_counts[a.trip_id] += 1

    for t in trips:
        if not t.driver:
            continue
        d_id = t.driver_id
        stats = driver_stats[d_id]
        stats["name"] = t.driver.name or str(t.driver.tg_id)
        stats["trips_count"] += 1
        
        km = (t.end_odometer - t.start_odometer) if t.end_odometer and t.start_odometer and t.end_odometer >= t.start_odometer else 0
        stats["total_km"] += km
        stats["anomalies_count"] += anomaly_counts.get(t.id, 0)

        for e in t.expenses:
            amt = e.amount_kzt if e.amount_kzt is not None else e.amount
            stats["expenses"] += amt
            if e.expense_type == "FINE":
                stats["total_fines_kzt"] += amt
            elif e.expense_type == "REPAIR":
                stats["total_repairs_kzt"] += amt
            elif e.expense_type == "FUEL":
                stats["total_fuel_kzt"] += amt

    # Calculate scores
    leaderboard = []
    for d_id, st in driver_stats.items():
        km = st["total_km"] or 1 # avoid div zero
        st["fines_per_10k"] = (st["total_fines_kzt"] / km) * 10000 if km > 1 else 0
        st["repairs_per_10k"] = (st["total_repairs_kzt"] / km) * 10000 if km > 1 else 0
        
        # Base score 100. Deduct points for anomalies, high fines.
        score = 100
        score -= st["anomalies_count"] * 10
        score -= (st["total_fines_kzt"] / max(st["trips_count"], 1)) / 5000  # -1 pt per 5000 KZT fine per trip
        score = max(min(int(score), 100), 0)
        st["score"] = score
        
        leaderboard.append((d_id, st))

    # Sort descending by score
    leaderboard.sort(key=lambda x: x[1]["score"], reverse=True)

    return templates.TemplateResponse(request, "director_rating.html", {
        "request": request,
        "user": current_user,
        "from_date": fd_str,
        "to_date": td_str,
        "leaderboard": leaderboard
    })

