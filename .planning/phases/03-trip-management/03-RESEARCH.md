# Phase 3: Trip Management — Research

**Researched:** 2026-03-09
**Domain:** Trip lifecycle (dispatcher web panel + PTB bot flows), PDF document upload, SQLAlchemy filtered queries, fleet status dashboard
**Confidence:** HIGH

---

## 1. Trip Model — Schema Gaps

Current `Trip` model (`src/db/models.py` lines 58-80) is missing fields required by TRIP-01:
- `client_name` — customer name (TRIP-01)
- `planned_departure` — date (TRIP-01)
- `planned_arrival` — date (TRIP-01)
- `delivery_status` — string (DELIVERED / PARTIAL / FAILED) for TRIP-05

Also missing for TRIP-04 (multi-document attachment):
- Need a `TripDocument` table: `id, trip_id FK, file_type (photo/pdf), r2_url, tg_file_id, uploaded_at`

`Trip.closing_document_id` exists but stores a Telegram `file_id` (ephemeral). Leave as legacy; TripDocument provides durable R2 URLs going forward.

**Alembic migration needs:**
```sql
ALTER TABLE trips ADD COLUMN client_name VARCHAR;
ALTER TABLE trips ADD COLUMN planned_departure TIMESTAMP;
ALTER TABLE trips ADD COLUMN planned_arrival TIMESTAMP;
ALTER TABLE trips ADD COLUMN delivery_status VARCHAR;
CREATE TABLE trip_documents (...);
CREATE INDEX ix_trip_documents_trip_id ON trip_documents(trip_id);
```

---

## 2. trip_opening.py — Complete Refactor Required

Current code (`antigravity_modules/trip_opening.py`):
- Creates trips from scratch with `vehicle_id=1` hardcoded (line 112)
- Asks driver for route/cargo/odometer — all info dispatcher should pre-fill

**Phase 3 correct flow:**
1. Driver taps "НАЧАТЬ РЕЙС"
2. Bot queries `Trip.status == PLANNED AND driver_id == driver.id` — shows the planned trip assigned by dispatcher
3. Driver confirms departure → enters start odometer → trip status → ACTIVE, vehicle status → ON_TRIP
4. If no planned trip: "Нет назначенного рейса. Ожидайте назначения диспетчером."

**Key CRUD needed:**
```python
async def get_planned_trip_for_driver(session, driver_id) -> Trip | None:
    result = await session.execute(
        select(Trip).where(
            Trip.driver_id == driver_id,
            Trip.status == TripStatus.PLANNED
        ).order_by(Trip.created_at).limit(1)
    )
    return result.scalars().first()

async def activate_trip(session, trip_id, start_odometer, vehicle_id) -> None:
    await session.execute(
        sa_update(Trip).where(Trip.id == trip_id).values(
            status=TripStatus.ACTIVE, start_odometer=start_odometer
        )
    )
    await session.execute(
        sa_update(Vehicle).where(Vehicle.id == vehicle_id).values(
            status=VehicleStatus.ON_TRIP
        )
    )
    await session.commit()
```

---

## 3. trip_closing.py — R2 Upload + Vehicle Status

Current code (`antigravity_modules/trip_closing.py`):
- Stores Telegram `file_id` in `Trip.closing_document_id` (not durable)
- Does NOT update `Vehicle.status` on close

**Phase 3 changes:**
- Upload closing doc to R2 (`upload_to_r2(bytes, key, content_type)`)
- Create `TripDocument` record with R2 URL
- Update `vehicle.status = AVAILABLE` when trip closes
- Add `delivery_status` step (DELIVERED / PARTIAL / FAILED keyboard before doc upload)

**New `close_trip` flow states:**
```
AWAITING_END_ODOMETER → AWAITING_DELIVERY_STATUS → AWAITING_CLOSING_DOCS → DONE
```

---

## 4. PDF Document Handling — r2.py Extension

`src/services/r2.py` line 34: `ContentType` hardcoded to `"image/jpeg"`.

**Fix:** Add `content_type` parameter:
```python
def _upload_sync(file_bytes: bytes, key: str, content_type: str = "image/jpeg") -> str:
    client = _get_r2_client()
    client.upload_fileobj(
        io.BytesIO(file_bytes),
        settings.R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return f"..."

async def upload_to_r2(file_bytes: bytes, key: str, content_type: str = "image/jpeg") -> Optional[str]:
    ...
    url = await loop.run_in_executor(None, partial(_upload_sync, file_bytes, key, content_type))
```

