from fastapi import APIRouter, Request, Form, Depends, HTTPException, Cookie, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from jose import JWTError, jwt
from datetime import datetime, timedelta

from src.core.config import settings
from src.db.database import async_session
from src.db.models import Driver, Trip, Expense, Vehicle, TripStatus, LocationUpdate, VehicleRepair, RepairStatus, DriverDocument, TripDocument, TripEvent, DriverRequest, RequestType, RequestStatus
from src.services.geofence import check_geofence_arrival
from antigravity_modules.expense_crud import get_active_trip_for_driver, create_expense
from src.services.r2 import save_uploaded_file
from src.web.auth import verify_password
import os
import uuid
import secrets
import logging
from pathlib import Path

from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/app", tags=["Mobile Driver App"])
templates = Jinja2Templates(directory="src/web/templates")

# Local photo storage (fallback when R2 not configured)
# Handled centrally in src/services/r2.py via save_uploaded_file

from src.services.r2 import PHOTO_DIR


@router.get("/photos/{path:path}")
async def serve_photo(path: str):
    """Serve locally stored photos and documents."""
    file_path = (PHOTO_DIR / path).resolve()
    if not str(file_path).startswith(str(PHOTO_DIR.resolve())):
        raise HTTPException(status_code=404, detail="File not found")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    ext = file_path.suffix.lower()
    ct_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".pdf": "application/pdf", ".gif": "image/gif",
    }
    return FileResponse(file_path, media_type=ct_map.get(ext, "application/octet-stream"))

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
    return templates.TemplateResponse(request, "mobile/login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, phone: str = Form(...), password: str = Form(...)):
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.phone == phone))
        driver = result.scalars().first()
        
        if not driver or not driver.password_hash or not verify_password(password, driver.password_hash):
            return templates.TemplateResponse(request, "mobile/login.html", {
                "request": request, 
                "error": "Неверный номер телефона или пароль. Попросите диспетчера выдать вам данные для входа."
            }, status_code=401)
            
        token = create_driver_token(driver.id)
        response = RedirectResponse(url="/app/", status_code=302)
        response.set_cookie("driver_token", token, max_age=365*24*3600, httponly=True, secure=True, samesite="lax")
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
        trip_vehicle = None
        if active_trip:
            exp_res = await session.execute(select(Expense).where(Expense.trip_id == active_trip.id).order_by(Expense.created_at.desc()))
            expenses = exp_res.scalars().all()

            if active_trip.vehicle_id:
                veh_res = await session.execute(select(Vehicle).where(Vehicle.id == active_trip.vehicle_id))
                trip_vehicle = veh_res.scalars().first()

                repairs_res = await session.execute(
                    select(VehicleRepair)
                    .where(VehicleRepair.vehicle_id == active_trip.vehicle_id)
                    .where(VehicleRepair.status.in_([RepairStatus.OPEN, RepairStatus.IN_PROGRESS]))
                    .order_by(VehicleRepair.created_at.desc())
                )
                open_repairs = repairs_res.scalars().all()

    return templates.TemplateResponse(request, "mobile/index.html", {
        "request": request,
        "driver": driver,
        "active_trip": active_trip,
        "trip_vehicle": trip_vehicle,
        "expenses": expenses,
        "open_repairs": open_repairs,
    })

# --- OPEN TRIP ---
@router.get("/open-trip", response_class=HTMLResponse)
async def open_trip_get(request: Request):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        v_res = await session.execute(select(Vehicle).order_by(Vehicle.license_plate))
        vehicles = v_res.scalars().all()
    return templates.TemplateResponse(request, "mobile/open_trip.html", {"request": request, "vehicles": vehicles})

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
            doc_url = await save_uploaded_file(file_bytes, key, content_type=document.content_type)
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
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        if not trip:
            return RedirectResponse("/app/", status_code=302)
        # Load driver's saved fuel card number
        driver_res = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = driver_res.scalars().first()
    return templates.TemplateResponse(request, "mobile/add_expense.html", {
        "request": request,
        "driver": driver,
        "fuel_card_number": driver.fuel_card_number or "" if driver else "",
    })

