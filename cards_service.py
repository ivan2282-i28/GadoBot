import os
import random
import logging
from typing import Dict, List, Tuple, Optional, Union

from aiogram import Bot, types
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import (
    add_card,
    delete_card_row,
    get_duplicate_cards,
    get_user_cards,
    update_card,
)

logger = logging.getLogger(__name__)

# Cards storage (kept exactly as in main.py to preserve behavior)
cards: Dict[int, Tuple[int, str, str]] = {
    1: (6, "Тыгыдун\nСам создатель бота", "./cards/tigidun.png"),
    3: (4, "назови", "cards/nazovi.png"),
    4: (4, "пернулканик", "cards/pernelkanic.jpg"),
    5: (5, "Флоппи картачка", "cards/flopi.jpg"),
    6: (5, "Ротен Хуманите", "cards/rotor.jpg"),
    7: (4, "Силли фембой\n@Ink_dev", "cards/inkdev.jpg"),
    8: (4, "Клоки (спонсор флоппи картачки)", "cards/kloki.png"),
    9: (4, "Злойтера", "cards/systemdboot.jpg"),
    10: (4, "Андрев Линолиум", "cards/linolium.jpg"),
    11: (4, "FB2 _ZaZuZaZi_\n@Flesxka", "cards/IOR.png"),
    12: (4, "Рефакторатор гадабота\n@faustyu", "cards/IOR.png"),
    13: (6, "GadoBot\nGBTP: Transmission failed, reason: remote server dropped connection, error: RDC","cards/rotor.jpg"),
    14: (0, "Null")
}

# Pagination state per user
user_pagination: Dict[int, Dict[str, Union[int, List[int]]]] = {}


async def add_user_card(user_id: int, card_id: int) -> int:
    """Add a card to user's collection and re-roll if it's a duplicate.

    Behavior preserved from original main.py implementation.
    """
    # Check if user already has this card
    user_cards = await get_user_cards(user_id)
    if card_id in user_cards:
        # Insert duplicate card
        await add_card(user_id, card_id)

        # Determine available cards to re-roll
        all_card_ids = list(cards.keys())
        available_cards = [c for c in all_card_ids if c not in user_cards]

        if available_cards:
            new_card_id = random.choice(available_cards)
            # Reuse DB helper logic: re-fetch duplicates and update last one for this user
            # This approximates original behavior where last inserted duplicate is updated
            duplicates = await get_duplicate_cards()
            for dup_id, dup_user_id, _ in duplicates:
                if dup_user_id == user_id:
                    await update_card(dup_id, new_card_id)
                    return new_card_id
            return card_id
        else:
            # User has all cards, keep duplicate
            return card_id

    # Card is not a duplicate, add normally
    await add_card(user_id, card_id)
    return card_id


async def get_user_unique_cards(user_id: int) -> List[int]:
    """Get all unique card IDs that user has.

    Uses DB helper to keep ordering and uniqueness.
    """
    return await get_user_cards(user_id)


async def check_and_reroll_duplicate_cards() -> int:
    """Check for duplicate cards and re-roll them to unique ones.

    Logic matches original implementation.
    """
    duplicates = await get_duplicate_cards()
    rerolled_count = 0

    for dup_id, user_id, original_card_id in duplicates:
        user_unique_cards = await get_user_cards(user_id)
        all_card_ids = list(cards.keys())
        available_cards = [c for c in all_card_ids if c not in user_unique_cards]

        if available_cards:
            new_card_id = random.choice(available_cards)
            await update_card(dup_id, new_card_id)
            rerolled_count += 1
            logger.info(
                f"Re-rolled duplicate card {original_card_id} to {new_card_id} for user {user_id}"
            )
        else:
            await delete_card_row(dup_id)
            logger.info(
                f"Deleted duplicate card {original_card_id} for user {user_id} (all cards collected)"
            )

    if rerolled_count > 0:
        logger.info(f"Re-rolled {rerolled_count} duplicate cards")

    return rerolled_count


