import time
from typing import Optional, List, Tuple

from aiogram import Bot
from aiogram.types import Message

from db import (
    add_filter as db_add_filter,
    get_chat_filters as db_get_chat_filters,
    remove_all_filters as db_remove_all_filters,
    remove_filter as db_remove_filter,
)


def parse_filter_command(text: str) -> tuple:
    if text.startswith('/filter'):
        text = text[len('/filter'):].strip()

    if text.startswith('r"'):
        end_quote = text.find('"', 2)
        if end_quote == -1:
            return None, None

        trigger = text[:end_quote + 1]
        response = text[end_quote + 1:].strip()

        if response.startswith('"'):
            response = response[1:]
        if response.endswith('"'):
            response = response[:-1]

        return trigger, response

    elif text.startswith('"'):
        end_quote = text.find('"', 1)
        if end_quote == -1:
            return None, None

        trigger = text[:end_quote + 1]
        response = text[end_quote + 1:].strip()

        trigger = trigger[1:-1]

        return trigger, response

    else:
        parts = text.split(' ', 1)
        if len(parts) < 2:
            return None, None

        trigger = parts[0]
        response = parts[1]

        return trigger, response


async def add_filter(chat_id: int, trigger: str, response: str, file_id: Optional[str] = None, file_type: Optional[str] = None):
    await db_add_filter(chat_id, trigger, response, file_id, file_type)


async def get_chat_filters(chat_id: int) -> List[Tuple]:
    return await db_get_chat_filters(chat_id)


async def remove_filter(chat_id: int, trigger: str) -> bool:
    return await db_remove_filter(chat_id, trigger)


async def remove_all_filters(chat_id: int) -> int:
    return await db_remove_all_filters(chat_id)


async def send_filter_response(bot: Bot, message: Message, response: str, file_id: Optional[str], file_type: Optional[str]):
    if file_id and file_type:
        if file_type == 'photo':
            await message.reply_photo(file_id, caption=response if response != "Media response" else None)
        elif file_type == 'video':
            await message.reply_video(file_id, caption=response if response != "Media response" else None)
        elif file_type == 'document':
            await message.reply_document(file_id, caption=response if response != "Media response" else None)
        elif file_type == 'animation':
            await message.reply_animation(file_id, caption=response if response != "Media response" else None)
    elif response.startswith("b::"):
        y = response.replace("b::", "", 1)
        timer = None
        if y.endswith("d") and y[:-1].isnumeric():
            timer = 24 * 60 * 60 * int(y[:-1])
        elif y.endswith("h") and y[:-1].isnumeric():
            timer = 60 * 60 * int(y[:-1])
        elif y.endswith("m") and y[:-1].isnumeric():
            timer = 60 * int(y[:-1])

        if timer:
            until_date = int(time.time() + timer)
            await bot.ban_chat_member(message.chat.id, message.from_user.id, until_date=until_date)
    else:
        await message.reply(response)