@router.post("/add-expense")
async def add_expense_post(
    request: Request,
    expense_type: str = Form(...),
    amount: float = Form(...),
    currency: str = Form("KZT"),
    comment: str = Form(""),
    liters: str = Form(default=""),
    odometer: str = Form(default=""),
    station: str = Form(""),
    fuel_card_number: str = Form(""),
    receipt: UploadFile = File(None),
    card_photo: UploadFile = File(None)
):
    driver_id = await requires_driver(request)

    # Static FX rates to KZT (updated periodically)
    FX_RATES: dict[str, float] = {
        "KZT": 1.0,
        "RUB": 5.2,    # 1 RUB ≈ 5.2 KZT
        "USD": 450.0,  # 1 USD ≈ 450 KZT
        "EUR": 490.0,  # 1 EUR ≈ 490 KZT
        "TRY": 13.5,   # 1 TRY ≈ 13.5 KZT
    }
    fx_rate = FX_RATES.get(currency, 1.0)
    amount_kzt = round(amount * fx_rate, 2)

    # Parse optional numeric fields — form always submits them as strings, even when empty
    liters_val = float(liters) if liters and liters.strip() else None
    odometer_val = int(float(odometer)) if odometer and odometer.strip() else None

    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        if not trip:
            return RedirectResponse(url="/app/", status_code=302)

        receipt_url = None
        if receipt and receipt.filename:
            file_bytes = await receipt.read()
            ext = receipt.filename.split('.')[-1] if '.' in receipt.filename else 'jpg'
            key = f"expenses/receipt_{uuid.uuid4()}.{ext}"
            receipt_url = await save_uploaded_file(file_bytes, key, content_type=receipt.content_type)

        card_url = None
        if card_photo and card_photo.filename:
            file_bytes = await card_photo.read()
            ext = card_photo.filename.split('.')[-1] if '.' in card_photo.filename else 'jpg'
            key = f"expenses/card_{uuid.uuid4()}.{ext}"
            card_url = await save_uploaded_file(file_bytes, key, content_type=card_photo.content_type)

        final_comment = comment.strip()
        if expense_type == "FUEL" and fuel_card_number.strip():
            final_comment = f"[Оплата: {fuel_card_number.strip()}] {final_comment}".strip()

        expense = Expense(
            trip_id=trip.id,
            expense_type=expense_type,
            amount=amount,
            currency=currency,
            comment=final_comment or None,
            photo_file_id=receipt_url,
            card_photo_file_id=card_url,
            fx_rate=fx_rate,
            amount_kzt=amount_kzt,
            liters=liters_val if expense_type == "FUEL" else None,
            odometer_reading=odometer_val if expense_type == "FUEL" else None,
            station=station.strip() or None if expense_type == "FUEL" else None,
        )
        session.add(expense)
        await session.flush()  # get expense.id

        # Anomaly check for FUEL: compare consumption vs vehicle norm
        if expense_type == "FUEL" and liters_val and odometer_val and trip.start_odometer:
            # Find previous odometer for this trip (from earlier fuel expenses)
            from sqlalchemy import func as sqlfunc
            prev_odo_result = await session.execute(
                select(Expense.odometer_reading)
                .where(
                    Expense.trip_id == trip.id,
                    Expense.expense_type == "FUEL",
                    Expense.odometer_reading != None,
                    Expense.id != expense.id,
                )
                .order_by(Expense.odometer_reading.desc())
                .limit(1)
            )
            prev_odo = prev_odo_result.scalar()
            base_odo = prev_odo or trip.start_odometer
            km_driven = odometer_val - base_odo

            if km_driven > 10:  # at least 10km to avoid division noise
                actual_per_100 = (liters_val / km_driven) * 100

                # Load vehicle norm
                from src.db.models import Vehicle as _Vehicle
                veh_res = await session.execute(
                    select(_Vehicle).where(_Vehicle.id == trip.vehicle_id)
                )
                vehicle = veh_res.scalars().first()
                norm = vehicle.fuel_norm_per_100km if vehicle and vehicle.fuel_norm_per_100km else 30.0
                threshold = norm * 1.15  # 15% over norm triggers anomaly

                if actual_per_100 > threshold:
                    excess_pct = round((actual_per_100 - norm) / norm * 100, 1)
                    from src.db.models import FuelAnomaly
                    anomaly = FuelAnomaly(
                        expense_id=expense.id,
                        vehicle_id=trip.vehicle_id,
                        trip_id=trip.id,
                        actual_per_100km=round(actual_per_100, 2),
                        norm_per_100km=norm,
                        threshold_per_100km=threshold,
                        excess_percent=excess_pct,
                    )
                    session.add(anomaly)

        # Save fuel card number to driver profile for auto-fill ONLY if it's currently empty, to avoid overwriting with CASH/other card
        if expense_type == "FUEL" and fuel_card_number.strip():
            if not fuel_card_number.strip().lower().startswith("нал"):
                driver_res = await session.execute(select(Driver).where(Driver.id == driver_id))
                driver = driver_res.scalars().first()
                if driver and not driver.fuel_card_number:
                    driver.fuel_card_number = fuel_card_number.strip()

        await session.commit()

    return RedirectResponse(url="/app/", status_code=302)

