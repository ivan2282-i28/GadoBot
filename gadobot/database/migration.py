import os
import sqlite3
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Warn, Blacklist, ChatSettings, CustomFilter, User

logger = logging.getLogger(__name__)

async def migrate_legacy_db(session: AsyncSession, old_db_path: str):
    '''
    Reads from the legacy 'gado.db' SQLite file and populates the new SQLAlchemy DB.
    Refactored to match the provided db.py schema.
    '''
    if not os.path.exists(old_db_path):
        logger.info(f"No legacy DB found at {old_db_path}, skipping migration.")
        return

    logger.info("Starting legacy DB migration...")
    
    try:
        conn = sqlite3.connect(old_db_path)
        cursor = conn.cursor()

        # 1. Migrate Warns (Schema: chat_id, user_id, count)
        try:
            rows = cursor.execute("SELECT chat_id, user_id, count FROM warns").fetchall()
            for r in rows:
                session.add(Warn(chat_id=r[0], user_id=r[1], count=r[2]))
        except Exception:
            logger.warning("Migration: 'warns' table skipped")

        # 2. Migrate Blacklist (Schema: chat_id, user_id)
        try:
            rows = cursor.execute("SELECT chat_id, user_id FROM blacklist").fetchall()
            for r in rows:
                session.add(Blacklist(chat_id=r[0], user_id=r[1]))
        except Exception:
            logger.warning("Migration: 'blacklist' table skipped")

        # 3. Migrate Warn Limits (Schema: chat_id, warn_limit)
        try:
            rows = cursor.execute("SELECT chat_id, warn_limit FROM warn_limits").fetchall()
            for r in rows:
                session.add(ChatSettings(chat_id=r[0], warn_limit=r[1]))
        except Exception:
            logger.warning("Migration: 'warn_limits' table skipped")

        # 4. Migrate Filters (Schema: chat_id, trigger, response, file_id, file_type)
        try:
            rows = cursor.execute("SELECT chat_id, trigger, response, file_id, file_type FROM filters").fetchall()
            for r in rows:
                session.add(CustomFilter(chat_id=r[0], trigger=r[1], response=r[2], file_id=r[3], file_type=r[4]))
        except Exception:
            logger.warning("Migration: 'filters' table skipped")
            
        # 5. Migrate Users (Schema: user_id, lang)
        try:
            # Note: old db has 'rc_cd' but we might not need it in new stricture, or add if needed
            rows = cursor.execute("SELECT user_id, lang FROM users").fetchall()
            for r in rows:
                session.add(User(user_id=r[0], lang=r[1]))
        except Exception:
            logger.warning("Migration: 'users' table skipped")

        await session.commit()
        conn.close()
        
        # Rename old DB
        os.rename(old_db_path, old_db_path + ".migrated")
        logger.info("Migration complete. Legacy DB renamed to .migrated")

    except Exception as e:
        logger.error(f"Migration failed: {e}")