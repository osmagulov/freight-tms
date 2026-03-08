---
phase: 01-infrastructure-and-foundation
plan: 02
type: execute
wave: 2
depends_on:
  - "01-01"
files_modified:
  - src/main.py
  - src/bot/bot_app.py
autonomous: true
requirements:
  - INFRA-01
  - REG-01
  - REG-02

must_haves:
  truths:
    - "POST /telegram receives Telegram updates and processes them without error"
    - "GET / returns 200 OK (healthcheck passes)"
    - "Driver can complete /start → language → name → phone → vehicle registration flow end to end"
    - "receive_vehicle() links driver.vehicle_id = vehicle.id before committing"
    - "PTB application shuts down cleanly when FastAPI receives SIGTERM"
  artifacts:
    - path: "src/main.py"
      provides: "FastAPI app with lifespan, /telegram POST endpoint, healthcheck"
      contains: "asynccontextmanager"
    - path: "src/bot/bot_app.py"
      provides: "create_bot_app() with handler registration; receive_vehicle() with FK link fix"
      contains: "link_driver_to_vehicle"
  key_links:
    - from: "src/main.py"
      to: "src/bot/bot_app.py"
      via: "create_bot_app() called in lifespan, handlers added to ptb_app"
      pattern: "create_bot_app"
    - from: "/telegram POST endpoint"
      to: "ptb_app.process_update()"
      via: "Update.de_json() then process_update()"
      pattern: "process_update"
    - from: "src/bot/bot_app.py receive_vehicle()"
      to: "src/db/crud.link_driver_to_vehicle()"
      via: "await link_driver_to_vehicle(session, driver.id, vehicle.id)"
      pattern: "link_driver_to_vehicle"
---

<objective>
Rewrite src/main.py to use the FastAPI lifespan pattern with PTB webhook integration, and fix the critical driver-vehicle FK bug in receive_vehicle(). Together these deliver a working single-process bot-plus-API server.

Purpose: This is the primary integration plan — PTB running inside FastAPI in one process, webhook-driven, with the registration flow producing properly linked driver+vehicle records.
Output: Functional src/main.py with lifespan + /telegram route; bot_app.py with receive_vehicle() fix.
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
@src/main.py
@src/bot/bot_app.py
@src/core/config.py
@src/db/crud.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rewrite src/main.py with lifespan pattern and PTB webhook endpoint</name>
  <files>src/main.py</files>
  <action>
  Replace the entire contents of src/main.py. The current file uses deprecated @app.on_event("startup") and @app.on_event("shutdown") — remove both completely. Do NOT use @app.on_event anywhere.

  Write the new version:

  ```python
  import logging
  from contextlib import asynccontextmanager
  from http import HTTPStatus
  from pathlib import Path

  from fastapi import FastAPI, Request, Response
  from telegram import Update
  from telegram.ext import Application, PicklePersistence

  from src.core.config import settings
  from src.bot.bot_app import register_handlers

  logging.basicConfig(level=logging.INFO)
  logger = logging.getLogger(__name__)

  ptb_app: Application = None

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      global ptb_app

      # Use Railway Volume path if available, fallback to local /data
      import os
      volume_mount = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/data")
      persistence_path = Path(volume_mount) / "bot_persistence.pkl"
      persistence_path.parent.mkdir(parents=True, exist_ok=True)

      persistence = PicklePersistence(filepath=persistence_path)

      ptb_app = (
          Application.builder()
          .token(settings.TELEGRAM_BOT_TOKEN)
          .updater(None)        # Disable polling — webhook mode only
          .persistence(persistence)
          .build()
      )

      # Register all bot handlers
      register_handlers(ptb_app)

      async with ptb_app:
          if settings.WEBHOOK_URL:
              await ptb_app.bot.set_webhook(
                  url=f"{settings.WEBHOOK_URL}/telegram",
                  allowed_updates=Update.ALL_TYPES,
              )
              logger.info(f"Webhook set to {settings.WEBHOOK_URL}/telegram")
          else:
              logger.warning("WEBHOOK_URL not set — webhook not registered. Set WEBHOOK_URL env var on Railway.")

          await ptb_app.start()
          yield
          await ptb_app.stop()

  app = FastAPI(title="Freight TMS API", lifespan=lifespan)

  @app.get("/")
  async def healthcheck():
      return {"status": "ok", "message": "Freight TMS API is running"}

  @app.post("/telegram")
  async def telegram_webhook(request: Request):
      data = await request.json()
      update = Update.de_json(data, ptb_app.bot)
      await ptb_app.process_update(update)
      return Response(status_code=HTTPStatus.OK)
  ```

  Key decisions:
  - `.updater(None)` disables polling (critical — polling and webhook cannot coexist)
  - `register_handlers(ptb_app)` is the new function name in bot_app.py (see Task 2)
  - PicklePersistence is created here in main.py, NOT in bot_app.py, so bot_app.py stays testable
  - `persistence_path.parent.mkdir(parents=True, exist_ok=True)` prevents crash if /data doesn't exist locally
  - WEBHOOK_URL absence is logged as warning, not an error — allows local development without Railway
  </action>
  <verify>
  Run: `python -c "from src.main import app; print('ok')"` — should import without error.
  Run: `python -c "import inspect; from src.main import lifespan; print('lifespan' in inspect.getsource(lifespan))"` — should print True.
  Grep: `grep -n "on_event" src/main.py` — must return empty (no deprecated decorators).
  Grep: `grep -n "updater(None)" src/main.py` — must match.
  </verify>
  <done>src/main.py has no @app.on_event. lifespan context manager creates PicklePersistence, builds ptb_app with .updater(None), sets webhook, starts ptb_app. POST /telegram endpoint calls ptb_app.process_update(). GET / returns healthcheck dict.</done>