# --- AI RECEIPT PARSING ---
@router.post("/parse-receipt")
async def parse_receipt(request: Request, receipt: UploadFile = File(...)):
    """Parse a fuel receipt photo using free local OCR (Tesseract) and return extracted data."""
    driver_id = await requires_driver(request)

    file_bytes = await receipt.read()
    if len(file_bytes) > 20 * 1024 * 1024:  # 20MB max
        return {"ok": False, "error": "Файл слишком большой"}

    import io
    import re
    import asyncio
    from functools import partial
    try:
        from PIL import Image, ImageEnhance
        import pytesseract
    except ImportError:
        return {"ok": False, "error": "OCR модуль не установлен на сервере"}

    try:
        # Load and enhance image for OCR
        img = Image.open(io.BytesIO(file_bytes))
        img = img.convert('L') # Grayscale
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Run tesseract in thread to avoid blocking asyncio
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, partial(pytesseract.image_to_string, img, lang="rus+eng"))
        
        # Parse data out of OCR text using Regex
        text_lower = text.lower()
        
        liters = None
        amount = None
        currency = "KZT"
        station = None

        # Extract Liters
        l_match = re.search(r'(?:литр|лит\.|лит|lit\.|lit|объем|кол-во|доза)\s*[:=]?\s*(\d+[.,]\d+)', text_lower)
        if l_match:
            try:
                liters = float(l_match.group(1).replace(',', '.'))
            except (ValueError, AttributeError): pass

        # Extract Amount
        a_match = re.search(r'(?:сумма|итого|всего|total|sum|к оплате)\s*[:=]?\s*(\d+[ \d]*[.,]\d+)', text_lower)
        if a_match:
            try:
                cleaned = a_match.group(1).replace(' ', '').replace(',', '.')
                amount = float(cleaned)
            except (ValueError, AttributeError): pass
                
        # Currency Heuristic
        if 'rub' in text_lower or 'руб' in text_lower or '₽' in text: currency = "RUB"
        elif 'kzt' in text_lower or 'тнг' in text_lower or 'тенге' in text_lower or '₸' in text: currency = "KZT"
        elif 'eur' in text_lower or 'евро' in text_lower or '€' in text: currency = "EUR"
        elif 'usd' in text_lower or 'долл' in text_lower or '$' in text: currency = "USD"
            
        # Basic Station Heuristic
        if 'gazprom' in text_lower or 'газпром' in text_lower: station = "Газпромнефть"
        elif 'lukoil' in text_lower or 'лукойл' in text_lower: station = "Лукойл"
        elif 'helios' in text_lower or 'гелиос' in text_lower: station = "Helios"
        elif 'sinooil' in text_lower or 'синоил' in text_lower: station = "Sinooil"
        elif 'qazaq' in text_lower or 'казак' in text_lower: station = "Qazaq Oil"
        elif 'rosneft' in text_lower or 'роснефть' in text_lower: station = "Роснефть"
        elif 'tatneft' in text_lower or 'татнефть' in text_lower: station = "Татнефть"
        elif 'shell' in text_lower: station = "Shell"

        return {
            "ok": True, 
            "liters": liters, 
            "amount": amount, 
            "currency": currency, 
            "station": station
        }
    except Exception as e:
        return {"ok": False, "error": f"Ошибка OCR: {str(e)}"}


