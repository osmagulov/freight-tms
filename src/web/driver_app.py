from fastapi import APIRouter, Request, Form, Depends, HTTPException, Cookie, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from jose import JWTError, jwt
from datetime import datetime, timedelta

from src.core.config import settings
from src.db.database import async_session
from src.db.models import Driver, Trip, Expense, Vehicle, TripStatus, LocationUpdate, VehicleRepair, RepairStatus
from antigravity_modules.expense_crud import get_active_trip_for_driver, create_expense
from src.services.r2 import upload_to_r2
from src.web.auth import verify_password
import os
import uuid
import secrets
from pathlib import Path

router = APIRouter(prefix="/app", tags=["Mobile Driver App"])
templates = Jinja2Templates(directory="src/web/templates")

# Simple auth logic for drivers
def create_driver_token(driver_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=365)
    return jwt.encode({"sub": str(driver_id), "role": "driver", "exp": expire}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

async def get_current_driver(request: Request):
    token = request.cookies.get("driver_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("role") != "driver":
            return None
        driver_id = int(payload.get("sub"))
        return driver_id
    except JWTError:
        return None

async def requires_driver(request: Request):
    driver_id = await get_current_driver(request)
    if not driver_id:
        raise HTTPException(status_code=302, headers={"Location": "/app/login"})
    return driver_id

@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("mobile/login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, phone: str = Form(...), password: str = Form(...)):
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.phone == phone))
        driver = result.scalars().first()
        
        if not driver or not driver.password_hash or not verify_password(password, driver.password_hash):
            return templates.TemplateResponse("mobile/login.html", {
                "request": request, 
                "error": "Неверный номер телефона или пароль. Попросите диспетчера выдать вам данные для входа."
            }, status_code=401)
            
        token = create_driver_token(driver.id)
        response = RedirectResponse(url="/app/", status_code=302)
        response.set_cookie("driver_token", token, max_age=365*24*3600, httponly=True)
        return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/app/login", status_code=302)
    response.delete_cookie("driver_token")
    return response

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    driver_id = await get_current_driver(request)
    if not driver_id:
        return RedirectResponse("/app/login", status_code=302)
        
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        
        active_trip = await get_active_trip_for_driver(session, driver_id)
        
        expenses = []
        open_repairs = []
        if active_trip:
            exp_res = await session.execute(select(Expense).where(Expense.trip_id == active_trip.id).order_by(Expense.created_at.desc()))
            expenses = exp_res.scalars().all()

            if active_trip.vehicle_id:
                repairs_res = await session.execute(
                    select(VehicleRepair)
                    .where(VehicleRepair.vehicle_id == active_trip.vehicle_id)
                    .where(VehicleRepair.status.in_([RepairStatus.OPEN, RepairStatus.IN_PROGRESS]))
                    .order_by(VehicleRepair.created_at.desc())
                )
                open_repairs = repairs_res.scalars().all()

    return templates.TemplateResponse("mobile/index.html", {
        "request": request,
        "driver": driver,
        "active_trip": active_trip,
        "expenses": expenses,
        "open_repairs": open_repairs,
    })

# --- OPEN TRIP ---
@router.get("/open-trip", response_class=HTMLResponse)
async def open_trip_get(request: Request):
    driver_id = await requires_driver(request)
    return templates.TemplateResponse("mobile/open_trip.html", {"request": request})

@router.post("/open-trip")
async def open_trip_post(
    request: Request,
    route: str = Form(...),
    vehicle_plate: str = Form(...),
    odometer: str = Form(...),
    document: UploadFile = File(None)
):
    driver_id = await requires_driver(request)
    
    async with async_session() as session:
        # Find or create vehicle
        res_v = await session.execute(select(Vehicle).where(Vehicle.license_plate == vehicle_plate))
        vehicle = res_v.scalars().first()
        if not vehicle:
            vehicle = Vehicle(license_plate=vehicle_plate)
            session.add(vehicle)
            await session.commit()
            
        # Create the trip first
        trip = Trip(
            driver_id=driver_id,
            vehicle_id=vehicle.id,
            route_details=route,
            start_odometer=int(odometer) if odometer.isdigit() else 0,
            status=TripStatus.ACTIVE
        )
        session.add(trip)
        await session.flush()  # To get trip.id
        
        # Optional: Save document
        if document and document.filename:
            from src.db.models import TripDocument
            file_bytes = await document.read()
            ext = document.filename.split('.')[-1] if '.' in document.filename else 'jpg'
            key = f"trips/{uuid.uuid4()}.{ext}"
            doc_url = await upload_to_r2(file_bytes, key, content_type=document.content_type)
            if doc_url:
                trip_doc = TripDocument(
                    trip_id=trip.id,
                    file_type="cmr_start",
                    r2_url=doc_url
                )
                session.add(trip_doc)

        await session.commit()
        
    return RedirectResponse(url="/app/", status_code=302)

# --- ADD EXPENSE ---
@router.get("/add-expense", response_class=HTMLResponse)
async def add_expense_get(request: Request):
    driver_id = await requires_driver(request)
    # Check if active trip
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        if not trip:
            return RedirectResponse("/app/", status_code=302)
    return templates.TemplateResponse("mobile/add_expense.html", {"request": request})

@router.post("/add-expense")
async def add_expense_post(
    request: Request,
    expense_type: str = Form(...),
    amount: float = Form(...),
    currency: str = Form("RUB"),
    comment: str = Form(""),
    receipt: UploadFile = File(None),
    card_photo: UploadFile = File(None)
):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        if trip:
            receipt_url = None
            if receipt and receipt.filename:
                file_bytes = await receipt.read()
                ext = receipt.filename.split('.')[-1] if '.' in receipt.filename else 'jpg'
                key = f"expenses/receipt_{uuid.uuid4()}.{ext}"
                receipt_url = await upload_to_r2(file_bytes, key, content_type=receipt.content_type)
                
            card_url = None
            if card_photo and card_photo.filename:
                file_bytes = await card_photo.read()
                ext = card_photo.filename.split('.')[-1] if '.' in card_photo.filename else 'jpg'
                key = f"expenses/card_{uuid.uuid4()}.{ext}"
                card_url = await upload_to_r2(file_bytes, key, content_type=card_photo.content_type)

            expense = Expense(
                trip_id=trip.id,
                expense_type=expense_type,
                amount=amount,
                currency=currency,
                comment=comment,
                photo_file_id=receipt_url,
                card_photo_file_id=card_url
            )
            session.add(expense)
            await session.commit()
            
    return RedirectResponse(url="/app/", status_code=302)

# --- CLOSE TRIP ---
@router.get("/close-trip", response_class=HTMLResponse)
async def close_trip_get(request: Request):
    driver_id = await requires_driver(request)
    return templates.TemplateResponse("mobile/close_trip.html", {"request": request})

@router.post("/close-trip")
async def close_trip_post(
    request: Request,
    end_odometer: str = Form(...),
    document: UploadFile = File(None)
):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        if trip:
            doc_url = None
            if document and document.filename:
                file_bytes = await document.read()
                ext = document.filename.split('.')[-1] if '.' in document.filename else 'jpg'
                key = f"trips/closing_{uuid.uuid4()}.{ext}"
                doc_url = await upload_to_r2(file_bytes, key, content_type=document.content_type)
                
            trip.status = TripStatus.COMPLETED
            trip.completed_at = datetime.utcnow()
            trip.end_odometer = int(end_odometer) if end_odometer.isdigit() else None
            if doc_url:
                trip.closing_document_id = doc_url
                
            await session.commit()
            
    return RedirectResponse(url="/app/", status_code=302)

# --- LOCATION FIX ---
@router.post("/location")
async def location_post(request: Request):
    driver_id = await requires_driver(request)
    data = await request.json()
    lat = data.get("lat")
    lng = data.get("lng")
    
    if lat and lng:
        async with async_session() as session:
            trip = await get_active_trip_for_driver(session, driver_id)
            loc = LocationUpdate(
                driver_id=driver_id,
                trip_id=trip.id if trip else None,
                latitude=lat,
                longitude=lng
            )
            session.add(loc)
            await session.commit()
            
    return {"status": "ok"}


# --- REPORT REPAIR ---
@router.get("/report-repair", response_class=HTMLResponse)
async def report_repair_get(request: Request):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        if not trip:
            return RedirectResponse("/app/", status_code=302)
    return templates.TemplateResponse("mobile/report_repair.html", {"request": request})


@router.post("/report-repair")
async def report_repair_post(
    request: Request,
    description: str = Form(...),
    priority: str = Form("NORMAL"),
):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        if trip and trip.vehicle_id:
            repair = VehicleRepair(
                vehicle_id=trip.vehicle_id,
                trip_id=trip.id,
                description=description.strip(),
                priority=priority,
                status=RepairStatus.OPEN,
                reported_by="driver",
            )
            session.add(repair)
            await session.commit()
    return RedirectResponse("/app/", status_code=302)
