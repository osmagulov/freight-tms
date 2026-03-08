# src/web/panel.py
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update as sa_update

from src.db.database import async_session
from src.db.models import Driver, Vehicle
from src.web.auth import (
    create_access_token,
    get_current_user_from_cookie,
    verify_password,
)
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/panel", tags=["panel"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(),
    password: str = Form(),
):
    # Validate against env-based credentials (Phase 1: single admin account)
    is_valid = (
        username == settings.ADMIN_USERNAME
        and settings.ADMIN_PASSWORD_HASH
        and verify_password(password, settings.ADMIN_PASSWORD_HASH)
    )
    if not is_valid:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный логин или пароль"},
            status_code=401,
        )
    token = create_access_token({"sub": username, "role": "dispatcher"})
    response = RedirectResponse(url="/panel/drivers", status_code=302)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/panel/login", status_code=302)
    response.delete_cookie("access_token")
    return response


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
    fuel_norm_per_100km: float = Form(default=0.0),
    current_user: dict = Depends(get_current_user_from_cookie),
):
    async with async_session() as session:
        result = await session.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
        vehicle = result.scalars().first()
        if vehicle:
            vehicle.make = make or None
            vehicle.model = model or None
            vehicle.fuel_norm_per_100km = fuel_norm_per_100km or None
            session.add(vehicle)
            await session.commit()
    return RedirectResponse(url="/panel/drivers", status_code=302)
