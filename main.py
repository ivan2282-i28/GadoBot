import os
import re
import aiosqlite
import logging
import html
from typing import Dict, List, Tuple, Union, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType, Chat, CallbackQuery, FSInputFile, InputMediaPhoto
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import random
import time
from translation import translation
from io import BytesIO

load_dotenv()

db_path = "gado.db"
cards = {
    1: (6, "Тыгыдун\nСам создатель бота", "./cards/tigidun.png"),
    3: (4, "назови", "cards/nazovi.png"),
    4: (4, "пернулканик", "cards/pernelkanic.jpg"),
    5: (5, "Флоппи картачка", "cards/flopi.jpg"),
    6: (5, "Ротен Хуманите", "cards/rotor.jpg"),
    7: (4, "Силли фембой\n@Ink_dev\n", "cards/inkdev.jpg"),
}
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv('BOT_TOKEN')
if not API_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Store user pagination data
user_pagination = {}

def lang(string: str):
    return translation["eng"][string]

async def init_db():
    async with aiosqlite.connect(db_path) as conn:
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
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            rc_cd INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        await conn.commit()

async def register_chat(chat: Chat):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'SELECT name, username, lang FROM chats WHERE chat_id = ?', 
            (chat.id,)
        )
        chater = await cursor.fetchone()
        
        if not chater:
            await conn.execute(
                'INSERT INTO chats (chat_id, name, username, lang) VALUES (?, ?, ?, ?)', 
                (chat.id, chat.full_name, chat.username, "ru")
            )
        else:
            await conn.execute(
                'UPDATE chats SET name = ?, username = ? WHERE chat_id = ?', 
                (chat.full_name, chat.username, chat.id)
            )
        await conn.commit()

async def register_user(user_id: int):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'SELECT user_id FROM users WHERE user_id = ?', 
            (user_id,)
        )
        user = await cursor.fetchone()
        
        if not user:
            await conn.execute(
                'INSERT INTO users (user_id, rc_cd) VALUES (?, ?)', 
                (user_id, 0)
            )
            await conn.commit()

async def get_chat(chat_id: int):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'SELECT name, username, lang FROM chats WHERE chat_id = ?', 
            (chat_id,)
        )
        chat = await cursor.fetchone()
        return chat

async def get_all_cards(user_id: int):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'SELECT card_id FROM cards WHERE user_id = ? ORDER BY created_at DESC', 
            (user_id,)
        )
        user_cards = await cursor.fetchall()
        return [card[0] for card in user_cards]

async def get_user_cards_count(user_id: int):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'SELECT COUNT(*) FROM cards WHERE user_id = ?', 
            (user_id,)
        )
        count = await cursor.fetchone()
        return count[0] if count else 0

async def get_user(user_id: int):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'SELECT rc_cd FROM users WHERE user_id = ?', 
            (user_id,)
        )
        user = await cursor.fetchone()
        return user

async def update_user_cooldown(user_id: int, cooldown: int):
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            'UPDATE users SET rc_cd = ? WHERE user_id = ?', 
            (cooldown, user_id)
        )
        await conn.commit()

async def add_user_card(user_id: int, card_id: int):
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            'INSERT INTO cards (user_id, card_id) VALUES (?, ?)', 
            (user_id, card_id)
        )
        await conn.commit()

async def get_card_by_index(user_id: int, index: int):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'SELECT card_id FROM cards WHERE user_id = ? ORDER BY created_at DESC LIMIT 1 OFFSET ?', 
            (user_id, index)
        )
        card = await cursor.fetchone()
        return card[0] if card else None

async def remove_user_card(user_id: int, card_id: int):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'DELETE FROM cards WHERE user_id = ? AND card_id = ?', 
            (user_id, card_id)
        )
        affected = cursor.rowcount
        await conn.commit()
        return affected > 0

async def reset_user_cooldown(user_id: int):
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            'UPDATE users SET rc_cd = 0 WHERE user_id = ?', 
            (user_id,)
        )
        await conn.commit()

