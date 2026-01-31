import logging
from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from .config import Config
from .utils.logging import setup_logging
from .handlers import admin, filters
from .database.models import Base
from .database.repo import Repository

from .resources.locales import lang

logger = logging.getLogger(__name__)

async def main():
    setup_logging()
    
    # Database initialization
    engine = create_async_engine(Config.DB_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        

    # Bot setup
    bot = Bot(token=Config.BOT_TOKEN)
    dp = Dispatcher()
    
    # Middleware: Inject Repository into handlers
    @dp.message.middleware
    async def db_middleware(handler, event, data):
        async with async_session() as session:
            data['repo'] = Repository(session)
            return await handler(event, data)

    dp.include_router(admin.router)
    dp.include_router(filters.router)
    
    logger.info(lang("bot_started"))
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)