</task>

<task type="auto">
  <name>Task 2: Refactor bot_app.py — add register_handlers(), fix receive_vehicle() FK bug</name>
  <files>src/bot/bot_app.py</files>
  <action>
  Make two targeted changes to src/bot/bot_app.py:

  **Change 1: Add import for link_driver_to_vehicle**
  Add to the existing imports at the top:
  ```python
  from src.db.crud import get_driver_by_tg_id, create_driver, get_vehicle_by_plate, create_vehicle, update_driver_language, link_driver_to_vehicle
  ```
  (link_driver_to_vehicle is appended to the existing import line)

  **Change 2: Fix receive_vehicle() to link driver→vehicle**
  Find the `receive_vehicle()` function. Currently it creates driver and vehicle separately with the comment "MVP just registers them". Replace the async with block body with:

  ```python
  async with async_session() as session:
      # Create or look up vehicle by license plate
      vehicle = await get_vehicle_by_plate(session, plate)
      if not vehicle:
          vehicle = await create_vehicle(session, plate)

      # Create driver record
      lang = context.user_data.get('lang', 'ru')
      driver = await create_driver(session, tg_id=tg_id, name=name, phone=phone, language=lang)

      # Link driver to vehicle (fixes REG-02: driver.vehicle_id FK was previously never set)
      await link_driver_to_vehicle(session, driver.id, vehicle.id)
  ```

  **Change 3: Extract register_handlers() function and update create_bot_app()**
  Add a new top-level function below the cancel_handler function and BEFORE create_bot_app():

  ```python
  def register_handlers(app: Application) -> None:
      """Register all ConversationHandlers and command handlers onto a PTB Application instance.
      Called from main.py lifespan so that PicklePersistence is already attached to the app."""
      app.add_handler(CommandHandler("menu", menu_command_handler))

      registration_conv = ConversationHandler(
          entry_points=[CommandHandler("start", start_handler)],
          states={
              AWAITING_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_language)],
              AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
              AWAITING_PHONE: [
                  MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), receive_phone)
              ],
              AWAITING_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_vehicle)]
          },
          fallbacks=[CommandHandler("cancel", cancel_handler)],
          name="registration",
          persistent=True,
      )

      app.add_handler(registration_conv)
      app.add_handler(get_trip_conversation_handler())
      app.add_handler(get_expense_conversation_handler())
      app.add_handler(get_location_conversation_handler())
      app.add_handler(get_trip_closing_conversation_handler())
  ```

  Update create_bot_app() to use register_handlers() for consistency (for local testing without persistence):
  ```python
  def create_bot_app() -> Application:
      """Build a standalone PTB Application for local testing (polling mode, no persistence)."""
      app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
      register_handlers(app)
      return app
  ```

  Note: `persistent=True` is added to registration_conv here. The other 4 ConversationHandlers (trip_opening, expense_flow, location_flow, trip_closing) will get `persistent=True` in Plan 03.
  </action>
  <verify>
  Run: `python -c "from src.bot.bot_app import register_handlers, create_bot_app; print('ok')"` — imports without error.
  Grep: `grep -n "link_driver_to_vehicle" src/bot/bot_app.py` — must match (appears in import and in receive_vehicle body).
  Grep: `grep -n "persistent=True" src/bot/bot_app.py` — must match registration_conv.
  Grep: `grep -n "MVP just registers" src/bot/bot_app.py` — must return empty (old comment removed).
  </verify>
  <done>bot_app.py imports link_driver_to_vehicle. receive_vehicle() calls link_driver_to_vehicle(session, driver.id, vehicle.id). register_handlers() function exists and registers all handlers. registration_conv has persistent=True. create_bot_app() delegates to register_handlers().</done>
</task>

</tasks>

<verification>
1. `python -c "from src.main import app, lifespan"` — no ImportError
2. `grep "on_event" src/main.py` — returns empty
3. `grep "updater(None)" src/main.py` — matches
4. `grep "link_driver_to_vehicle" src/bot/bot_app.py` — matches in import and receive_vehicle body
5. `grep "persistent=True" src/bot/bot_app.py` — matches
6. `python -c "from src.bot.bot_app import register_handlers"` — imports cleanly
</verification>

<success_criteria>
- src/main.py uses lifespan context manager (no @app.on_event anywhere)
- PTB built with .updater(None) and PicklePersistence pointing to /data/bot_persistence.pkl
- POST /telegram endpoint exists and calls ptb_app.process_update()
- receive_vehicle() calls link_driver_to_vehicle() so driver.vehicle_id is set
- register_handlers() extracted so main.py can attach handlers to a persistence-equipped app
- registration ConversationHandler has persistent=True
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-and-foundation/01-02-SUMMARY.md`
</output>
