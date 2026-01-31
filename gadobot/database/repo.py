from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from .models import Warn, ChatSettings, Blacklist, CustomFilter, User

class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Warns ---
    async def add_warn(self, chat_id: int, user_id: int) -> int:
        result = await self.session.execute(
            select(Warn).where(Warn.chat_id == chat_id, Warn.user_id == user_id)
        )
        warn = result.scalar_one_or_none()
        if not warn:
            warn = Warn(chat_id=chat_id, user_id=user_id, count=1)
            self.session.add(warn)
        else:
            warn.count += 1
        await self.session.commit()
        return warn.count

    async def remove_warn(self, chat_id: int, user_id: int):
        # Decrement or delete? Original logic deleted on 0, but usually removing a warn decreases count
        result = await self.session.execute(
            select(Warn).where(Warn.chat_id == chat_id, Warn.user_id == user_id)
        )
        warn = result.scalar_one_or_none()
        if warn:
            if warn.count > 1:
                warn.count -= 1
            else:
                await self.session.delete(warn)
            await self.session.commit()

    async def reset_warns(self, chat_id: int, user_id: int):
        await self.session.execute(
            delete(Warn).where(Warn.chat_id == chat_id, Warn.user_id == user_id)
        )
        await self.session.commit()

    async def get_warns(self, chat_id: int, user_id: int) -> int:
        result = await self.session.execute(
            select(Warn.count).where(Warn.chat_id == chat_id, Warn.user_id == user_id)
        )
        return result.scalar_one_or_none() or 0

    # --- Settings ---
    async def set_warn_limit(self, chat_id: int, limit: int):
        result = await self.session.execute(select(ChatSettings).where(ChatSettings.chat_id == chat_id))
        settings = result.scalar_one_or_none()
        if not settings:
            settings = ChatSettings(chat_id=chat_id, warn_limit=limit)
            self.session.add(settings)
        else:
            settings.warn_limit = limit
        await self.session.commit()

    async def get_warn_limit(self, chat_id: int) -> int:
        result = await self.session.execute(select(ChatSettings.warn_limit).where(ChatSettings.chat_id == chat_id))
        return result.scalar_one_or_none() or 3

    # --- Blacklist ---
    async def add_blacklist(self, chat_id: int, user_id: int):
        exists = await self.session.execute(select(Blacklist).where(Blacklist.chat_id == chat_id, Blacklist.user_id == user_id))
        if not exists.scalar_one_or_none():
            self.session.add(Blacklist(chat_id=chat_id, user_id=user_id))
            await self.session.commit()

    async def remove_blacklist(self, chat_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            delete(Blacklist).where(Blacklist.chat_id == chat_id, Blacklist.user_id == user_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def get_blacklist(self, chat_id: int) -> list[int]:
        result = await self.session.execute(select(Blacklist.user_id).where(Blacklist.chat_id == chat_id))
        return list(result.scalars().all())

    # --- Filters ---
    async def add_filter(self, chat_id: int, trigger: str, response: str, file_id=None, file_type=None):
        self.session.add(CustomFilter(chat_id=chat_id, trigger=trigger, response=response, file_id=file_id, file_type=file_type))
        await self.session.commit()

    async def remove_filter(self, chat_id: int, trigger: str) -> bool:
        result = await self.session.execute(
            delete(CustomFilter).where(CustomFilter.chat_id == chat_id, CustomFilter.trigger == trigger)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def remove_all_filters(self, chat_id: int):
        await self.session.execute(delete(CustomFilter).where(CustomFilter.chat_id == chat_id))
        await self.session.commit()

    async def get_filters(self, chat_id: int):
        result = await self.session.execute(
            select(CustomFilter).where(CustomFilter.chat_id == chat_id)
        )
        return result.scalars().all()