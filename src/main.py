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
