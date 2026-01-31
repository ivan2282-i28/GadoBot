import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    # New DB location
    DB_URL = "sqlite+aiosqlite:///bot.db"
    # Old DB location for migration
    OLD_DB_PATH = "gado.db"

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable not set in .env")