async def add_card_to_system(card_id: int, rarity: int, name: str, image_path: str):
    """Add a new card to the system"""
    global cards
    cards[card_id] = (rarity, name, image_path)
    return True

async def remove_card_from_system(card_id: int):
    """Remove a card from the system"""
    global cards
    if card_id in cards:
        del cards[card_id]
        return True
    return False

def escape_html(text: str) -> str:
    if not text:
        return ""
    return html.escape(text)

async def user_can_change_info(chat_id: int, user_id: int, fun: bool) -> bool:
    a = await bot.get_chat_member(chat_id, API_TOKEN.split(":")[0])
    if not isinstance(a, types.ChatMemberAdministrator) and fun: 
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in ['administrator', 'creator']:
            if member.status == 'creator':
                return True
            return member.can_change_info if hasattr(member, 'can_change_info') else False
        return False
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def user_can_restrict(chat_id: int, user_id: int, fun: bool) -> bool:
    a = await bot.get_chat_member(chat_id, API_TOKEN.split(":")[0])
    if not isinstance(a, types.ChatMemberAdministrator) and fun: 
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in ['administrator', 'creator']:
            if member.status == 'creator':
                return True
            return member.can_restrict_members if hasattr(member, 'can_restrict_members') else False
        return False
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def add_filter(chat_id: int, trigger: str, response: str, file_id: Optional[str] = None, file_type: Optional[str] = None):
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            'INSERT INTO filters (chat_id, trigger, response, file_id, file_type) VALUES (?, ?, ?, ?, ?)',
            (chat_id, trigger, response, file_id, file_type)
        )
        await conn.commit()

async def get_chat_filters(chat_id: int) -> List[Tuple]:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'SELECT trigger, response, file_id, file_type FROM filters WHERE chat_id = ?', 
            (chat_id,)
        )
        filters = await cursor.fetchall()
        return filters

async def remove_filter(chat_id: int, trigger: str) -> bool:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'DELETE FROM filters WHERE chat_id = ? AND trigger = ?', 
            (chat_id, trigger)
        )
        affected = cursor.rowcount
        await conn.commit()
        return affected > 0

async def remove_all_filters(chat_id: int) -> int:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'DELETE FROM filters WHERE chat_id = ?', 
            (chat_id,)
        )
        affected = cursor.rowcount
        await conn.commit()
        return affected

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

async def get_all_chats():
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            'SELECT chat_id, name, username, lang FROM chats', 
            ()
        )
        chat = await cursor.fetchall()
        return chat

async def send_message_to_all_chats(text: str):
    chats = await get_all_chats()
    for chat in chats:
        try:
            await bot.send_message(chat_id=chat[0], text=text)
        except Exception:
            pass

async def send_card_with_image(chat_id: int, card_data: tuple, caption: str = None):
    """
    Send a card with its image
    card_data: (rarity, name, image_path)
    """
    rarity, name, image_path = card_data
    
    if not caption:
        caption = f"🎴 {name}\nRarity: {rarity}"
    
    try:
        # Check multiple possible path formats
        possible_paths = [
            image_path,
            f"./{image_path}",
            f"./cards/{os.path.basename(image_path)}",
            f"cards/{os.path.basename(image_path)}",
            os.path.join("cards", os.path.basename(image_path)),
            os.path.join("./cards", os.path.basename(image_path))
        ]
        
        actual_path = None
        for path in possible_paths:
            if os.path.exists(path):
                actual_path = path
                break
        
        if actual_path:
            logger.info(f"Sending card image from: {actual_path}")
            # Use FSInputFile for file system paths
            input_file = FSInputFile(actual_path)
            await bot.send_photo(chat_id, input_file, caption=caption)
        else:
            # Fallback to text if image not found
            logger.warning(f"Image not found for card. Tried paths: {possible_paths}")
            await bot.send_message(chat_id, f"📄 {caption}\n(Image not found)")
    
    except Exception as e:
        logger.error(f"Error sending card image: {e}")
        # Fallback to text message if image fails
        await bot.send_message(chat_id, caption)