# --- CLOSE TRIP ---
@router.get("/close-trip", response_class=HTMLResponse)
async def close_trip_get(request: Request):
    driver_id = await requires_driver(request)
    return templates.TemplateResponse(request, "mobile/close_trip.html", {"request": request})

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
                doc_url = await save_uploaded_file(file_bytes, key, content_type=document.content_type)
                
            trip.status = TripStatus.COMPLETED
            trip.completed_at = datetime.utcnow()
            trip.end_odometer = int(end_odometer) if end_odometer.isdigit() else None
            if doc_url:
                trip.closing_document_id = doc_url
                
            await session.commit()
            
    return RedirectResponse(url="/app/", status_code=302)


# --- DOCUMENTS ---
@router.get("/documents", response_class=HTMLResponse)
async def documents_get(request: Request):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        
        docs_res = await session.execute(
            select(DriverDocument).where(DriverDocument.driver_id == driver_id).order_by(DriverDocument.uploaded_at.desc())
        )
        docs = docs_res.scalars().all()
        
        trip = await get_active_trip_for_driver(session, driver_id)
        trip_docs = []
        if trip:
            td_res = await session.execute(
                select(TripDocument).where(TripDocument.trip_id == trip.id).order_by(TripDocument.uploaded_at.desc())
            )
            trip_docs = td_res.scalars().all()
            
    return templates.TemplateResponse(request, "mobile/documents.html", {
        "request": request, 
        "driver": driver, 
        "docs": docs, 
        "active_trip": trip,
        "trip_docs": trip_docs
    })


@router.post("/documents/upload")
async def documents_upload_post(
    request: Request,
    doc_type: str = Form(...),
    doc_file: UploadFile = File(...),
):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        if not doc_file.filename:
            return RedirectResponse(url="/app/documents", status_code=302)
            
        file_bytes = await doc_file.read()
        ext = doc_file.filename.rsplit(".", 1)[-1].lower() if "." in doc_file.filename else "jpg"
        content_type = "application/pdf" if ext == "pdf" else "image/jpeg"
        
        if doc_type.startswith("trip_"):
            trip = await get_active_trip_for_driver(session, driver_id)
            if not trip:
                return RedirectResponse(url="/app/documents", status_code=302)
            
            key = f"trip_docs/{trip.id}/{uuid.uuid4()}.{ext}"
            r2_url = await save_uploaded_file(file_bytes, key, content_type)
            
            trip_doc = TripDocument(
                trip_id=trip.id,
                file_type=doc_type.replace("trip_", "", 1),
                r2_url=r2_url
            )
            session.add(trip_doc)
        else:
            key = f"driver_docs/{driver_id}/{uuid.uuid4()}.{ext}"
            r2_url = await save_uploaded_file(file_bytes, key, content_type)
            
            driver_doc = DriverDocument(
                driver_id=driver_id,
                doc_type=doc_type,
                r2_url=r2_url
            )
            session.add(driver_doc)
            
        await session.commit()
    return RedirectResponse(url="/app/documents", status_code=302)


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
            
            # Check for geofences if there's an active trip
            if trip:
                await check_geofence_arrival(session, trip, lat, lng)
                
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
    return templates.TemplateResponse(request, "mobile/report_repair.html", {"request": request})


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


# --- REPORT EVENT (BOTTLENECK) ---
@router.get("/trip-event", response_class=HTMLResponse)
async def trip_event_get(request: Request):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        if not trip:
            return RedirectResponse("/app/", status_code=302)
        # Load past events
        result = await session.execute(
            select(TripEvent).where(TripEvent.trip_id == trip.id).order_by(TripEvent.created_at.desc())
        )
        events = result.scalars().all()
    return templates.TemplateResponse(request, "mobile/report_event.html", {"request": request, "events": events})


