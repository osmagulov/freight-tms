from fastapi import FastAPI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Freight TMS API")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Freight TMS API is running"}

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up FastAPI application...")
    # TODO: In the future, start Telegram bot polling or set webhook here
    
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down FastAPI application...")
    # TODO: Clean up resources