async def show_card_page(message: Union[Message, CallbackQuery], user_id: int, page_index: int):
    if user_id not in user_pagination:
        if isinstance(message, Message):
            await message.answer("Your session expired. Use /sc again.")
        else:
            await message.answer("Your session expired. Use /sc again.")
        return
    
    pagination_data = user_pagination[user_id]
    cards_list = pagination_data['cards']
    total_pages = pagination_data['total']
    
    if page_index < 0 or page_index >= total_pages:
        page_index = 0
    
    card_id = cards_list[page_index]
    card_data = cards.get(card_id, (0, "Unknown Card", ""))
    
    # Create navigation keyboard
    builder = InlineKeyboardBuilder()
    
    # Previous button
    if page_index > 0:
        builder.add(types.InlineKeyboardButton(
            text="<", 
            callback_data=f"card_nav:{user_id}:{page_index-1}"
        ))
    
    # Page indicator
    builder.add(types.InlineKeyboardButton(
        text=f"{page_index + 1}/{total_pages}", 
        callback_data="card_page:current"
    ))
    
    # Next button
    if page_index < total_pages - 1:
        builder.add(types.InlineKeyboardButton(
            text=">", 
            callback_data=f"card_nav:{user_id}:{page_index+1}"
        ))
    
    # Combined caption with navigation info
    caption = f"🎴 {card_data[1]}\nRarity: {card_data[0]}\n\nPage {page_index + 1} of {total_pages}"
    
    # Check if image exists
    image_path = card_data[2]
    possible_paths = [
        image_path,
        f"./{image_path}",
        f"./cards/{os.path.basename(image_path)}",
        f"cards/{os.path.basename(image_path)}",
        os.path.join("cards", os.path.basename(image_path)),
        os.path.join("./cards", os.path.basename(image_path))
    ]
    
    actual_path = None
    for path in possible_paths:
        if os.path.exists(path):
            actual_path = path
            break
    
    if isinstance(message, CallbackQuery):
        # For callback queries, edit the existing message
        try:
            if actual_path:
                # Edit both photo and caption
                input_file = FSInputFile(actual_path)
                media = InputMediaPhoto(media=input_file, caption=caption)
                await message.message.edit_media(media=media, reply_markup=builder.as_markup())
            else:
                # If no image, edit just the caption and buttons
                await message.message.edit_caption(caption=caption, reply_markup=builder.as_markup())
        except Exception as e:
            logger.error(f"Error editing card message: {e}")
            await message.answer("Error updating card view")
    else:
        # For new messages, send the card with image and navigation
        if actual_path:
            input_file = FSInputFile(actual_path)
            sent_message = await message.answer_photo(input_file, caption=caption, reply_markup=builder.as_markup())
        else:
            sent_message = await message.answer(f"📄 {caption}\n(Image not found)", reply_markup=builder.as_markup())
        
        # Store the message ID for future edits
        user_pagination[user_id]['message_id'] = sent_message.message_id
    
    # Update current index
    user_pagination[user_id]['current_index'] = page_index

@dp.message(Command("rc", "roll-card", "rollcard"))
async def cmd_roll_card(message: Message):
    await register_user(message.from_user.id)
    
    user_data = await get_user(message.from_user.id)
    current_time = int(time.time())
    
    if user_data and user_data[0] > current_time:
        cooldown_remaining = user_data[0] - current_time
        hours = cooldown_remaining // 3600
        minutes = (cooldown_remaining % 3600) // 60
        
        await message.answer(
            f"⏰ Please wait {hours}h {minutes}m before rolling again!"
        )
        return
    
    # Roll a random card
    card_id = random.choice(list(cards.keys()))
    card_data = cards[card_id]
    
    # Add card to user's collection
    await add_user_card(message.from_user.id, card_id)
    
    # Set cooldown (4 hours)
    next_roll_time = current_time + (4 * 60 * 60)  # 4 hours in seconds
    await update_user_cooldown(message.from_user.id, next_roll_time)
    
    # Send the card with image
    await send_card_with_image(message.chat.id, card_data)

