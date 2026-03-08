---
phase: 01-infrastructure-and-foundation
plan: 05
type: execute
wave: 3
depends_on:
  - "01-01"
  - "01-02"
files_modified:
  - src/web/__init__.py
  - src/web/auth.py
  - src/web/panel.py
  - src/web/templates/base.html
  - src/web/templates/login.html
  - src/web/templates/drivers.html
  - src/web/templates/vehicle_edit.html
  - src/main.py
autonomous: false
requirements:
  - INFRA-05
  - REG-03
  - REG-04

must_haves:
  truths:
    - "GET /panel/login shows a login form"
    - "POST /panel/login with correct ADMIN_USERNAME+password sets httponly JWT cookie and redirects to /panel/drivers"
    - "POST /panel/login with wrong credentials re-renders login.html with error message"
    - "GET /panel/drivers without valid cookie redirects to /panel/login"
    - "GET /panel/drivers with valid cookie shows table of all drivers and their linked vehicle plate"
    - "GET /panel/vehicles/{id}/edit shows a form with make, model, fuel_norm_per_100km fields"
    - "POST /panel/vehicles/{id}/edit saves changes and redirects back to /panel/drivers"
  artifacts:
    - path: "src/web/auth.py"
      provides: "create_access_token(), get_current_user_from_cookie() dependency"
      contains: "get_current_user_from_cookie"
    - path: "src/web/panel.py"
      provides: "APIRouter with /panel routes: login, drivers, vehicle edit"
      contains: "list_drivers"
    - path: "src/web/templates/login.html"
      provides: "Login form HTML"
      contains: "form"
    - path: "src/web/templates/drivers.html"
      provides: "Driver+vehicle table HTML"
      contains: "vehicle"
    - path: "src/web/templates/vehicle_edit.html"
      provides: "Vehicle edit form with make/model/fuel_norm fields"
      contains: "fuel_norm_per_100km"
    - path: "src/main.py"
      provides: "Jinja2 StaticFiles mount + panel router included"
      contains: "include_router"
  key_links:
    - from: "src/web/panel.py /panel/drivers"
      to: "src/db/models.py Driver+Vehicle"
      via: "SQLAlchemy outerjoin(Vehicle, Driver.vehicle_id == Vehicle.id)"
      pattern: "outerjoin.*Vehicle"
    - from: "src/web/panel.py POST /panel/login"
      to: "src/web/auth.py create_access_token()"
      via: "JWT payload {sub: username, role: dispatcher}"
      pattern: "create_access_token"
    - from: "src/web/panel.py GET /panel/drivers"
      to: "src/web/auth.py get_current_user_from_cookie()"
      via: "Depends(get_current_user_from_cookie)"
      pattern: "Depends.*get_current_user_from_cookie"
---

<objective>
Build the complete web panel: JWT cookie authentication, drivers list with vehicle pairs, and vehicle edit form. Uses Jinja2 templates, python-jose JWT, and pwdlib[bcrypt] password verification against env-based credentials.

Purpose: Dispatchers need to see registered drivers and their trucks, and manually edit vehicle details. INFRA-05 requires auth before any panel page. This delivers the full REG-03 + REG-04 + INFRA-05 capability.
Output: src/web/ module with auth.py, panel.py, 4 Jinja2 templates, wired into src/main.py.
</objective>

