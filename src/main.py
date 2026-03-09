import logging
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException as _HTTPException
from fastapi.responses import JSONResponse, RedirectResponse as _RR
from telegram import Update
from telegram.ext import Application, PicklePersistence

from src.core.config import settings
from src.bot.bot_app import register_handlers
from src.services.anomaly import run_anomaly_digest
from src.web.panel import router as panel_router
from src.web.director import router as director_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ptb_app: Application = None
scheduler = AsyncIOScheduler(timezone="UTC")

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

    # Start APScheduler before PTB (independent of bot lifecycle)
    scheduler.add_job(run_anomaly_digest, 'interval', hours=1, id='anomaly_digest')
    scheduler.start()  # NOTE: do NOT await — APScheduler 3.x start() is synchronous

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

    scheduler.shutdown(wait=False)

app = FastAPI(title="Freight TMS API", lifespan=lifespan)
app.include_router(panel_router)
app.include_router(director_router)


@app.exception_handler(_HTTPException)
async def http_exception_handler(request, exc):
    if exc.status_code == 302 and "Location" in exc.headers:
        return _RR(url=exc.headers["Location"], status_code=302)
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})


@app.get("/")
async def healthcheck():
    return {"status": "ok", "message": "Freight TMS API is running"}

@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=HTTPStatus.OK)
