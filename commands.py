import html
import logging
import os
import random
import re
import subprocess
import time
from typing import Callable
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Chat, Message

from translation import translation


def _get_git_version() -> str:
    """Return short git commit hash for the current repo, or 'unknown'."""
    try:
        result = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return result.strip() or "unknown"
    except Exception:
        return "unknown"

BOT_VERSION = _get_git_version()

from db import (
    DB_PATH,
    get_all_chats,
    get_user,
    get_user_lang,
    register_chat as db_register_chat,
    register_user,
    set_user_lang,
)
from filters_service import (
    add_filter,
    get_chat_filters,
    parse_filter_command,
    remove_all_filters,
    remove_filter,
    send_filter_response,
)
from moderation import (
    ban_command,
    mute_command,
    warn_command,
    unwarn_command,
    limitwarn_command,
    unban_command,
    unmute_command,
    kick_command,
    kickme_command,
    checkhistory_command,
    blacklist_command,
    addblacklist_command,
    removeblacklist_command,
    user_can_change_info as mod_user_can_change_info,
    user_can_restrict as mod_user_can_restrict,
)

logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """Configure bot command list for private and group chats (non-admin commands)."""
    # Currently descriptions use English translations; can be extended per chat lang later.
    t = translation["eng"]
    user_commands = [
        types.BotCommand(command="start", description=t["cmd_start_desc"]),
        types.BotCommand(command="stats", description=t["cmd_stats_desc"]),
        types.BotCommand(command="stats_global", description=t["cmd_stats_global_desc"]),
        types.BotCommand(command="help", description=t["cmd_help_desc"]),
        types.BotCommand(command="lang", description=t["cmd_lang_desc"]),
        types.BotCommand(command="filter", description=t["cmd_filter_desc"]),
        types.BotCommand(command="filters", description=t["cmd_filters_desc"]),
        types.BotCommand(command="remove_filter", description=t["cmd_remove_filter_desc"]),
        types.BotCommand(command="remove_all_filters", description=t["cmd_remove_all_filters_desc"]),
        types.BotCommand(command="export", description=t["cmd_export_desc"]),
        types.BotCommand(command="import", description=t["cmd_import_desc"]),
        types.BotCommand(command="ban", description=t["cmd_ban_desc"]),
        types.BotCommand(command="unban", description=t["cmd_unban_desc"]),
        types.BotCommand(command="mute", description=t["cmd_mute_desc"]),
        types.BotCommand(command="unmute", description=t["cmd_unmute_desc"]),
        types.BotCommand(command="warn", description=t["cmd_warn_desc"]),
        types.BotCommand(command="unwarn", description=t["cmd_unwarn_desc"]),
        types.BotCommand(command="limitwarn", description=t["cmd_limitwarn_desc"]),
        types.BotCommand(command="kick", description=t["cmd_kick_desc"]),
        types.BotCommand(command="checkhistory", description=t["cmd_checkhistory_desc"]),
        types.BotCommand(command="blacklist", description=t["cmd_blacklist_desc"]),
        types.BotCommand(command="addblacklist", description=t["cmd_addblacklist_desc"]),
        types.BotCommand(command="removeblacklist", description=t["cmd_removeblacklist_desc"]),
    ]

    # Private chats
    await bot.set_my_commands(
        user_commands,
        scope=types.BotCommandScopeAllPrivateChats(),
    )

    # Group / supergroup chats
    await bot.set_my_commands(
        user_commands,
        scope=types.BotCommandScopeAllGroupChats(),
    )