<execution_context>
@/Users/osmagulov/.claude/get-shit-done/workflows/execute-plan.md
@/Users/osmagulov/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/01-infrastructure-and-foundation/01-RESEARCH.md
@.planning/phases/01-infrastructure-and-foundation/01-01-SUMMARY.md
@src/core/config.py
@src/db/models.py
@src/db/database.py
@src/main.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create src/web/ module with JWT auth and panel routes</name>
  <files>src/web/__init__.py, src/web/auth.py, src/web/panel.py</files>
  <action>
  Create src/web/__init__.py as an empty file.

  Create src/web/auth.py:
  ```python
  # src/web/auth.py
  from datetime import datetime, timedelta
  from typing import Optional

  from fastapi import Cookie, Request
  from fastapi.responses import RedirectResponse
  from jose import JWTError, jwt
  from pwdlib import PasswordHash

  from src.core.config import settings

  password_hash = PasswordHash.recommended()


  def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
      """Encode a JWT with expiry. Default expiry from settings.JWT_EXPIRE_MINUTES (480 = 8h)."""
      to_encode = data.copy()
      expires = expires_minutes or settings.JWT_EXPIRE_MINUTES
      expire = datetime.utcnow() + timedelta(minutes=expires)
      to_encode.update({"exp": expire})
      return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


  def verify_password(plain_password: str, hashed_password: str) -> bool:
      """Verify plain password against stored bcrypt hash."""
      return password_hash.verify(plain_password, hashed_password)


  def get_current_user_from_cookie(access_token: str = Cookie(default=None)) -> dict:
      """FastAPI dependency: extract user dict from JWT cookie. Raise 302 to /panel/login if invalid."""
      if not access_token:
          raise HTTPException(status_code=302, headers={"Location": "/panel/login"})
      try:
          payload = jwt.decode(
              access_token,
              settings.JWT_SECRET_KEY,
              algorithms=[settings.JWT_ALGORITHM],
          )
          username: str = payload.get("sub")
          role: str = payload.get("role", "dispatcher")
          if username is None:
              raise HTTPException(status_code=302, headers={"Location": "/panel/login"})
          return {"username": username, "role": role}
      except JWTError:
          raise HTTPException(status_code=302, headers={"Location": "/panel/login"})
  ```

  Note: Import HTTPException at the top of the file — add `from fastapi import Cookie, HTTPException, Request` (replace the Cookie-only import line). There is no `_redirect_to_login()` helper function. Each guard site raises `HTTPException(status_code=302, headers={"Location": "/panel/login"})` directly to avoid the unreachable-raise confusion of a helper that itself raises.

  Create src/web/panel.py:
  ```python
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
  ```
  </action>
  <verify>
  Run: `python -c "from src.web.auth import create_access_token, get_current_user_from_cookie, verify_password; print('ok')"` — imports without error.
  Run: `python -c "from src.web.panel import router; print(len(router.routes), 'routes')"` — prints 6 routes (login GET, login POST, logout, drivers, vehicle edit GET, vehicle edit POST).
  Grep: `grep -n "outerjoin.*Vehicle\|Vehicle.*outerjoin" src/web/panel.py` — must match.
  Grep: `grep -n "Depends(get_current_user_from_cookie)" src/web/panel.py` — matches on list_drivers, vehicle edit routes.
  Grep: `grep -n "_redirect_to_login" src/web/auth.py` — must NOT match (no such helper function exists).
  </verify>
  <done>src/web/auth.py has create_access_token(), verify_password(), get_current_user_from_cookie() with inline HTTPException raises (no _redirect_to_login helper). src/web/panel.py router has 6 routes: login GET/POST, logout, drivers GET, vehicle edit GET/POST. drivers route uses outerjoin(Vehicle, Driver.vehicle_id == Vehicle.id). All protected routes use Depends(get_current_user_from_cookie).</done>
</task>

