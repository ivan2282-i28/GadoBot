import time
import logging
from typing import Optional

from aiogram import Bot, types
from aiogram.types import Message

from translation import translation
from db import (
    add_to_blacklist,
    remove_from_blacklist,
    get_blacklist,
    add_warn,
    remove_warn,
    get_warns,
    set_warn_limit,
    get_warn_limit,
)

logger = logging.getLogger(__name__)


def lang(string: str) -> str:
    return translation["eng"][string]


async def user_can_change_info(bot: Bot, chat_id: int, user_id: int, api_token: str, fun: bool) -> bool:
    a = await bot.get_chat_member(chat_id, api_token.split(":")[0])
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


async def user_can_restrict(bot: Bot, chat_id: int, user_id: int, api_token: str, fun: bool) -> bool:
    a = await bot.get_chat_member(chat_id, api_token.split(":")[0])
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


async def _parse_target_reason_timer(message: Message) -> tuple[Optional[int | str], Optional[str], Optional[int]]:
    """Parse moderation command arguments: target (id or @mention), reason text and timer in seconds."""
    user_id: Optional[int | str] = None
    reason: Optional[str] = None
    timer: Optional[int] = None

    args = list(message.text.split())
    if args:
        args.pop(0)  # drop command itself

    for arg in args:
        if arg.startswith("@"):
            if user_id is None:
                user_id = arg
        elif arg.isnumeric():
            if user_id is None or (isinstance(user_id, str) and user_id.startswith("@")):
                user_id = int(arg)
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

    return user_id, reason, timer


async def ban_command(bot: Bot, message: Message, api_token: str):
    a = await bot.get_chat_member(message.chat.id, api_token.split(":")[0])
    # If bot is not admin or doesn't have restrict permissions, deny action.
    if not getattr(a, "can_restrict_members", False):
        await message.reply(lang("bot_no_perm_restrict_members"))
        return
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    user_id, reason, timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    # Prevent banning the bot itself
    me = await bot.get_me()
    try:
        target_int = int(user_id)
    except Exception:
        target_int = None
    if target_int is not None and target_int == me.id:
        await message.reply("I can't ban myself")
        return

    until_date = int(time.time() + timer) if timer else None

    try:
        await bot.ban_chat_member(message.chat.id, target_int, until_date=until_date)

        timer_text = f"-time {timer}" if timer else ""
        reason_text = f"-reason {reason}" if reason else ""

        await message.reply(
            lang("banned").format(
                user_id=user_id,
                timer=timer_text,
                reason=reason_text,
                chat_id=message.chat.id,
            )
        )
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        await message.reply("Failed to ban user")


async def mute_command(bot: Bot, message: Message, api_token: str):
    a = await bot.get_chat_member(message.chat.id, api_token.split(":")[0])
    if not getattr(a, "can_restrict_members", False):
        await message.reply(lang("bot_no_perm_restrict_members"))
        return
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    user_id, reason, timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    # Prevent muting the bot itself
    me = await bot.get_me()
    try:
        target_int = int(user_id)
    except Exception:
        target_int = None
    if target_int is not None and target_int == me.id:
        await message.reply("I can't mute myself")
        return

    until_date = int(time.time() + timer) if timer else None

    permissions = types.ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
    )

    try:
        await bot.restrict_chat_member(
            message.chat.id,
            target_int,
            permissions=permissions,
            until_date=until_date,
        )

        timer_text = f"-time {timer}" if timer else ""
        reason_text = f"-reason {reason}" if reason else ""

        await message.reply(
            lang("muted").format(
                user_id=user_id,
                timer=timer_text,
                reason=reason_text,
                chat_id=message.chat.id,
            )
        )
    except Exception as e:
        logger.error(f"Error muting user: {e}")
        await message.reply("Failed to mute user")