@dp.message(Command("sc", "seecards", "see-cards"))
async def cmd_see_cards(message: Message):
    user_id = message.from_user.id
    user_cards = await get_all_cards(user_id)
    
    if not user_cards:
        await message.answer("You don't have any cards yet! Use /rc to roll your first card.")
        return
    
    total_cards = len(user_cards)
    user_pagination[user_id] = {
        'cards': user_cards,
        'current_index': 0,
        'total': total_cards
    }
    
    await show_card_page(message, user_id, 0)

@dp.callback_query(F.data.startswith("card_nav:"))
async def handle_card_navigation(callback: CallbackQuery):
    data_parts = callback.data.split(":")
    if len(data_parts) != 3:
        await callback.answer("Invalid navigation data")
        return
    
    target_user_id = int(data_parts[1])
    page_index = int(data_parts[2])
    
    # Only allow the card owner to navigate
    if callback.from_user.id != target_user_id:
        await callback.answer("These are not your cards!")
        return
    
    await show_card_page(callback, target_user_id, page_index)
    await callback.answer()

@dp.callback_query(F.data == "card_page:current")
async def handle_current_page(callback: CallbackQuery):
    await callback.answer(f"Page {user_pagination.get(callback.from_user.id, {}).get('current_index', 0) + 1}")

# ... (rest of the admin commands and other functions remain the same)

# Admin commands
@dp.message(Command("ADM_add_card"))
async def cmd_adm_add_card(message: Message):
    if message.from_user.id != 1999559891:
        await message.answer("Who are YOU?")
        return
    
    try:
        parts = message.text.split(maxsplit=4)
        if len(parts) < 5:
            await message.answer("Usage: /ADM_add_card <card_id> <rarity> <name> <image_path>")
            return
        
        card_id = int(parts[1])
        rarity = int(parts[2])
        name = parts[3]
        image_path = parts[4]
        
        success = await add_card_to_system(card_id, rarity, name, image_path)
        
        if success:
            await message.answer(f"Card added successfully!\nID: {card_id}\nName: {name}\nRarity: {rarity}\nImage: {image_path}")
        else:
            await message.answer("Failed to add card")
    
    except Exception as e:
        await message.answer(f"Error adding card: {e}")

@dp.message(Command("ADM_remove_card"))
async def cmd_adm_remove_card(message: Message):
    if message.from_user.id != 1999559891:
        await message.answer("Who are YOU?")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Usage: /ADM_remove_card <card_id>")
            return
        
        card_id = int(parts[1])
        success = await remove_card_from_system(card_id)
        
        if success:
            await message.answer(f"Card {card_id} removed successfully!")
        else:
            await message.answer(f"Card {card_id} not found!")
    
    except Exception as e:
        await message.answer(f"Error removing card: {e}")

@dp.message(Command("ADM_reset_cooldown"))
async def cmd_adm_reset_cooldown(message: Message):
    if message.from_user.id != 1999559891:
        await message.answer("Who are YOU?")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Usage: /ADM_reset_cooldown <user_id>")
            return
        
        user_id = int(parts[1])
        await reset_user_cooldown(user_id)
        await message.answer(f"Cooldown reset for user {user_id}")
    
    except Exception as e:
        await message.answer(f"Error resetting cooldown: {e}")

@dp.message(Command("ADM_remove_user_card"))
async def cmd_adm_remove_user_card(message: Message):
    if message.from_user.id != 1999559891:
        await message.answer("Who are YOU?")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("Usage: /ADM_remove_user_card <user_id> <card_id>")
            return
        
        user_id = int(parts[1])
        card_id = int(parts[2])
        success = await remove_user_card(user_id, card_id)
        
        if success:
            await message.answer(f"Card {card_id} removed from user {user_id}")
        else:
            await message.answer(f"Card {card_id} not found for user {user_id}")
    
    except Exception as e:
        await message.answer(f"Error removing user card: {e}")

