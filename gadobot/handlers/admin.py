import time
from aiogram import Router, types, Bot
from aiogram.filters import Command
from ..database.repo import Repository
from ..resources.locales import lang
from ..utils.helpers import parse_target_args

router = Router()

def is_admin(func):
    '''Decorator: Checks if user and bot have admin rights.'''
    async def wrapper(message: types.Message, bot: Bot, repo: Repository, **kwargs):
        # 1. User check
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        except:
            return # Bot probably kicked
            
        if member.status not in ('administrator', 'creator'):
            await message.reply(lang("user_no_perm"))
            return
        
        # 2. Bot check
        try:
            bot_member = await bot.get_chat_member(message.chat.id, bot.id)
            if not bot_member.can_restrict_members:
                await message.reply(lang("bot_no_perm"))
                return
        except:
            pass # Ignore if can't check
            
        return await func(message, bot, repo, **kwargs)
    return wrapper

@router.message(Command("ban"))
@is_admin
async def cmd_ban(message: types.Message, bot: Bot, repo: Repository):
    user_id, reason, duration = await parse_target_args(message)
    if not user_id:
        return await message.reply(lang("invalid_user"))
    if user_id == bot.id:
        return await message.reply(lang("self_action_error"))

    until = int(time.time() + duration) if duration else None
    
    try:
        await bot.ban_chat_member(message.chat.id, user_id, until_date=until)
        timer_str = f"-time {duration}s" if duration else ""
        reason_str = f"-reason {reason}" if reason else ""
        await message.reply(lang("banned", user_id=user_id, timer=timer_str, reason=reason_str))
    except Exception:
        await message.reply(lang("action_failed"))

@router.message(Command("mute"))
@is_admin
async def cmd_mute(message: types.Message, bot: Bot, repo: Repository):
    user_id, reason, duration = await parse_target_args(message)
    if not user_id: return await message.reply(lang("invalid_user"))
    if user_id == bot.id: return await message.reply(lang("self_action_error"))
    
    perms = types.ChatPermissions(can_send_messages=False)
    until = int(time.time() + duration) if duration else None
    
    try:
        await bot.restrict_chat_member(message.chat.id, user_id, permissions=perms, until_date=until)
        timer_str = f"-time {duration}s" if duration else ""
        reason_str = f"-reason {reason}" if reason else ""
        await message.reply(lang("muted", user_id=user_id, timer=timer_str, reason=reason_str))
    except Exception:
        await message.reply(lang("action_failed"))

@router.message(Command("unban"))
@is_admin
async def cmd_unban(message: types.Message, bot: Bot, repo: Repository):
    user_id, _, _ = await parse_target_args(message)
    if not user_id: return await message.reply(lang("invalid_user"))
    
    try:
        await bot.unban_chat_member(message.chat.id, user_id)
        await message.reply(lang("unbanned", user_id=user_id))
    except Exception:
        await message.reply(lang("action_failed"))

@router.message(Command("unmute"))
@is_admin
async def cmd_unmute(message: types.Message, bot: Bot, repo: Repository):
    user_id, _, _ = await parse_target_args(message)
    if not user_id: return await message.reply(lang("invalid_user"))
    
    perms = types.ChatPermissions(
        can_send_messages=True, can_send_media_messages=True,
        can_send_polls=True, can_send_other_messages=True
    )
    try:
        await bot.restrict_chat_member(message.chat.id, user_id, permissions=perms)
        await message.reply(lang("unmuted", user_id=user_id))
    except Exception:
        await message.reply(lang("action_failed"))

@router.message(Command("warn"))
@is_admin
async def cmd_warn(message: types.Message, bot: Bot, repo: Repository):
    user_id, reason, _ = await parse_target_args(message)
    if not user_id: return await message.reply(lang("invalid_user"))
    
    count = await repo.add_warn(message.chat.id, user_id)
    limit = await repo.get_warn_limit(message.chat.id)
    
    await message.reply(lang("warned", user_id=user_id, reason=reason or "", count=count, limit=limit))
    
    if count >= limit:
        await bot.ban_chat_member(message.chat.id, user_id)
        await message.reply(lang("banned", user_id=user_id, timer="", reason="Max warns reached"))
        await repo.reset_warns(message.chat.id, user_id)

@router.message(Command("unwarn"))
@is_admin
async def cmd_unwarn(message: types.Message, repo: Repository, bot: Bot):
    user_id, _, _ = await parse_target_args(message)
    if not user_id: return await message.reply(lang("invalid_user"))
    
    await repo.remove_warn(message.chat.id, user_id)
    await message.reply(lang("unwarned", user_id=user_id))

@router.message(Command("limitwarn"))
@is_admin
async def cmd_limitwarn(message: types.Message, repo: Repository, bot: Bot):
    args = message.text.split()
    if len(args) < 2:
        curr = await repo.get_warn_limit(message.chat.id)
        return await message.reply(lang("warn_limit_curr", limit=curr))
    
    try:
        limit = int(args[1])
        if limit < 1: raise ValueError
        await repo.set_warn_limit(message.chat.id, limit)
        await message.reply(lang("warn_limit_set", limit=limit))
    except ValueError:
        await message.reply(lang("warn_limit_invalid"))

@router.message(Command("history"))
@is_admin
async def cmd_history(message: types.Message, repo: Repository, bot: Bot):
    user_id, _, _ = await parse_target_args(message)
    if not user_id: return await message.reply(lang("invalid_user"))
    
    warns = await repo.get_warns(message.chat.id, user_id)
    limit = await repo.get_warn_limit(message.chat.id)
    bl_list = await repo.get_blacklist(message.chat.id)
    is_bl = "Yes" if user_id in bl_list else "No"
    
    await message.reply(lang("history", user_id=user_id, warns=warns, limit=limit, bl=is_bl))

@router.message(Command("kickme"))
async def cmd_kickme(message: types.Message, bot: Bot):
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status in ('administrator', 'creator'):
        return await message.reply(lang("kickme_admin"))
        
    try:
        await bot.ban_chat_member(message.chat.id, message.from_user.id)
        await message.reply(lang("kickme_self", user_id=message.from_user.id))
        await bot.unban_chat_member(message.chat.id, message.from_user.id)
    except Exception:
        await message.reply(lang("action_failed"))