async def send_card_with_image(bot: Bot, chat_id: int, card_data: tuple, caption: Optional[str] = None):
    """Send a card with its image (same behavior as before)."""
    rarity, name, image_path = card_data

    if not caption:
        caption = f"🎴 {name}\nRarity: {rarity}"

    try:
        possible_paths = [
            image_path,
            f"./{image_path}",
            f"./cards/{os.path.basename(image_path)}",
            f"cards/{os.path.basename(image_path)}",
            os.path.join("cards", os.path.basename(image_path)),
            os.path.join("./cards", os.path.basename(image_path)),
        ]

        actual_path = None
        for path in possible_paths:
            if os.path.exists(path):
                actual_path = path
                break

        if actual_path:
            logger.info(f"Sending card image from: {actual_path}")
            input_file = FSInputFile(actual_path)
            await bot.send_photo(chat_id, input_file, caption=caption)
        else:
            logger.warning(f"Image not found for card. Tried paths: {possible_paths}")
            await bot.send_message(chat_id, f"📄 {caption}\n(Image not found)")

    except Exception as e:
        logger.error(f"Error sending card image: {e}")
        await bot.send_message(chat_id, caption)


async def show_card_page(
    bot: Bot,
    message: Union[Message, CallbackQuery],
    user_id: int,
    page_index: int,
):
    if len(user_pagination) > 6: user_pagination.pop(0)
    if user_id not in user_pagination:
        if isinstance(message, Message):
            await message.reply("Your session expired. Use /sc again.")
        else:
            await message.reply("Your session expired. Use /sc again.")
        return

    pagination_data = user_pagination[user_id]
    cards_list = pagination_data['cards']
    total_pages = pagination_data['total']

    if page_index < 0 or page_index >= total_pages:
        page_index = 0

    card_id = cards_list[page_index]
    card_data = cards.get(card_id, (0, "Unknown Card", ""))

    builder = InlineKeyboardBuilder()

    if page_index > 0:
        builder.add(
            types.InlineKeyboardButton(
                text="<",
                callback_data=f"card_nav:{user_id}:{page_index-1}",
            )
        )

    builder.add(
        types.InlineKeyboardButton(
            text=f"{page_index + 1}/{total_pages}",
            callback_data="card_page:current",
        )
    )

    if page_index < total_pages - 1:
        builder.add(
            types.InlineKeyboardButton(
                text=">",
                callback_data=f"card_nav:{user_id}:{page_index+1}",
            )
        )

    caption = (
        f"🎴 {card_data[1]}\nRarity: {card_data[0]}\n\n"
        f"Page {page_index + 1} of {total_pages}"
    )

    image_path = card_data[2]
    possible_paths = [
        image_path,
        f"./{image_path}",
        f"./cards/{os.path.basename(image_path)}",
        f"cards/{os.path.basename(image_path)}",
        os.path.join("cards", os.path.basename(image_path)),
        os.path.join("./cards", os.path.basename(image_path)),
    ]

    actual_path = None
    for path in possible_paths:
        if os.path.exists(path):
            actual_path = path
            break

    if isinstance(message, CallbackQuery):
        try:
            if actual_path:
                input_file = FSInputFile(actual_path)
                media = InputMediaPhoto(media=input_file, caption=caption)
                await message.message.edit_media(
                    media=media, reply_markup=builder.as_markup()
                )
            else:
                await message.message.edit_caption(
                    caption=caption, reply_markup=builder.as_markup()
                )
        except Exception as e:
            logger.error(f"Error editing card message: {e}")
            await message.answer("Error updating card view")
    else:
        if actual_path:
            input_file = FSInputFile(actual_path)
            sent_message = await message.reply_photo(
                input_file, caption=caption, reply_markup=builder.as_markup()
            )
        else:
            sent_message = await message.reply(
                f"📄 {caption}\n(Image not found)",
                reply_markup=builder.as_markup(),
            )

        user_pagination[user_id]['message_id'] = sent_message.message_id

    user_pagination[user_id]['current_index'] = page_index


async def add_card_to_system(card_id: int, rarity: int, name: str, image_path: str) -> bool:
    global cards
    cards[card_id] = (rarity, name, image_path)
    return True


async def remove_card_from_system(card_id: int) -> bool:
    global cards
    if card_id in cards:
        del cards[card_id]
        return True
    return False


def get_cards_dict() -> Dict[int, Tuple[int, str, str]]:
    return cards


def get_user_pagination() -> Dict[int, Dict[str, Union[int, List[int]]]]:
    return user_pagination