<task type="auto">
  <name>Task 2: Create Jinja2 templates and wire router into main.py</name>
  <files>src/web/templates/base.html, src/web/templates/login.html, src/web/templates/drivers.html, src/web/templates/vehicle_edit.html, src/main.py</files>
  <action>
  Create src/web/templates/base.html:
  ```html
  <!DOCTYPE html>
  <html lang="ru">
  <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>{% block title %}Freight TMS{% endblock %}</title>
      <style>
          body { font-family: sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
          .navbar { background: #1a1a2e; color: white; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; }
          .navbar a { color: white; text-decoration: none; }
          .container { max-width: 1100px; margin: 32px auto; padding: 0 16px; }
          table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
          th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #e0e0e0; }
          th { background: #f0f0f0; font-weight: 600; }
          tr:hover { background: #fafafa; }
          .btn { display: inline-block; padding: 6px 14px; background: #1a1a2e; color: white; border-radius: 4px; text-decoration: none; font-size: 14px; }
          .btn:hover { background: #2d2d5e; }
          .error { color: #c0392b; font-size: 14px; margin-top: 8px; }
      </style>
  </head>
  <body>
  {% if request.cookies.get('access_token') %}
  <nav class="navbar">
      <span>Freight TMS</span>
      <div>
          <a href="/panel/drivers">Водители</a>&nbsp;&nbsp;
          <a href="/panel/logout">Выйти</a>
      </div>
  </nav>
  {% endif %}
  <div class="container">
      {% block content %}{% endblock %}
  </div>
  </body>
  </html>
  ```

  Create src/web/templates/login.html:
  ```html
  {% extends "base.html" %}
  {% block title %}Вход — Freight TMS{% endblock %}
  {% block content %}
  <div style="max-width: 380px; margin: 80px auto; background: white; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.15); border-radius: 6px;">
      <h2 style="margin-top: 0;">Вход в систему</h2>
      <form method="post" action="/panel/login">
          <div style="margin-bottom: 16px;">
              <label style="display: block; margin-bottom: 6px; font-size: 14px;">Логин</label>
              <input type="text" name="username" required autofocus
                     style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
          </div>
          <div style="margin-bottom: 20px;">
              <label style="display: block; margin-bottom: 6px; font-size: 14px;">Пароль</label>
              <input type="password" name="password" required
                     style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
          </div>
          {% if error %}
          <p class="error">{{ error }}</p>
          {% endif %}
          <button type="submit" style="width: 100%; padding: 12px; background: #1a1a2e; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;">
              Войти
          </button>
      </form>
  </div>
  {% endblock %}
  ```

  Create src/web/templates/drivers.html:
  ```html
  {% extends "base.html" %}
  {% block title %}Водители — Freight TMS{% endblock %}
  {% block content %}
  <h2>Водители и борта</h2>
  <table>
      <thead>
          <tr>
              <th>ФИО</th>
              <th>Телефон</th>
              <th>Борт (гос. номер)</th>
              <th>Марка</th>
              <th>Модель</th>
              <th>Норма (л/100км)</th>
              <th>Статус</th>
              <th>Действия</th>
          </tr>
      </thead>
      <tbody>
          {% for driver, vehicle in rows %}
          <tr>
              <td>{{ driver.name or '—' }}</td>
              <td>{{ driver.phone or '—' }}</td>
              <td>{{ vehicle.license_plate if vehicle else '—' }}</td>
              <td>{{ vehicle.make if vehicle else '—' }}</td>
              <td>{{ vehicle.model if vehicle else '—' }}</td>
              <td>{{ vehicle.fuel_norm_per_100km if vehicle and vehicle.fuel_norm_per_100km else '—' }}</td>
              <td>{{ driver.status }}</td>
              <td>
                  {% if vehicle %}
                  <a class="btn" href="/panel/vehicles/{{ vehicle.id }}/edit">Изменить борт</a>
                  {% else %}
                  —
                  {% endif %}
              </td>
          </tr>
          {% else %}
          <tr><td colspan="8" style="text-align:center; color:#888;">Водители не зарегистрированы</td></tr>
          {% endfor %}
      </tbody>
  </table>
  {% endblock %}
  ```

  Create src/web/templates/vehicle_edit.html:
  ```html
  {% extends "base.html" %}
  {% block title %}Редактировать борт — Freight TMS{% endblock %}
  {% block content %}
  <h2>Борт: {{ vehicle.license_plate }}</h2>
  <form method="post" action="/panel/vehicles/{{ vehicle.id }}/edit" style="max-width: 480px; background: white; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 6px;">
      <div style="margin-bottom: 16px;">
          <label style="display: block; margin-bottom: 6px; font-size: 14px;">Марка</label>
          <input type="text" name="make" value="{{ vehicle.make or '' }}"
                 style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
      </div>
      <div style="margin-bottom: 16px;">
          <label style="display: block; margin-bottom: 6px; font-size: 14px;">Модель</label>
          <input type="text" name="model" value="{{ vehicle.model or '' }}"
                 style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
      </div>
      <div style="margin-bottom: 20px;">
          <label style="display: block; margin-bottom: 6px; font-size: 14px;">Норма расхода (л/100км)</label>
          <input type="number" name="fuel_norm_per_100km" step="0.1" min="0"
                 value="{{ vehicle.fuel_norm_per_100km or '' }}"
                 style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
      </div>
      <div style="display: flex; gap: 12px;">
          <button type="submit" class="btn" style="padding: 10px 24px; font-size: 15px; border: none; cursor: pointer;">
              Сохранить
          </button>
          <a href="/panel/drivers" style="padding: 10px 24px; color: #555; text-decoration: none; font-size: 15px;">
              Отмена
          </a>
      </div>
  </form>
  {% endblock %}
  ```

  Update src/main.py to include the panel router. Add these imports near the top (after existing imports):
  ```python
  from src.web.panel import router as panel_router
  ```

  Add the router inclusion AFTER `app = FastAPI(title="Freight TMS API", lifespan=lifespan)`:
  ```python
  app.include_router(panel_router)
  ```

  Also add exception handler for 302 HTTPExceptions from the auth dependency so the browser follows the redirect correctly:
  ```python
  from fastapi.responses import RedirectResponse as _RR
  from fastapi.exceptions import HTTPException as _HTTPException

  @app.exception_handler(_HTTPException)
  async def http_exception_handler(request, exc):
      if exc.status_code == 302 and "Location" in exc.headers:
          return _RR(url=exc.headers["Location"], status_code=302)
      from fastapi.responses import JSONResponse
      return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})
  ```
  </action>
  <verify>
  Run: `python -c "from src.main import app; routes = [r.path for r in app.routes]; print([r for r in routes if '/panel' in r])"` — should show /panel/login, /panel/drivers, /panel/logout, /panel/vehicles/{vehicle_id}/edit
  Run: `ls src/web/templates/` — lists base.html, login.html, drivers.html, vehicle_edit.html
  Grep: `grep -n "include_router" src/main.py` — matches.
  Run: `python -c "from src.web.panel import templates; print(templates.directory)"` — prints path to templates dir.
  </verify>
  <done>All 4 templates created with proper Jinja2 inheritance from base.html. panel_router included in FastAPI app. /panel/login, /panel/logout, /panel/drivers, /panel/vehicles/{id}/edit routes all registered. HTTPException 302 handler redirects to login for unauthenticated requests.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Checkpoint: Verify web panel auth and driver list locally</name>
  <action>
  Start the server locally: `uvicorn src.main:app --reload --port 8000`

  Required .env for local test:
  - TELEGRAM_BOT_TOKEN=any_value
  - ADMIN_USERNAME=dispatcher
  - ADMIN_PASSWORD_HASH=(generate with: python -c "from pwdlib import PasswordHash; print(PasswordHash.recommended().hash('testpass123'))")

  Test steps:
  1. Open http://localhost:8000/panel/drivers — should redirect to /panel/login
  2. Enter wrong password — should re-render login with error "Неверный логин или пароль"
  3. Enter correct username (dispatcher) + password (testpass123) — should redirect to /panel/drivers
  4. /panel/drivers shows Freight TMS navbar and driver table (or "Водители не зарегистрированы" if empty)
  5. Click "Выйти" — redirects to /panel/login and requires credentials again
  6. If driver+vehicle exists in DB: table shows name, phone, plate, "Изменить борт" link
  7. Click "Изменить борт", enter make/model/fuel_norm, save → values appear in drivers table
  </action>
  <verify>
  All 7 steps above produce the expected outcome.
  GET /panel/drivers without cookie → 302 to /panel/login (not 500 or 200).
  POST /panel/login with wrong creds → 401 re-render with error message.
  POST /panel/login with correct creds → 302 to /panel/drivers + Set-Cookie header with httponly token.
  </verify>
  <done>Human confirms: login works, auth redirects correctly, drivers table loads, vehicle edit form saves changes. Type "approved" to continue.</done>
</task>

</tasks>

<verification>
1. `python -c "from src.main import app; print(len([r for r in app.routes if '/panel' in getattr(r,'path','')]))"` — prints 5 or more
2. `ls src/web/templates/` — 4 files: base.html, login.html, drivers.html, vehicle_edit.html
3. `grep "include_router" src/main.py` — matches
4. `grep "outerjoin" src/web/panel.py` — matches
5. `grep "httponly=True" src/web/panel.py` — matches
6. Server starts and returns 302 on GET /panel/drivers when no cookie present
</verification>

<success_criteria>
- GET /panel/login renders login form
- POST /panel/login with correct creds sets httponly JWT cookie and redirects to /panel/drivers
- POST /panel/login with wrong creds re-renders login.html with Russian error message
- GET /panel/drivers without cookie → 302 to /panel/login
- GET /panel/drivers with cookie → shows driver+vehicle table with outerjoin query
- GET/POST /panel/vehicles/{id}/edit lets dispatcher save make, model, fuel_norm_per_100km
- Human checkpoint passed
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-and-foundation/01-05-SUMMARY.md`
</output>