@dp.message(Command("ADM_list_cards"))
async def cmd_adm_list_cards(message: Message):
    if message.from_user.id != 1999559891:
        await message.answer("Who are YOU?")
        return
    
    card_list = "Available cards:\n"
    for card_id, (rarity, name, image_path) in cards.items():
        card_list += f"{card_id}: {name} (Rarity: {rarity}) - {image_path}\n"
    
    await message.answer(card_list)

@dp.message(Command("ADM_check_images"))
async def cmd_adm_check_images(message: Message):
    if message.from_user.id != 1999559891:
        await message.answer("Who are YOU?")
        return
    
    image_status = "Image Status:\n"
    for card_id, (rarity, name, image_path) in cards.items():
        possible_paths = [
            image_path,
            f"./{image_path}",
            f"./cards/{os.path.basename(image_path)}",
            f"cards/{os.path.basename(image_path)}",
            os.path.join("cards", os.path.basename(image_path)),
            os.path.join("./cards", os.path.basename(image_path))
        ]
        
        found = False
        actual_path = None
        for path in possible_paths:
            if os.path.exists(path):
                found = True
                actual_path = path
                break
        
        status = "✅ Found" if found else "❌ Missing"
        image_status += f"Card {card_id}: {name} - {status}"
        if actual_path:
            image_status += f" ({actual_path})"
        image_status += "\n"
    
    await message.answer(image_status)

@dp.message(Command("ADM_send"))
async def cmd_adm_send(message: Message):
    if message.from_user.id == 1999559891:
        text = message.text
        text = text[(len(text.split()[0]) + 1):]
        await send_message_to_all_chats(text)
        await message.answer("OK")
    else:
        await message.answer("Who are YOU?")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    help_text = lang("start_message")
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    help_text = (
        f'{lang("stats_header")} {message.chat.id}\n'
        f"{lang('stats_name')}: {message.chat.full_name}\n"
        f"{lang('stats_members')}: {await message.chat.get_member_count()}\n"
        f"{lang('stats_username')}: {message.chat.username}"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("stats_global"))
async def cmd_stats_global(message: Message):
    chats = await get_all_chats()
    if "-root" in message.text:
        if message.from_user.id == 1999559891:
            help_text = (
                f'{lang("global_stats_header_root")}\n'
                f"{lang('global_stats_chat_count')}: {len(chats)}\n"
                f"{chats}"
            )
        else:
            help_text = (
                f'{lang("global_stats_header")}\n'
                "I do not believe you! YOU ARE NOT ROOT"
            )
    else:
        help_text = (
            f'{lang("global_stats_header")}\n'
            f"{lang('global_stats_chat_count')}: {len(chats)}\n"
        )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    if "-misc" in message.text:
        help_text = lang("help_misc")
    elif "-filters" in message.text:
        help_text = lang("help_filters")
    elif "-mod" in message.text:
        help_text = lang("help_moderation")
    else:
        help_text = lang("help")
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("filter"))
async def cmd_filter(message: Message):
    if not await user_can_change_info(message.chat.id, message.from_user.id, True):
        await message.answer(lang("no_perm_profile"))
        return

    if message.reply_to_message and message.reply_to_message.content_type in ['photo', 'video', 'document', 'animation']:
        parts = message.text.split(' ', 1)
        if len(parts) < 2:
            await message.answer(lang("filter_usage_media"))
            return
        
        trigger = parts[1].strip()
        response = ""
        if message.reply_to_message.caption:
            response = message.reply_to_message.caption
        elif message.reply_to_message.text:
            response = message.reply_to_message.text

        file_id = None
        file_type = message.reply_to_message.content_type
        
        if file_type == 'photo':
            file_id = message.reply_to_message.photo[-1].file_id
        elif file_type == 'video':
            file_id = message.reply_to_message.video.file_id
        elif file_type == 'document':
            file_id = message.reply_to_message.document.file_id
        elif file_type == 'animation':
            file_id = message.reply_to_message.animation.file_id
        
        filters = await get_chat_filters(message.chat.id)
        for f in filters:
            if f[0] == trigger:
                await message.answer(lang("already_exists"))
                return
        
        await add_filter(message.chat.id, trigger, response, file_id, file_type)
        
        await message.answer(
            lang("filter_added_media").format(trigger=escape_html(trigger)),
            parse_mode=ParseMode.HTML
        )
    else:
        trigger, response = parse_filter_command(message.text)
        if not trigger or not response:
            await message.answer(lang("filter_usage_text"))
            return
        
        filters = await get_chat_filters(message.chat.id)
        for f in filters:
            if f[0] == trigger:
                await message.answer(lang("already_exists"))
                return
        
        await add_filter(message.chat.id, trigger, response)
        
        if trigger.startswith('r"') and trigger.endswith('"'):
            filter_type = lang("regex")
            clean_trigger = trigger[2:-1]
        else:
            filter_type = lang("text")
            clean_trigger = trigger
        
        await message.answer(
            lang("filter_added_text").format(filter_type=filter_type, trigger=escape_html(clean_trigger)),
            parse_mode=ParseMode.HTML
        )