async def warn_command(bot: Bot, message: Message, api_token: str):  # noqa: ARG001
    # Only check that user has restrict rights; bot capabilities are not required for warn.
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    user_id, reason, _timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    # Update warns counter in DB (even if not shown in message yet)
    await add_warn(message.chat.id, int(user_id))

    reason_text = f"-reason {reason}" if reason else ""

    await message.reply(
        lang("warned").format(
            user_id=user_id,
            reason=reason_text,
            chat_id=message.chat.id,
        )
    )


async def unwarn_command(bot: Bot, message: Message, api_token: str):  # noqa: ARG001
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    user_id, _reason, _timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    await remove_warn(message.chat.id, int(user_id))

    await message.reply(
        lang("unwarned").format(
            user_id=user_id,
            chat_id=message.chat.id,
        )
    )


async def limitwarn_command(bot: Bot, message: Message, api_token: str):  # noqa: ARG001
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    args = message.text.split()
    if len(args) == 1:
        current = await get_warn_limit(message.chat.id)
        if current is None:
            await message.reply(
                lang("warn_limit_current").format(
                    chat_id=message.chat.id,
                    warn_limit=0,
                )
            )
        else:
            await message.reply(
                lang("warn_limit_current").format(
                    chat_id=message.chat.id,
                    warn_limit=current,
                )
            )
        return

    try:
        new_limit = int(args[1])
    except ValueError:
        await message.reply(lang("warn_limit_invalid"))
        return

    if new_limit < 0:
        await message.reply(lang("warn_limit_invalid"))
        return

    await set_warn_limit(message.chat.id, new_limit)

    await message.reply(
        lang("warn_limit_set").format(
            chat_id=message.chat.id,
            warn_limit=new_limit,
        )
    )


async def addblacklist_command(bot: Bot, message: Message, api_token: str):  # noqa: ARG001
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    user_id, _reason, _timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    await add_to_blacklist(message.chat.id, int(user_id))

    await message.reply(
        lang("blacklist_added").format(
            user_id=user_id,
            chat_id=message.chat.id,
        )
    )


async def removeblacklist_command(bot: Bot, message: Message, api_token: str):  # noqa: ARG001
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    user_id, _reason, _timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    removed = await remove_from_blacklist(message.chat.id, int(user_id))

    if not removed:
        await message.reply(
            lang("blacklist_not_found").format(
                user_id=user_id,
                chat_id=message.chat.id,
            )
        )
        return

    await message.reply(
        lang("blacklist_removed").format(
            user_id=user_id,
            chat_id=message.chat.id,
        )
    )


async def blacklist_command(bot: Bot, message: Message, api_token: str):  # noqa: ARG001
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    users = await get_blacklist(message.chat.id)

    if not users:
        await message.reply(
            lang("blacklist_empty").format(
                chat_id=message.chat.id,
            )
        )
        return

    entries = "\n".join(str(u) for u in users)
    await message.reply(
        lang("blacklist_list_header").format(
            chat_id=message.chat.id,
            entries=entries,
        )
    )


async def unban_command(bot: Bot, message: Message, api_token: str):
    a = await bot.get_chat_member(message.chat.id, api_token.split(":")[0])
    if not getattr(a, "can_restrict_members", False):
        await message.reply(lang("bot_no_perm_restrict_members"))
        return
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    user_id, _reason, _timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    try:
        await bot.unban_chat_member(message.chat.id, int(user_id))
        await message.reply(
            lang("unbanned").format(
                user_id=user_id,
                chat_id=message.chat.id,
            )
        )
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")
        await message.reply("Failed to unban user")


async def unmute_command(bot: Bot, message: Message, api_token: str):
    a = await bot.get_chat_member(message.chat.id, api_token.split(":")[0])
    if not getattr(a, "can_restrict_members", False):
        await message.reply(lang("bot_no_perm_restrict_members"))
        return
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    user_id, _reason, _timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    permissions = types.ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )

    try:
        await bot.restrict_chat_member(
            message.chat.id,
            int(user_id),
            permissions=permissions,
            until_date=None,
        )
        await message.reply(
            lang("unmuted").format(
                user_id=user_id,
                chat_id=message.chat.id,
            )
        )
    except Exception as e:
        logger.error(f"Error unmuting user: {e}")
        await message.reply("Failed to unmute user")