**Telegram PDF detection:**
```python
if update.message.document:
    doc = update.message.document
    mime = doc.mime_type or "application/octet-stream"
    file = await doc.get_file()
else:  # photo
    photo = update.message.photo[-1]
    mime = "image/jpeg"
    file = await photo.get_file()
file_bytes = await file.download_as_bytearray()
```

---

## 5. Bot Notification to Driver — Proven Pattern

`src/web/panel.py` lines 25-40 — `notify_driver_expense_decision()` already works:
```python
async def notify_driver_trip_assignment(driver_tg_id: int, trip: Trip) -> None:
    from src.main import ptb_app  # deferred import
    if ptb_app is None:
        return
    try:
        text = f"Вам назначен рейс #{trip.id}: {trip.route_details}\nГруз: {trip.load_info}\nКлиент: {trip.client_name}"
        await ptb_app.bot.send_message(chat_id=driver_tg_id, text=text)
    except Exception as e:
        logger.error(f"Failed to notify driver: {e}")
```

Copy this pattern in `panel.py` — add `notify_driver_trip_assignment()` alongside existing `notify_driver_expense_decision()`.

---

## 6. Web Panel — Trip Creation (TRIP-01)

**Form fields:** vehicle_id (select), driver_id (select), route_from, route_to, load_info, client_name, planned_departure, planned_arrival.

**Pattern:** Use existing HTMX pattern from expenses.html. Trip creation is a standard POST form (full page redirect on success, no HTMX needed — too complex for HTMX).

**Routes needed:**
```
GET  /panel/trips              — trip list with filters (driver_id, vehicle_id, status, date range)
GET  /panel/trips/create       — creation form
POST /panel/trips/create       — save + send driver notification
GET  /panel/trips/{id}         — detail view: expenses, documents, locations
GET  /panel/fleet              — fleet dashboard (replaces simple drivers list for FLEET-01/02)
```

---

## 7. Trip History/Search — SQLAlchemy Patterns

```python
# TRIP-06: filtered trip list
q = select(Trip).options(
    selectinload(Trip.driver),
    selectinload(Trip.vehicle),
).order_by(Trip.created_at.desc())

if driver_id:
    q = q.where(Trip.driver_id == int(driver_id))
if vehicle_id:
    q = q.where(Trip.vehicle_id == int(vehicle_id))
if status:
    q = q.where(Trip.status == status)

# TRIP-07: trip detail with all related data
q = select(Trip).options(
    selectinload(Trip.driver),
    selectinload(Trip.vehicle),
    selectinload(Trip.expenses),
    selectinload(Trip.documents),  # TripDocument relationship
).where(Trip.id == trip_id)
```

---

## 8. Fleet Dashboard — FLEET-01 + FLEET-02

Single query to get all vehicles with current trip+driver:
```python
q = select(Vehicle).options(
    selectinload(Vehicle.drivers),
    selectinload(Vehicle.trips).selectinload(Trip.driver),
)
# Then in Python: find the ACTIVE trip for each vehicle
active_trip = next((t for t in vehicle.trips if t.status == TripStatus.ACTIVE), None)
```

Or more efficiently with a lateral join. Given small fleet size (<100), Python-side filtering is fine.

---

## 9. Wave Decomposition

| Wave | Plans | Content |
|------|-------|---------|
| 1 | 03-01 | Schema migration (Trip new cols + TripDocument table) |
| 2 | 03-02, 03-03 | trip_opening.py refactor (TRIP-03) + r2.py + trip_closing.py update (TRIP-04, TRIP-05) |
| 3 | 03-04 | Web panel trip creation + notification (TRIP-01, TRIP-02) |
| 4 | 03-05 | Trip history, detail view, fleet dashboard (TRIP-06, TRIP-07, FLEET-01, FLEET-02) |

**Note:** Plans 03-02 and 03-03 can run in parallel — 03-02 modifies `trip_opening.py`, 03-03 modifies `trip_closing.py` and `r2.py`. No file overlap.

---

## 10. Key Decisions

1. **trip_opening.py**: Complete rewrite — driver no longer enters route/cargo (dispatcher does). Bot only confirms departure + odometer.
2. **TripDocument**: New table needed for durable multi-doc storage. `Trip.closing_document_id` stays as legacy.
3. **Vehicle.status**: Must be updated in both trip open (→ ON_TRIP) and trip close (→ AVAILABLE).
4. **r2.py**: Add `content_type` parameter to `upload_to_r2()` — keep backward compat with default `"image/jpeg"`.
5. **Delivery status**: Store as `Trip.delivery_status` string (DELIVERED/PARTIAL/FAILED) — no separate enum model needed.
6. **Fleet dashboard**: Separate `/panel/fleet` route, not the same as `/panel/drivers`.

---
*Research complete. Ready for planner.*
