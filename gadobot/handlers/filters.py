from aiogram import Router, F, types
from aiogram.filters import Command
from ..database.repo import Repository
from ..resources.locales import lang

router = Router()

@router.message(Command("filter"))
async def add_filter(message: types.Message, repo: Repository):
    raw_text = message.text or message.caption
    if not raw_text:
        return

    args = raw_text.split(" ", 2)
    if len(args) < 2:
        return
        
    trigger = args[1]
    response = args[2] if len(args) > 2 else ""
    
    file_id = None
    file_type = None

    # Determine which message to pull the media from
    target = message.reply_to_message if message.reply_to_message else message

    if target.photo:
        file_id = target.photo[-1].file_id
        file_type = "photo"
    elif target.video:
        file_id = target.video.file_id
        file_type = "video"
    elif target.animation:  # Added GIF support
        file_id = target.animation.file_id
        file_type = "animation"
            
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
    filters = await repo.get_filters(message.chat.id)
    for f in filters:
        if f.trigger.lower() == message.text.lower(): # Bonus: case-insensitive check
            if f.file_id:
                if f.file_type == "photo":
                    await message.reply_photo(f.file_id, caption=f.response)
                elif f.file_type == "video":
                    await message.reply_video(f.file_id, caption=f.response)
                elif f.file_type == "animation": # Added GIF support
                    await message.reply_animation(f.file_id, caption=f.response)
            else:
                await message.reply(f.response)
            return