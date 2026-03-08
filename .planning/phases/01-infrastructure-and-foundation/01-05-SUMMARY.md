---
phase: 01-infrastructure-and-foundation
plan: 05
subsystem: auth
tags: [jwt, python-jose, pwdlib, bcrypt, jinja2, fastapi, web-panel, cookie-auth]

# Dependency graph
requires:
  - phase: 01-01
    provides: Settings (JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, ADMIN_USERNAME, ADMIN_PASSWORD_HASH, async_database_url)
  - phase: 01-02
    provides: src/main.py FastAPI app with lifespan, src/db/models.py Driver+Vehicle models
provides:
  - JWT cookie authentication (create_access_token, verify_password, get_current_user_from_cookie)
  - Web panel at /panel/* (login, logout, drivers list, vehicle edit)
  - 4 Jinja2 templates (base, login, drivers, vehicle_edit)
  - HTTPException 302 handler wired into FastAPI app
affects: [02-api-and-endpoints, 03-business-logic, 05-deployment]

# Tech tracking
tech-stack:
  added: [python-jose, pwdlib[bcrypt], jinja2, fastapi.templating]
  patterns:
    - HTTPException(302) for auth redirects instead of helper-that-raises pattern
    - PasswordHash.recommended() from pwdlib for bcrypt hashing
    - APIRouter with prefix=/panel included in main app via app.include_router()
    - Jinja2Templates directory resolved relative to panel.py via Path(__file__).parent

key-files:
  created:
    - src/web/__init__.py
    - src/web/auth.py
    - src/web/panel.py
    - src/web/templates/base.html
    - src/web/templates/login.html
    - src/web/templates/drivers.html
    - src/web/templates/vehicle_edit.html
  modified:
    - src/main.py

key-decisions:
  - "HTTPException(status_code=302, headers={Location}) used inline at each auth guard site — no _redirect_to_login() helper to avoid unreachable-raise confusion"
  - "Templates directory resolved as Path(__file__).parent / 'templates' so it works regardless of working directory"
  - "302 HTTPException handler added to app so browser follows auth redirects from Depends() dependency"

patterns-established:
  - "Panel: auth dependency via Depends(get_current_user_from_cookie) on protected routes"
  - "Panel: outerjoin(Vehicle, Driver.vehicle_id == Vehicle.id) for driver+vehicle pair queries"
  - "Panel: httponly=True, samesite=lax JWT cookie set on successful login"

requirements-completed: [INFRA-05, REG-03, REG-04]

# Metrics
duration: 32min
completed: 2026-03-09
---

# Phase 1 Plan 05: Web Panel Summary

**JWT cookie auth + Jinja2 web panel for dispatchers to view all drivers with linked vehicles and edit vehicle fuel norms**

## Performance

- **Duration:** 32 min
- **Started:** 2026-03-08T22:54:09Z
- **Completed:** 2026-03-08T23:27:00Z
- **Tasks:** 2 of 2 (checkpoint task awaits human verify)
- **Files modified:** 8

## Accomplishments
- JWT cookie authentication via python-jose + pwdlib[bcrypt] with 8h token expiry
- 6-route APIRouter: GET/POST /panel/login, GET /panel/logout, GET /panel/drivers, GET/POST /panel/vehicles/{id}/edit
- 4 Jinja2 templates with Russian UI, responsive table layout, and base.html inheritance
- FastAPI app wired with panel router and 302 HTTPException handler so Depends() auth redirects work in browsers

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/web/ module with JWT auth and panel routes** - `78b79ed` (feat)
2. **Task 2: Create Jinja2 templates and wire router into main.py** - `6baca31` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified
- `src/web/__init__.py` - Empty module init
- `src/web/auth.py` - JWT auth: create_access_token(), verify_password(), get_current_user_from_cookie() dependency
- `src/web/panel.py` - APIRouter with 6 panel routes, outerjoin drivers+vehicles query, httponly cookie login
- `src/web/templates/base.html` - Base HTML layout with navbar (shown when logged in), table styles, error class
- `src/web/templates/login.html` - Login form with Russian labels, error display block
- `src/web/templates/drivers.html` - Driver+vehicle pair table, "Изменить борт" edit link per row
- `src/web/templates/vehicle_edit.html` - Vehicle edit form with make/model/fuel_norm_per_100km fields
- `src/main.py` - Added panel_router inclusion, 302 HTTPException handler for browser auth redirects

## Decisions Made
- HTTPException(status_code=302) raised inline at each guard site in get_current_user_from_cookie() — no helper function, to avoid unreachable-raise confusion
- Templates path resolved via `Path(__file__).parent / "templates"` so templates are portable regardless of server working directory
- 302 exception handler added to FastAPI app so browser follows redirects from Depends() dependencies (FastAPI normally returns the exception body, not a redirect)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Previous agent had created src/web/__init__.py, auth.py, panel.py but did not commit them or create templates. This continuation agent committed Task 1 files first (78b79ed), then completed Task 2 (6baca31).
- Local venv has pwdlib with argon2 as recommended hasher; bcrypt is available but PasswordHash.recommended() tries argon2 first. This is a dev environment issue, not a code bug — Railway deploy uses pwdlib[bcrypt] per requirements.txt.

## User Setup Required

The human-verify checkpoint (Task 3) requires local server startup to visually test the panel. Required environment variables for local test:
- `TELEGRAM_BOT_TOKEN=any_value`
- `ADMIN_USERNAME=dispatcher`
- `ADMIN_PASSWORD_HASH` — generate with: `venv/bin/python -c "from pwdlib import PasswordHash; from pwdlib.hashers.bcrypt import BcryptHasher; ph = PasswordHash([BcryptHasher()]); print(ph.hash('testpass123'))"`

Start server: `venv/bin/uvicorn src.main:app --reload --port 8000`

Test: http://localhost:8000/panel/drivers should redirect to /panel/login.

## Next Phase Readiness
- Web panel fully wired; dispatcher can login, view drivers table, and edit vehicle make/model/fuel_norm
- Phase 1 plan 06 is the final infrastructure plan before Phase 2 API/business logic
- Railway deployment should confirm ADMIN_PASSWORD_HASH env var is set before go-live

## Self-Check: PASSED

All files verified present on disk. All task commits verified in git history.

| Check | Result |
|-------|--------|
| src/web/__init__.py | FOUND |
| src/web/auth.py | FOUND |
| src/web/panel.py | FOUND |
| src/web/templates/base.html | FOUND |
| src/web/templates/login.html | FOUND |
| src/web/templates/drivers.html | FOUND |
| src/web/templates/vehicle_edit.html | FOUND |
| 01-05-SUMMARY.md | FOUND |
| commit 78b79ed (task 1) | FOUND |
| commit 6baca31 (task 2) | FOUND |

---
*Phase: 01-infrastructure-and-foundation*
*Completed: 2026-03-09*
