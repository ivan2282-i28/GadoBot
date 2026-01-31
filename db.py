import aiosqlite
from typing import List, Tuple, Optional

DB_PATH = "gado.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            trigger TEXT NOT NULL,
            response TEXT NOT NULL,
            file_id TEXT,
            file_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            username TEXT,
            lang TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, user_id)
        )
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS warns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, user_id)
        )
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS warn_limits (
            chat_id INTEGER PRIMARY KEY,
            warn_limit INTEGER NOT NULL
        )
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            rc_cd INTEGER DEFAULT 0,
            lang TEXT NOT NULL DEFAULT 'eng',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Migration: ensure 'lang' column exists in users table for old DBs
        cursor = await conn.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        column_names = {col[1] for col in columns}
        if "lang" not in column_names:
            await conn.execute("ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'eng'")

        await conn.commit()


# Chats
async def register_chat(chat_id: int, name: str, username: Optional[str]):
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT name, username, lang FROM chats WHERE chat_id = ?',
            (chat_id,)
        )
        chater = await cursor.fetchone()

        if not chater:
            await conn.execute(
                'INSERT INTO chats (chat_id, name, username, lang) VALUES (?, ?, ?, ?)',
                (chat_id, name, username, "ru")
            )
        else:
            await conn.execute(
                'UPDATE chats SET name = ?, username = ? WHERE chat_id = ?',
                (name, username, chat_id)
            )
        await conn.commit()


async def get_chat(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT name, username, lang FROM chats WHERE chat_id = ?',
            (chat_id,)
        )
        return await cursor.fetchone()


async def get_all_chats():
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT chat_id, name, username, lang FROM chats',
            ()
        )
        return await cursor.fetchall()


# Users
async def register_user(user_id: int, lang: str = "eng"):
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT user_id FROM users WHERE user_id = ?',
            (user_id,)
        )
        user = await cursor.fetchone()

        if not user:
            await conn.execute(
                'INSERT INTO users (user_id, rc_cd, lang) VALUES (?, ?, ?)',
                (user_id, 0, lang)
            )
            await conn.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT rc_cd FROM users WHERE user_id = ?',
            (user_id,)
        )
        return await cursor.fetchone()



async def get_user_lang(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT lang FROM users WHERE user_id = ?',
            (user_id,)
        )
        row = await cursor.fetchone()
        if row and row[0]:
            return row[0]
        return "eng"

async def set_user_lang(user_id: int, lang: str) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        query = f"UPDATE users SET lang = '{lang}' WHERE user_id = {user_id}"
        await conn.executescript(query)
        await conn.commit()


# Filters
async def add_filter(chat_id: int, trigger: str, response: str, file_id: Optional[str] = None, file_type: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            'INSERT INTO filters (chat_id, trigger, response, file_id, file_type) VALUES (?, ?, ?, ?, ?)',
            (chat_id, trigger, response, file_id, file_type)
        )
        await conn.commit()


async def get_chat_filters(chat_id: int) -> List[Tuple]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT trigger, response, file_id, file_type FROM filters WHERE chat_id = ?',
            (chat_id,)
        )
        return await cursor.fetchall()


async def remove_filter(chat_id: int, trigger: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'DELETE FROM filters WHERE chat_id = ? AND trigger = ?',
            (chat_id, trigger)
        )
        affected = cursor.rowcount
        await conn.commit()
        return affected > 0


async def remove_all_filters(chat_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'DELETE FROM filters WHERE chat_id = ?',
            (chat_id,)
        )
        affected = cursor.rowcount
        await conn.commit()
        return affected


# Blacklist
async def add_to_blacklist(chat_id: int, user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            'INSERT OR IGNORE INTO blacklist (chat_id, user_id) VALUES (?, ?)',
            (chat_id, user_id),
        )
        await conn.commit()


async def remove_from_blacklist(chat_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'DELETE FROM blacklist WHERE chat_id = ? AND user_id = ?',
            (chat_id, user_id),
        )
        affected = cursor.rowcount
        await conn.commit()
        return affected > 0


async def get_blacklist(chat_id: int) -> List[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT user_id FROM blacklist WHERE chat_id = ?',
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


# Warns
async def add_warn(chat_id: int, user_id: int) -> int:
    """Increment warn counter for user in chat and return new count."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            'INSERT INTO warns (chat_id, user_id, count) VALUES (?, ?, 1) '
            'ON CONFLICT(chat_id, user_id) DO UPDATE SET count = count + 1',
            (chat_id, user_id),
        )
        cursor = await conn.execute(
            'SELECT count FROM warns WHERE chat_id = ? AND user_id = ?',
            (chat_id, user_id),
        )
        row = await cursor.fetchone()
        await conn.commit()
        return row[0] if row else 0


async def remove_warn(chat_id: int, user_id: int) -> int:
    """Decrement warn counter (not below 0) and return new count."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT count FROM warns WHERE chat_id = ? AND user_id = ?',
            (chat_id, user_id),
        )
        row = await cursor.fetchone()
        if not row:
            return 0
        new_count = max(row[0] - 1, 0)
        if new_count == 0:
            await conn.execute(
                'DELETE FROM warns WHERE chat_id = ? AND user_id = ?',
                (chat_id, user_id),
            )
        else:
            await conn.execute(
                'UPDATE warns SET count = ? WHERE chat_id = ? AND user_id = ?',
                (new_count, chat_id, user_id),
            )
        await conn.commit()
        return new_count


async def get_warns(chat_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT count FROM warns WHERE chat_id = ? AND user_id = ?',
            (chat_id, user_id),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def set_warn_limit(chat_id: int, warn_limit: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            'INSERT INTO warn_limits (chat_id, warn_limit) VALUES (?, ?) '
            'ON CONFLICT(chat_id) DO UPDATE SET warn_limit = excluded.warn_limit',
            (chat_id, warn_limit),
        )
        await conn.commit()


async def get_warn_limit(chat_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'SELECT warn_limit FROM warn_limits WHERE chat_id = ?',
            (chat_id,),
        )
        row = await cursor.fetchone()
        # Default warn limit is 3 if not explicitly set for this chat
        return row[0] if row else 3