@router.post("/trip-event")
async def trip_event_post(
    request: Request,
    event_type: str = Form(...),
    location_name: str = Form("")
):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        if trip:
            event = TripEvent(
                trip_id=trip.id,
                event_type=event_type,
                location_name=location_name.strip() or None
            )
            session.add(event)
            await session.commit()
    return RedirectResponse("/app/trip-event", status_code=302)

# --- REQUEST FUNDS / BORDER QUEUE ---
@router.get("/request-funds", response_class=HTMLResponse)
async def request_funds_get(request: Request):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        # We can still let them request even without an active trip, but it's better if they have one.
        result = await session.execute(
            select(DriverRequest).where(DriverRequest.driver_id == driver_id).order_by(DriverRequest.created_at.desc())
        )
        requests = result.scalars().all()
    return templates.TemplateResponse(request, "mobile/request_funds.html", {"request": request, "requests": requests})

@router.get("/camera", response_class=HTMLResponse)
async def camera_get(request: Request):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        driver_result = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = driver_result.scalars().first()

        trip_result = await session.execute(
            select(Trip).where(Trip.driver_id == driver_id, Trip.status == TripStatus.ACTIVE.value)
        )
        active_trip = trip_result.scalars().first()

        vehicle = None
        if active_trip and active_trip.vehicle_id:
            veh_result = await session.execute(select(Vehicle).where(Vehicle.id == active_trip.vehicle_id))
            vehicle = veh_result.scalars().first()

    return templates.TemplateResponse(request, "mobile/camera.html", {
        "request": request,
        "driver": driver,
        "active_trip": active_trip,
        "vehicle": vehicle,
        "active_tab": "camera",
    })


@router.post("/camera/upload")
async def camera_upload(
    request: Request,
    file: UploadFile = File(...),
    trip_id: str = Form(default=""),
):
    from fastapi.responses import JSONResponse as _JSONResponse
    driver_id = await requires_driver(request)
    file_bytes = await file.read()
    is_video = file.content_type and "video" in file.content_type
    ext = "webm" if is_video else "jpg"
    content_type = file.content_type or ("video/webm" if is_video else "image/jpeg")
    key = f"camera/{driver_id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:6]}.{ext}"
    url = await save_uploaded_file(file_bytes, key, content_type)
    if url and trip_id.strip():
        try:
            tid = int(trip_id)
        except (ValueError, TypeError):
            tid = None
        if tid:
            async with async_session() as session:
                # Verify trip belongs to this driver
                trip_check = await session.execute(
                    select(Trip).where(Trip.id == tid, Trip.driver_id == driver_id)
                )
                if trip_check.scalars().first():
                    label = "Видео с камеры" if is_video else "Фото с камеры"
                    session.add(TripDocument(trip_id=tid, file_type=label, r2_url=url))
                    await session.commit()
    return _JSONResponse({"ok": True, "url": url})


@router.post("/create-request")
async def request_funds_post(
    request: Request,
    request_type: str = Form(...),
    description: str = Form(...),
    amount: float = Form(None),
    currency: str = Form("KZT")
):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        trip = await get_active_trip_for_driver(session, driver_id)
        new_req = DriverRequest(
            driver_id=driver_id,
            trip_id=trip.id if trip else None,
            request_type=request_type,
            description=description.strip(),
            amount=amount,
            currency=currency if amount else None,
            status=RequestStatus.PENDING
        )
        session.add(new_req)
        await session.commit()
    return RedirectResponse("/app/request-funds", status_code=302)


@router.post("/cancel-request/{request_id}")
async def cancel_request(request: Request, request_id: int):
    driver_id = await requires_driver(request)
    async with async_session() as session:
        result = await session.execute(
            select(DriverRequest).where(
                DriverRequest.id == request_id,
                DriverRequest.driver_id == driver_id,
                DriverRequest.status == RequestStatus.PENDING,
            )
        )
        req = result.scalars().first()
        if req:
            await session.delete(req)
            await session.commit()
    return RedirectResponse("/app/request-funds", status_code=302)
