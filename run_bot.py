import asyncio
import logging
from src.bot.bot_app import create_bot_app

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    app = create_bot_app()
    logger.info("Starting bot in polling mode...")
    app.run_polling()

if __name__ == "__main__":
    main()