@dp.message(Command("filters"))
async def cmd_filters(message: Message):
    filters = await get_chat_filters(message.chat.id)
    if not filters:
        await message.answer(lang("not_exists_filter_all"))
        return
    
    filters_list = []
    for i, (trigger, response, file_id, file_type) in enumerate(filters, 1):
        display_trigger = trigger
        filters_list.append(f"<code>{escape_html(display_trigger)}</code>")
    
    filters_list.sort(key=lambda x: x[0])

    filters_text = "\n".join(filters_list)
    await message.answer(
        lang("filters_list").format(filters_text=filters_text),
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("remove_filter"))
async def cmd_remove_filter(message: Message):
    if not await user_can_change_info(message.chat.id, message.from_user.id, True):
        await message.answer(lang("no_perm_profile"))
        return
    
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        await message.answer(lang("remove_filter_usage"))
        return
    
    trigger = parts[1].strip()
    
    success = await remove_filter(message.chat.id, trigger)
    
    if not success:
        await message.answer(lang("remove_filter_not_found"))
        return
    
    await message.answer(
        lang("remove_filter_success").format(trigger=escape_html(trigger)), 
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("remove_all_filters"))
async def cmd_remove_all_filters(message: Message):
    if not await user_can_change_info(message.chat.id, message.from_user.id, True):
        await message.answer(lang("no_perm_profile"))
        return
    
    count = await remove_all_filters(message.chat.id)
    
    if count == 0:
        await message.answer(lang("not_exists_filter_all"))
        return
    
    await message.answer(lang("remove_all_filters_success").format(count=count))

@dp.message(Command("ban"))
async def ban(message: Message):
    a = await bot.get_chat_member(message.chat.id, API_TOKEN.split(":")[0])
    if not a.can_restrict_members: 
        await message.reply(lang("bot_no_perm_restrict_members"))
        return
    if not await user_can_restrict(message.chat.id, message.from_user.id, False):
        await message.reply(lang("no_restmem_profile"))
        return
    
    user_id = None
    reason = None
    timer = None
    args = list(message.text.split())
    args.pop(0)
    
    for arg in args:
        if arg.startswith("@"):
            if user_id is None:
                user_id = arg
        elif arg.isnumeric():
            if user_id is None or isinstance(user_id, str) and user_id.startswith("@"):
                user_id = arg
        elif arg.endswith("d") and arg[:-1].isnumeric():
            timer = 24 * 60 * 60 * int(arg[:-1])
        elif arg.endswith("h") and arg[:-1].isnumeric():
            timer = 60 * 60 * int(arg[:-1])
        elif arg.endswith("m") and arg[:-1].isnumeric():
            timer = 60 * int(arg[:-1])
        else:
            if reason is None:
                reason = arg
            else:
                reason = f"{reason} {arg}"
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    
    if user_id is None:
        await message.reply("/dev/null is not a user")
        return
    
    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return
    
    until_date = int(time.time() + timer) if timer else None
    
    try:
        await bot.ban_chat_member(message.chat.id, int(user_id), until_date=until_date)
        
        timer_text = f"-time {timer}" if timer else ""
        reason_text = f"-reason {reason}" if reason else ""
        
        await message.reply(
            lang("banned").format(
                user_id=user_id, 
                timer=timer_text, 
                reason=reason_text, 
                chat_id=message.chat.id
            )
        )
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        await message.reply("Failed to ban user")

