from aiogram import Router, F, types
from aiogram.filters import Command
from ..database.repo import Repository
from ..resources.locales import lang

router = Router()

@router.message(Command("filter"))
async def add_filter(message: types.Message, repo: Repository):
    # message.text is None if the command is in a photo/video caption
    raw_text = message.text or message.caption
    
    if not raw_text:
        return

    args = raw_text.split(" ", 2)
    if len(args) < 2:
        # Optionally notify user they missed arguments
        return
        
    trigger = args[1]
    response = args[2] if len(args) > 2 else ""  # Default to empty response if not provided
    
    
    if message.reply_to_message:
        if message.reply_to_message.photo:
            file_id = message.reply_to_message.photo[-1].file_id
            file_type = "photo"
        elif message.reply_to_message.video:
            file_id = message.reply_to_message.video.file_id
            file_type = "video"
    else:
        if message.photo:
            file_id = message.photo[-1].file_id
            file_type = "photo"
        elif message.video:
            file_id = message.video.file_id
            file_type = "video"
            
    await repo.add_filter(message.chat.id, trigger, response, file_id, file_type)
    await message.reply(lang("filter_added", trigger=trigger))

@router.message(Command("stop"))
async def remove_filter(message: types.Message, repo: Repository):
    args = message.text.split(" ", 1)
    if len(args) < 2: return
    
    trigger = args[1]
    res = await repo.remove_filter(message.chat.id, trigger)
    if res:
        await message.reply(lang("filter_removed"))

@router.message(Command("filters"))
async def cmd_list_filters(message: types.Message, repo: Repository):
    filters = await repo.get_filters(message.chat.id)
    
    if not filters:
        await message.reply("No filters active in this chat.")
        return

    # Create a list of triggers
    text = "📂 **Active Filters:**\n\n"
    for f in filters:
        text += f"• <code>{f.trigger}</code>\n"
        
    await message.reply(text, parse_mode="HTML")

@router.message(F.text)
async def check_filters(message: types.Message, repo: Repository):
    # Check if text matches any filter trigger
    filters = await repo.get_filters(message.chat.id)
    for f in filters:
        if f.trigger == message.text:
            if f.file_id:
                if f.file_type == "photo":
                    await message.answer_photo(f.file_id, caption=f.response)
                elif f.file_type == "video":
                    await message.answer_video(f.file_id, caption=f.response)
            else:
                await message.answer(f.response)
            return