def register_handlers(bot: Bot, dp: Dispatcher, api_token: str) -> None:
    """Register all bot commands and handlers on the given dispatcher."""

    # --- Helpers -----------------------------------------------------------

    admin_ids = {
        int(x)
        for x in os.getenv("ADMINS", "").replace(",", " ").split()
        if x.strip().isdigit()
    }

    def is_admin(user_id: int) -> bool:
        return user_id in admin_ids

    async def get_translations(message: Message):
        """Return translation dict for this user, using DB or Telegram language_code.

        Supported lang codes: ru, en, uk, kk, de, fr.
        They are mapped to translation keys: ru, eng, uk, kk, de, fr.
        """
        user_id = message.from_user.id
        db_lang = await get_user_lang(user_id)

        if db_lang:
            code = db_lang.lower()
        else:
            tg_code = (message.from_user.language_code or "").split("-")[0].lower()
            supported = {"ru", "en", "uk", "kk", "de", "fr"}
            code = tg_code if tg_code in supported else "en"
            await register_user(user_id, code)

        # Map external code to internal translation key
        if code == "ru":
            key = "ru"
        elif code == "uk":
            key = "uk"
        elif code == "kk":
            key = "kk"
        elif code == "de":
            key = "de"
        elif code == "fr":
            key = "fr"
        else:  # "en" or anything else -> English
            key = "eng"

        return translation[key]

    async def user_can_change_info(chat_id: int, user_id: int, fun: bool) -> bool:
        return await mod_user_can_change_info(bot, chat_id, user_id, api_token, fun)

    async def user_can_restrict(chat_id: int, user_id: int, fun: bool) -> bool:
        return await mod_user_can_restrict(bot, chat_id, user_id, api_token, fun)

    async def register_chat(chat: Chat) -> None:
        await db_register_chat(chat.id, chat.full_name, chat.username)

    def escape_html(text: str) -> str:
        if not text:
            return ""
        return html.escape(text)

    async def send_message_to_all_chats(text: str) -> None:
        chats = await get_all_chats()
        for chat_row in chats:
            try:
                await bot.send_message(chat_id=chat_row[0], text=text,parse_mode=ParseMode.HTML)
            except Exception:
                # Ignore failures when sending broadcast
                pass

    
    @dp.message(Command("ADM_send"))
    async def cmd_adm_send(message: Message) -> None:
        if not is_admin(message.from_user.id):
            await message.answer("Who are YOU?")
            return

        # Split only once: "/ADM_send <text>" -> ["/ADM_send", "<text>"]
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await message.answer("Usage: /ADM_send <text>")
            return

        text = parts[1].strip()
        await send_message_to_all_chats(text)
        await message.answer("OK")

    # --- Public: basic commands ------------------------------------------

    @dp.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        t = await get_translations(message)
        help_text = t["start_message"].format(version=BOT_VERSION)
        await message.answer(
            help_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    @dp.message(Command("stats"))
    async def cmd_stats(message: Message) -> None:
        t = await get_translations(message)
        help_text = (
            f"{t['stats_header']} {message.chat.id}\n"
            f"{t['stats_name']}: {message.chat.full_name}\n"
            f"{t['stats_members']}: {await message.chat.get_member_count()}\n"
            f"{t['stats_username']}: {message.chat.username}"
        )
        await message.answer(help_text, parse_mode=ParseMode.HTML)

    @dp.message(Command("stats_global"))
    async def cmd_stats_global(message: Message) -> None:
        t = await get_translations(message)
        chats = await get_all_chats()
        if "-root" in message.text:
            if is_admin(message.from_user.id):
                help_text = (
                    f"{t['global_stats_header_root']}\n"
                    f"{t['global_stats_chat_count']}: {len(chats)}\n"
                    f"{chats}"
                )
            else:
                help_text = (
                    f"{t['global_stats_header']}\n"
                    "I do not believe you! YOU ARE NOT ROOT"
                )
        else:
            help_text = (
                f"{t['global_stats_header']}\n"
                f"{t['global_stats_chat_count']}: {len(chats)}\n"
            )
        await message.answer(help_text, parse_mode=ParseMode.HTML)

    @dp.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        t = await get_translations(message)
        if "-misc" in message.text:
            help_text = t["help_misc"]
        elif "-filters" in message.text:
            help_text = t["help_filters"]
        elif "-mod" in message.text or "-moderation" in message.text:
            help_text = t["help_moderation"]
        else:
            help_text = t["help"]
        await message.answer(help_text, parse_mode=ParseMode.HTML)

    @dp.message(Command("lang"))
    async def cmd_lang(message: Message) -> None:
        parts = message.text.split()

        # For now, language is per-user, not per-chat
        current_t = await get_translations(message)

        # /lang -> show available languages
        if len(parts) == 1:
            await message.answer(current_t["lang_help"])
            return

        # /lang <code>
        lang_code = parts[1].lower()

        # Supported external codes (what user types)
        supported_langs = {"ru", "en", "uk", "kk", "de", "fr"}

        if lang_code not in supported_langs:
            await message.answer(current_t["lang_invalid"].format(lang=lang_code))
            return

        # Ensure user exists, then update preferred language code as typed
        await register_user(message.from_user.id)
        await set_user_lang(message.from_user.id, lang_code)

        # Map external code to translation key for confirmation message
        if lang_code == "ru":
            t = translation["ru"]
        elif lang_code == "uk":
            t = translation["uk"]
        elif lang_code == "kk":
            t = translation["kk"]
        elif lang_code == "de":
            t = translation["de"]
        elif lang_code == "fr":
            t = translation["fr"]
        else:  # "en"
            t = translation["eng"]

        await message.answer(t["lang_set_success"].format(lang=lang_code))

    # --- Filters module ----------------------------------------------------

    @dp.message(Command("filter"))
    async def cmd_filter(message: Message) -> None:
        t = await get_translations(message)
        if not await user_can_change_info(message.chat.id, message.from_user.id, True):
            await message.answer(t["no_perm_profile"])
            return

        if message.reply_to_message and message.reply_to_message.content_type in [
            "photo",
            "video",
            "document",
            "animation",
        ]:
            parts = message.text.split(" ", 1)
            if len(parts) < 2:
                await message.answer(t["filter_usage_media"])
                return

            trigger = parts[1].strip()
            response = ""
            if message.reply_to_message.caption:
                response = message.reply_to_message.caption
            elif message.reply_to_message.text:
                response = message.reply_to_message.text

            file_id = None
            file_type = message.reply_to_message.content_type

            if file_type == "photo":
                file_id = message.reply_to_message.photo[-1].file_id
            elif file_type == "video":
                file_id = message.reply_to_message.video.file_id
            elif file_type == "document":
                file_id = message.reply_to_message.document.file_id
            elif file_type == "animation":
                file_id = message.reply_to_message.animation.file_id

            filters = await get_chat_filters(message.chat.id)
            for f in filters:
                if f[0] == trigger:
                    await message.answer(t["already_exists"])
                    return

            await add_filter(message.chat.id, trigger, response, file_id, file_type)

            await message.answer(
                t["filter_added_media"].format(trigger=escape_html(trigger)),
                parse_mode=ParseMode.HTML,
            )
        else:
            trigger, response = parse_filter_command(message.text)
            if not trigger or not response:
                await message.answer(t["filter_usage_text"])
                return

            filters = await get_chat_filters(message.chat.id)
            for f in filters:
                if f[0] == trigger:
                    await message.answer(t["already_exists"])
                    return

            await add_filter(message.chat.id, trigger, response)

            if trigger.startswith('r"') and trigger.endswith('"'):
                filter_type = t["regex"]
                clean_trigger = trigger[2:-1]
            else:
                filter_type = t["text"]
                clean_trigger = trigger

            await message.answer(
                t["filter_added_text"].format(
                    filter_type=filter_type,
                    trigger=escape_html(clean_trigger),
                ),
                parse_mode=ParseMode.HTML,
            )

    @dp.message(Command("filters"))
    async def cmd_filters(message: Message) -> None:
        t = await get_translations(message)
        filters = await get_chat_filters(message.chat.id)
        if not filters:
            await message.answer(t["not_exists_filter_all"])
            return

        filters_list = []
        for trigger, response, file_id, file_type in filters:
            filters_list.append(f"<code>{escape_html(trigger)}</code>")

        filters_list.sort(key=lambda x: x[0])

        filters_text = "\n".join(filters_list)
        await message.answer(
            t["filters_list"].format(filters_text=filters_text),
            parse_mode=ParseMode.HTML,
        )

    @dp.message(Command("remove_filter"))
    async def cmd_remove_filter(message: Message) -> None:
        t = await get_translations(message)
        if not await user_can_change_info(message.chat.id, message.from_user.id, True):
            await message.answer(t["no_perm_profile"])
            return

        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            await message.answer(t["remove_filter_usage"])
            return

        trigger = parts[1].strip()

        success = await remove_filter(message.chat.id, trigger)

        if not success:
            await message.answer(t["remove_filter_not_found"])
            return

        await message.answer(
            t["remove_filter_success"].format(trigger=escape_html(trigger)),
            parse_mode=ParseMode.HTML,
        )

    @dp.message(Command("remove_all_filters"))
    async def cmd_remove_all_filters(message: Message) -> None:
        t = await get_translations(message)
        if not await user_can_change_info(message.chat.id, message.from_user.id, True):
            await message.answer(t["no_perm_profile"])
            return

        count = await remove_all_filters(message.chat.id)

        if count == 0:
            await message.answer(t["not_exists_filter_all"])
            return

        await message.answer(t["remove_all_filters_success"].format(count=count))

    # --- Moderation --------------------------------------------------------

    @dp.message(Command("ban"))
    async def cmd_ban(message: Message) -> None:
        await ban_command(bot, message, api_token)

    @dp.message(Command("unban"))
    async def cmd_unban(message: Message) -> None:
        await unban_command(bot, message, api_token)

    @dp.message(Command("mute"))
    async def cmd_mute(message: Message) -> None:
        await mute_command(bot, message, api_token)

    @dp.message(Command("unmute"))
    async def cmd_unmute(message: Message) -> None:
        await unmute_command(bot, message, api_token)

    @dp.message(Command("warn"))
    async def cmd_warn(message: Message) -> None:
        await warn_command(bot, message, api_token)

    @dp.message(Command("unwarn"))
    async def cmd_unwarn(message: Message) -> None:
        await unwarn_command(bot, message, api_token)

    @dp.message(Command("limitwarn"))
    async def cmd_limitwarn(message: Message) -> None:
        await limitwarn_command(bot, message, api_token)

    @dp.message(Command("kick"))
    async def cmd_kick(message: Message) -> None:
        await kick_command(bot, message, api_token)

    @dp.message(Command("kickme"))
    async def cmd_kickme(message: Message) -> None:
        await kickme_command(bot, message, api_token)

    @dp.message(Command("checkhistory"))
    async def cmd_checkhistory(message: Message) -> None:
        await checkhistory_command(bot, message, api_token)

    @dp.message(Command("blacklist"))
    async def cmd_blacklist(message: Message) -> None:
        await blacklist_command(bot, message, api_token)

    @dp.message(Command("addblacklist"))
    async def cmd_addblacklist(message: Message) -> None:
        await addblacklist_command(bot, message, api_token)

    @dp.message(Command("removeblacklist"))
    async def cmd_removeblacklist(message: Message) -> None:
        await removeblacklist_command(bot, message, api_token)

    # --- Filters export/import --------------------------------------------

    @dp.message(Command("export"))
    async def exportcmd(message: Message) -> None:
        filters = await get_chat_filters(message.chat.id)
        fstr = ""
        for trigger, response, file_id, file_type in filters:
            fstr += f"~{trigger};{response};{file_id or 'None'};{file_type or 'None'}\n"

        file_content = (
            "GBTP001:GADOBOT Transmit Protocol v0.0.1\nBEGIN\n" f"{fstr}"
        )

        await message.answer_document(
            document=types.BufferedInputFile(
                file_content.encode(),
                filename=f"gadobot_backup_{message.chat.id}_{int(time.time())}.gbtp",
            ),
            caption="GBTP001: Backup file generated",
        )

    @dp.message(Command("import"))
    async def importcmd(message: Message) -> None:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)

        if not isinstance(member, types.ChatMemberOwner):
            await message.answer("GBTP MANAGMENT SYSTEM: NOT ENOUGH RIGHTS")
            return

        if not message.document:
            await message.answer(
                "GBTP MANAGMENT SYSTEM:\n"
                "Please attach a backup file to import.\n"
                "How to use: Reply to this message with /import and attach the .gbtp file",
            )
            return

        if not message.document.file_name.endswith(".gbtp"):
            await message.answer(
                "GBTP MANAGMENT SYSTEM: Invalid file format. Please use .gbtp backup files"
            )
            return

        try:
            file_info = await bot.get_file(message.document.file_id)
            downloaded_file = await bot.download_file(file_info.file_path)

            file_content = downloaded_file.read().decode("utf-8")

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

                    pload = [None if entry == "None" else entry for entry in pload]
                    payload_real.append((pload[0], pload[1], pload[2], pload[3]))

                await remove_all_filters(message.chat.id)
                for trigger, response, file_id, file_type in payload_real:
                    await add_filter(
                        message.chat.id,
                        trigger,
                        response,
                        file_id,
                        file_type,
                    )

                await message.answer("GBTP MANAGMENT SYSTEM: Import successful!")
            else:
                await message.answer(
                    "GBTP MANAGMENT SYSTEM: This GBTP type is not supported"
                )

        except Exception as exc:  # noqa: BLE001
            await message.answer(
                "GBTP MANAGMENT SYSTEM: Import failed! Your chat db was wiped for stability:3"
            )
            logger.error("Import error: %s", exc)
            await remove_all_filters(message.chat.id)

    # --- Generic text handler ---------------------------------------------

    @dp.message(F.text)
    async def message_handler(message: Message) -> None:
        await register_chat(message.chat)
        filters = await get_chat_filters(message.chat.id)
        if not filters:
            return

        text = message.text.lower() if message.text else ""
        for trigger, response, file_id, file_type in filters:
            trigger_lower = trigger.lower()
            if trigger.startswith('r"') and trigger.endswith('"'):
                pattern = trigger[2:-1]
                try:
                    if re.search(pattern, message.text or "", re.IGNORECASE):
                        await send_filter_response(
                            bot, message, response, file_id, file_type
                        )
                        break
                except re.error as exc:  # noqa: BLE001
                    logger.error("Regex error in pattern '%s': %s", pattern, exc)

            elif (
                f" {trigger_lower} " in text
                or text.startswith(f"{trigger_lower} ")
                or text.endswith(f" {trigger_lower}")
                or text == trigger_lower
            ):
                await send_filter_response(bot, message, response, file_id, file_type)
                break
