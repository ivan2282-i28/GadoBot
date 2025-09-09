import os
import re
import sqlite3
import logging
import html
from typing import Dict, List, Tuple, Union, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from translation import translation

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
API_TOKEN = os.getenv('BOT_TOKEN')
if not API_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


def lang(string: str):
    return translation["ru"][string]
# Database setup
def init_db():
    conn = sqlite3.connect('filters.db')
    cursor = conn.cursor()
    cursor.execute('''
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
    conn.commit()
    conn.close()

init_db()

def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    if not text:
        return ""
    return html.escape(text)

async def user_can_change_info(chat_id: int, user_id: int) -> bool:
    """Check if user can change chat info (admin with appropriate rights)"""
    a = await bot.get_chat_member(chat_id,API_TOKEN.split(":")[0])
    if not isinstance(a,types.ChatMemberAdministrator): return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in ['administrator', 'creator']:
            if member.status == 'creator':
                return True
            # Check if admin has the right to change info
            return member.can_change_info if hasattr(member, 'can_change_info') else False
        return False
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

def add_filter(chat_id: int, trigger: str, response: str, file_id: Optional[str] = None, file_type: Optional[str] = None):
    """Add a filter to the database"""
    conn = sqlite3.connect('filters.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO filters (chat_id, trigger, response, file_id, file_type) VALUES (?, ?, ?, ?, ?)',
        (chat_id, trigger, response, file_id, file_type)
    )
    conn.commit()
    conn.close()

def get_chat_filters(chat_id: int) -> List[Tuple]:
    """Get all filters for a chat"""
    conn = sqlite3.connect('filters.db')
    cursor = conn.cursor()
    cursor.execute('SELECT trigger, response, file_id, file_type FROM filters WHERE chat_id = ?', (chat_id,))
    filters = cursor.fetchall()
    conn.close()
    return filters

def remove_filter(chat_id: int, trigger: str) -> bool:
    """Remove a specific filter from the database"""
    conn = sqlite3.connect('filters.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM filters WHERE chat_id = ? AND trigger = ?', (chat_id, trigger))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def remove_all_filters(chat_id: int) -> int:
    """Remove all filters for a chat"""
    conn = sqlite3.connect('filters.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM filters WHERE chat_id = ?', (chat_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected

def parse_filter_command(text: str) -> tuple:
    """Parse filter command with proper handling of regex patterns"""
    # Remove the command part
    if text.startswith('/filter'):
        text = text[len('/filter'):].strip()
    
    # Check if it's a regex pattern (starts with r")
    if text.startswith('r"'):
        # Find the closing quote
        end_quote = text.find('"', 2)
        if end_quote == -1:
            return None, None  # No closing quote found
        
        trigger = text[:end_quote + 1]  # Include the r" and closing quote
        response = text[end_quote + 1:].strip()
        
        # If response starts with a quote, remove it
        if response.startswith('"'):
            response = response[1:]
        if response.endswith('"'):
            response = response[:-1]
            
        return trigger, response
    
    # Handle regular quoted triggers
    elif text.startswith('"'):
        # Find the closing quote
        end_quote = text.find('"', 1)
        if end_quote == -1:
            return None, None  # No closing quote found
        
        trigger = text[:end_quote + 1]  # Include the quotes
        response = text[end_quote + 1:].strip()
        
        # Remove quotes from trigger
        trigger = trigger[1:-1]
        
        return trigger, response
    
    # Handle unquoted triggers
    else:
        # Split on the first space
        parts = text.split(' ', 1)
        if len(parts) < 2:
            return None, None
        
        trigger = parts[0]
        response = parts[1]
        
        return trigger, response

@dp.message(Command("start", "help"))
async def cmd_start(message: Message):
    """Handler for /start and /help commands"""
    help_text = (
        "🤖 <b>ГадоБот</b>\n\n"
        "Киминды:\n"
        "• /filter [trigger] [response] - Нагадить фильтр\n"
        "• /filter [trigger] (reply to media) - Нагадить медиа фильтр\n"
        "• /filters - Список фильтр\n"
        "• /remove_filter [trigger] - Прогнать гадский фильтр\n"
        "• /remove_all_filters - рататататата\n\n"
        "Типы фильтров:\n"
        "• <code>regex</code> - Гадь r\"pattern\" чтоб regex\n"
        "• <code>text</code> - Обычный текст(case-insensitive)\n"
        "• <code>media</code> - Ответь на медию /filter trigger\n\n"
        "Экзамплес:\n"
        "• <code>/filter r\"hello|hi\" \"Hey there!\"</code>\n"
        "• <code>/filter \"thank you\" \"You're welcome!\"</code>\n"
        "• <code>/filter hello Hello_back!</code>\n"
        "• Reply to a photo with <code>/filter cat_pic</code>\n\n"
        "ГадоИнфа:\n"
        "ГадоЭтот ГадоБот ГадоБыл ГадоСделан ГадоДля ГадоЧата ГадаРотен ГадоХуманете\n"
        "Под ГадоЛицензитей ГадоАпафь Тву поинт ноль \n"
        "ГадоСурсы на ГадоХабе: https://github.com/ivan2282-i28/GadoBot"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("filter"))
async def cmd_filter(message: Message):
    """Add a filter to the chat"""
    # Check if user can change chat info
    if not await user_can_change_info(message.chat.id, message.from_user.id):
        await message.answer(lang("no_perm_profile"))
        return

    # Check if replying to media
    if message.reply_to_message and message.reply_to_message.content_type in ['photo', 'video', 'document', 'animation']:
        # Media filter - parse the trigger from the command
        parts = message.text.split(' ', 1)
        if len(parts) < 2:
            await message.answer("❌ Как гадить?: Ответь на медию /filter <trigger>")
            return
        
        trigger = parts[1].strip()
        response = ""  # Placeholder, media will be sent instead
        if message.reply_to_message.caption:
            response = message.reply_to_message.caption
        elif message.reply_to_message.text:
            esponse = message.reply_to_message.text
        # Get file info based on content type
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
        
        # Check if trigger already exists
        filters = get_chat_filters(message.chat.id)
        for f in filters:
            if f[0] == trigger:
                await message.answer(lang("already_exists"))
                return
        
        # Add filter to database
        add_filter(message.chat.id, trigger, response, file_id, file_type)
        
        await message.answer(
            f"✅ <b>Фильтр добавлен!</b>\n\n"
            f"<b>Trigger:</b> <code>{escape_html(trigger)}</code>\n",
            # f"<b>Type:</b> {file_type.capitalize()}",
            parse_mode=ParseMode.HTML
        )
    else:
        # Text filter - parse trigger and response from command
        trigger, response = parse_filter_command(message.text)
        if not trigger or not response:
            await message.answer("❌ Как гадить?: /filter <trigger> <response>")
            return
        
        # Check if trigger already exists
        filters = get_chat_filters(message.chat.id)
        for f in filters:
            if f[0] == trigger:
                await message.answer(lang("already_exists"))
                return
        
        # Add filter to database
        add_filter(message.chat.id, trigger, response)
        
        # Determine filter type
        if trigger.startswith('r"') and trigger.endswith('"'):
            filter_type = "Regex"
            clean_trigger = trigger[2:-1]  # Remove r"" wrapping
        else:
            filter_type = "Text"
            clean_trigger = trigger
        
        await message.answer(
            f"✅ <b>{filter_type} Фильтр добавлен!</b>\n\n"
            f"<b>Trigger:</b> <code>{escape_html(clean_trigger)}</code>\n",
            # f"<b>Response:</b> {escape_html(response)}",
            parse_mode=ParseMode.HTML
        )

@dp.message(Command("filters"))
async def cmd_filters(message: Message):
    """List all filters in the chat"""
    filters = get_chat_filters(message.chat.id)
    if not filters:
        await message.answer(lang("not_exists_filter_all"))
        return
    

    
    filters_list = []
    for i, (trigger, response, file_id, file_type) in enumerate(filters, 1):
        # if trigger.startswith('r"') and trigger.endswith('"'):
        #     display_trigger = f"Regex: {trigger[2:-1]}"
        # else:
        #     display_trigger = f"Text: {trigger}"
        display_trigger = trigger
        if file_type:
            display_response = f"[{file_type.capitalize()}]"
        else:
            display_response = response
        
        # filters_list.append(f"{i}. <code>{escape_html(display_trigger)}</code> → {escape_html(display_response)}")
        filters_list.append(f"<code>{escape_html(display_trigger)}</code>")
    
    filters_list = filters_list.sort()

    filters_text = "\n".join(filters_list)
    await message.answer(
        f"📋 <b>Filters in this chat:</b>\n\n{filters_text}",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("remove_filter"))
async def cmd_remove_filter(message: Message):
    """Remove a specific filter"""
    # Check if user can change chat info
    if not await user_can_change_info(message.chat.id, message.from_user.id):
        await message.answer(lang("no_perm_profile"))
        return
    
    # Parse command arguments
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        await message.answer("❌ Как гадить?: /remove_filter <trigger>")
        return
    
    trigger = parts[1].strip()
    
    # Remove filter
    success = remove_filter(message.chat.id, trigger)
    
    if not success:
        await message.answer("❌ Нету фильтра с таким тригером.")
        return
    
    await message.answer(f"✅ Фильтр рататата: <code>{escape_html(trigger)}</code>", 
                         parse_mode=ParseMode.HTML)

@dp.message(Command("remove_all_filters"))
async def cmd_remove_all_filters(message: Message):
    """Remove all filters in the chat"""
    # Check if user can change chat info
    if not await user_can_change_info(message.chat.id, message.from_user.id):
        await message.answer(lang("no_perm_profile"))
        return
    
    # Remove all filters
    count = remove_all_filters(message.chat.id)
    
    if count == 0:
        await message.answer(lang("not_exists_filter_all"))
        return
    
    await message.answer(f"✅ Ратататат {count}")

@dp.message(F.text)
async def message_handler(message: Message):
    """Handle incoming messages and check against filters"""
    filters = get_chat_filters(message.chat.id)
    if not filters:
        return
    
    text = message.text.lower() if message.text else ""
    
    for trigger, response, file_id, file_type in filters:
        tragger = trigger.lower()
        # Handle regex triggers
        if trigger.startswith('r"') and trigger.endswith('"'):
            pattern = trigger[2:-1]  # Extract pattern from r"pattern"
            try:
                if re.search(pattern, message.text or "", re.IGNORECASE):
                    await send_filter_response(message, response, file_id, file_type)
                    break
            except re.error as e:
                logger.error(f"Regex error in pattern '{pattern}': {e}")
        
        # Handle text triggers (case-insensitive)
        
        elif f" {tragger} " in text or text.startswith(f"{tragger} ") or text.endswith(f" {tragger}") or text == tragger:
            await send_filter_response(message, response, file_id, file_type)
            break

async def send_filter_response(message: Message, response: str, file_id: Optional[str], file_type: Optional[str]):
    """Send the appropriate response based on filter type"""
    if file_id and file_type:
        # Media response
        if file_type == 'photo':
            await message.reply_photo(file_id, caption=response if response != "Media response" else None)
        elif file_type == 'video':
            await message.reply_video(file_id, caption=response if response != "Media response" else None)
        elif file_type == 'document':
            await message.reply_document(file_id, caption=response if response != "Media response" else None)
        elif file_type == 'animation':
            await message.reply_animation(file_id, caption=response if response != "Media response" else None)
    else:
        # Text response
        await message.reply(response)

async def main():
    """Main function to start the bot"""
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())