@dp.message(Command("export"))
async def exportcmd(message: Message):
    filters = await get_chat_filters(message.chat.id)
    fstr = ""
    for trigger, response, file_id, file_type in filters:
        fstr += f"~{trigger};{response};{file_id or 'None'};{file_type or 'None'}\n"
    
    file_content = f"GBTP001:GADOBOT Transmit Protocol v0.0.1\nBEGIN\n{fstr}"
    
    await message.answer_document(
        document=types.BufferedInputFile(
            file_content.encode(), 
            filename=f"gadobot_backup_{message.chat.id}_{int(time.time())}.gbtp"
        ),
        caption="GBTP001: Backup file generated"
    )

@dp.message(Command("import"))
async def importcmd(message: Message):
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    
    if not isinstance(member, types.ChatMemberOwner):
        await message.answer("GBTP MANAGMENT SYSTEM: NOT ENOUGH RIGHTS")
        return

    if not message.document:
        await message.answer(
            "GBTP MANAGMENT SYSTEM:\n"
            "Please attach a backup file to import.\n"
            "How to use: Reply to this message with /import and attach the .gbtp file"
        )
        return

    if not message.document.file_name.endswith('.gbtp'):
        await message.answer("GBTP MANAGMENT SYSTEM: Invalid file format. Please use .gbtp backup files")
        return

    try:
        file_info = await bot.get_file(message.document.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        file_content = downloaded_file.read().decode('utf-8')
        
        if file_content.startswith("GBTP001"):
            payload_parts = file_content.split("BEGIN")
            if len(payload_parts) < 2:
                raise ValueError("Invalid file format: BEGIN section missing")
                
            payload_fake = payload_parts[1].strip()
            payload_fake = payload_fake.split("~")
            payload_fake = [p for p in payload_fake if p.strip()]
            
            payload_real = []
            for item in payload_fake:
                pload = item.split(";")
                if len(pload) != 4:
                    continue
                    
                pload = [None if item == "None" else item for item in pload]
                payload_real.append((pload[0], pload[1], pload[2], pload[3]))
            
            await remove_all_filters(message.chat.id)
            for trigger, response, file_id, file_type in payload_real:
                await add_filter(message.chat.id, trigger, response, file_id, file_type)
            
            await message.answer("GBTP MANAGMENT SYSTEM: Import successful!")
        else:
            await message.answer("GBTP MANAGMENT SYSTEM: This GBTP type is not supported")
            
    except Exception as e:
        await message.answer("GBTP MANAGMENT SYSTEM: Import failed! Your chat db was wiped for stability:3")
        logger.error(f"Import error: {e}")
        await remove_all_filters(message.chat.id)

@dp.message(F.text)
async def message_handler(message: Message):
    await register_chat(message.chat)
    filters = await get_chat_filters(message.chat.id)
    if not filters:
        return
    
    text = message.text.lower() if message.text else ""
    for trigger, response, file_id, file_type in filters:
        tragger = trigger.lower()
        if trigger.startswith('r"') and trigger.endswith('"'):
            pattern = trigger[2:-1]
            try:
                if re.search(pattern, message.text or "", re.IGNORECASE):
                    await send_filter_response(message, response, file_id, file_type)
                    break
            except re.error as e:
                logger.error(f"Regex error in pattern '{pattern}': {e}")
        
        elif (f" {tragger} " in text or text.startswith(f"{tragger} ") or 
              text.endswith(f" {tragger}") or text == tragger):
            await send_filter_response(message, response, file_id, file_type)
            break

async def send_filter_response(message: Message, response: str, file_id: Optional[str], file_type: Optional[str]):
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

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())