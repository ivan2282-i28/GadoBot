import logging
import os
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv


from commands import register_handlers, setup_bot_commands
from db import init_db


logger = logging.getLogger(__name__)


async def startup(bot: Bot) -> None:
    await init_db()
    # Configure bot command list for private and group chats
    await setup_bot_commands(bot)


async def main() -> None:
    load_dotenv()

    api_token = os.getenv("BOT_TOKEN")
    if not api_token:
        raise ValueError("BOT_TOKEN environment variable not set")

    # Ensure logs directory exists
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "bot.log")

    # Root logger configuration (no DEBUG in logs)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # File handler with rotation: max 5 files, 5 MB each, all levels except INFO
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    # Store only INFO and above in log file
    file_handler.setLevel(logging.INFO)

    class NoInfoFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
            return record.levelno != logging.INFO

    file_handler.addFilter(NoInfoFilter())
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Console handler: only errors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Clear existing handlers to avoid duplication on reload
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    bot = Bot(token=api_token)
    dp = Dispatcher()

    # Register all command and message handlers
    register_handlers(bot, dp, api_token)

    await startup(bot)

    # Explicit console info about startup (other INFO logs go only to file)
    print("Bot started")

    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot down")