async def kick_command(bot: Bot, message: Message, api_token: str):
    a = await bot.get_chat_member(message.chat.id, api_token.split(":")[0])
    if not getattr(a, "can_restrict_members", False):
        await message.reply(lang("bot_no_perm_restrict_members"))
        return

    user_id, reason, _timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    # Prevent kicking the bot itself
    me = await bot.get_me()
    try:
        target_int = int(user_id)
    except Exception:
        target_int = None
    if target_int is not None and target_int == me.id:
        await message.reply("I can't kick myself")
        return

    # First, try to ban (kick) the user. If this fails, treat as error.
    try:
        await bot.ban_chat_member(message.chat.id, target_int)
    except Exception as e:
        logger.error(f"Error banning user for kick: {e}")
        await message.reply("Failed to kick user")
        return

    # Send success message to chat immediately after successful ban.
    reason_text = f"-reason {reason}" if reason else ""
    await message.reply(
        lang("kicked").format(
            user_id=user_id,
            reason=reason_text,
            chat_id=message.chat.id,
        )
    )

    # Then best-effort unban (to allow rejoin). Errors here are non-fatal,
    # especially in basic groups where unban may not be supported.
    try:
        await bot.unban_chat_member(message.chat.id, target_int)
    except Exception as e:
        logger.warning(
            "Error unbanning after kick for user %s in chat %s: %s",
            target_int,
            message.chat.id,
            e,
        )


async def kickme_command(bot: Bot, message: Message, api_token: str):
    a = await bot.get_chat_member(message.chat.id, api_token.split(":")[0])
    if not getattr(a, "can_restrict_members", False):
        await message.reply(lang("bot_no_perm_restrict_members"))
        return

    # Don't allow admins/owner to /kickme
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status in ["administrator", "creator"]:
        await message.reply("Sorry, you должны work")
        return

    # First, try to ban (kick) the user. If this fails, treat as error.
    try:
        await bot.ban_chat_member(message.chat.id, message.from_user.id)
    except Exception as e:
        logger.error("Error self-kicking user %s: %s", message.from_user.id, e)
        await message.reply("Failed to kick you")
        return

    # Send info message to chat so others see that user kicked themselves.
    await message.reply(
        lang("kicked").format(
            user_id=message.from_user.id,
            reason="-reason self-kick",
            chat_id=message.chat.id,
        )
    )

    # Then best-effort unban (to allow rejoin). Errors here are non-fatal,
    # especially in basic groups where unban may not be supported.
    try:
        await bot.unban_chat_member(message.chat.id, message.from_user.id)
    except Exception as e:
        logger.warning(
            "Error self-unbanning after kick for user %s in chat %s: %s",
            message.from_user.id,
            message.chat.id,
            e,
        )


async def checkhistory_command(bot: Bot, message: Message, api_token: str):  # noqa: ARG001
    if not await user_can_restrict(bot, message.chat.id, message.from_user.id, api_token, False):
        await message.reply(lang("no_restmem_profile"))
        return

    user_id, _reason, _timer = await _parse_target_reason_timer(message)

    if user_id is None:
        await message.reply("/dev/null is not a user")
        return

    if isinstance(user_id, str) and user_id.startswith("@"):
        await message.reply(lang("mention_unreadable").format(user_id=user_id))
        return

    warns = await get_warns(message.chat.id, int(user_id))
    warn_limit = await get_warn_limit(message.chat.id) or 0
    bl = await get_blacklist(message.chat.id)
    blacklisted = "yes" if int(user_id) in bl else "no"

    await message.reply(
        lang("history").format(
            chat_id=message.chat.id,
            user_id=user_id,
            warns=warns,
            warn_limit=warn_limit,
            blacklisted=blacklisted,
        )
    )
