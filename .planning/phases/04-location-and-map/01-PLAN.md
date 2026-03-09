---
id: "04-01"
title: "Map Backend: /panel/map route + fleet location query"
phase: 4
wave: 1
goal: "Implement FastAPI routes for the fleet map page and HTMX marker refresh endpoint"
autonomous: true
depends_on: []
files_modified:
  - src/web/panel.py
  - src/web/templates/base.html
---

# Plan 04-01: Map Backend

## Goal
Add two FastAPI routes to the web panel:
1. `GET /panel/map` — renders the Leaflet map page with initial markers
2. `GET /panel/map/markers` — returns JSON of current truck positions for HTMX polling

## Context
- LOC-01 (bot location capture) already complete in `antigravity_modules/location_flow.py`
- `LocationUpdate` model + table already exist (migration `102c50087403_add_location_model.py`)
- Auth pattern: use existing `get_current_user_from_cookie` dependency
- Target requirements: LOC-02, LOC-04

## Tasks

### Task 1: Fleet location CRUD query
Add a helper inside panel.py that queries the latest LocationUpdate per active-trip driver:

```sql
SELECT DISTINCT ON (lu.driver_id)
  lu.latitude, lu.longitude, lu.created_at,
  d.name as driver_name,
  v.license_plate
FROM locations lu
JOIN drivers d ON d.id = lu.driver_id
JOIN trips t ON t.driver_id = d.id AND t.status = 'ACTIVE'
JOIN vehicles v ON v.id = t.vehicle_id
ORDER BY lu.driver_id, lu.created_at DESC
```

Return list of dicts: `{lat, lng, driver_name, plate, updated_at}`.

### Task 2: GET /panel/map route
- Requires auth (get_current_user_from_cookie)
- Calls fleet location query
- Renders `map.html` with `markers=markers_list`

### Task 3: GET /panel/map/markers route
- Requires auth
- Calls same fleet location query
- Returns `JSONResponse` with list of marker dicts
- `updated_at` serialized as ISO string

### Task 4: Add "Карта" to base.html navbar
- Insert `<a href="/panel/map">Карта</a>` between "Парк" and "Водители" links

## Acceptance Criteria
- `GET /panel/map` returns HTTP 200 for authenticated dispatcher
- `GET /panel/map/markers` returns valid JSON array
- Unauthenticated → redirect to `/panel/login`
- Empty markers list (no active trips) → no crash, returns `[]`
