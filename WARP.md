# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Environment & Setup

- Runtime: Python 3.11+ (tested with 3.11.2 and 3.13.7).
- Install dependencies in an activated virtual environment:
  - `pip install -r requirements.txt`
- Configuration:
  - Copy `.env_template` to `.env` (if present).
  - Set `BOT_TOKEN` in `.env` to the token from `@BotFather`.

## Common Commands

All commands assume you are in the project root (the directory containing `main.py`).

### Run the bot

- Start the bot:
  - `python main.py`

### Dependencies & updates

- Install / update dependencies after pulling changes:
  - `pip install -r requirements.txt`

### Linting & tests

- There is currently no dedicated lint or test configuration in this repository.
- If you add tooling (e.g., `pytest`, `ruff`, `flake8`), update this section with the canonical commands.

## High-level Architecture

### Overview

This repository implements a Telegram bot using **aiogram 3** with:

- A **filter system**: per-chat text/regex/media filters that trigger automatic replies.
- A **moderation module**: basic `/ban` command and filter-based bans.
- Simple **internationalization** via a translation dictionary.
- **SQLite** storage via `aiosqlite`.

The bot exposes user- and admin-facing commands via aiogram handlers defined in `main.py`.

### Entry point & bot lifecycle (`main.py`)

- `main()` is the entry point:
  - Calls `init_db()` to create/update the SQLite database (`gado.db`) and ensure required tables exist (`filters`, `chats`, `cards`, `users`).
  - Calls `check_and_reroll_duplicate_cards()` at startup to normalize existing card data (re-roll or remove duplicates).
  - Starts polling via `dp.start_polling(bot)`.
- `BOT_TOKEN` is read from environment (`BOT_TOKEN`), loaded via `python-dotenv`. The bot will raise if `BOT_TOKEN` is not set.

### Data storage (`aiosqlite` + `gado.db`)

The bot uses a single SQLite database file (`gado.db`) with these concerns:

- **chats**: chat metadata and language code
  - `chat_id`, `name`, `username`, `lang`.
  - Managed via `register_chat()`, `get_chat()`, `get_all_chats()`.
- **users**: Telegram users known to the bot
  - `user_id`, `rc_cd` (card roll cooldown), timestamps.
  - Managed via `register_user()`, `get_user()`, `update_user_cooldown()`, `reset_user_cooldown()`.
- **cards**: user card ownership
  - `user_id`, `card_id`, `created_at`.
  - Managed via `add_user_card()`, `get_user_unique_cards()`, `get_user_cards_count()`, `get_card_by_index()`, `remove_user_card()`.
- **filters**: per-chat filter definitions
  - `chat_id`, `trigger`, `response`, optional `file_id` and `file_type`.
  - Managed via `add_filter()`, `get_chat_filters()`, `remove_filter()`, `remove_all_filters()`.

All DB access is asynchronous via `aiosqlite.connect(db_path)`.

### Card system

- In-memory `cards` dict defines card metadata: `{card_id: (rarity, name, image_path)}`.
- Core behaviors:
  - **Rolling** (`/rc`, `/roll-card`, `/rollcard`):
    - Enforces per-user cooldown (`rc_cd` in `users`).
    - Chooses a random card from `cards`.
    - Uses `add_user_card()` which:
      - Inserts the card.
      - If the user already owns it, re-rolls into a card the user does not have yet (if possible) by updating the last insert.
  - **Startup normalization**: `check_and_reroll_duplicate_cards()` scans existing `cards` rows and ensures each user has at most one copy of a card, rerolling/deleting extras.
  - **Viewing cards** (`/sc`, `/seecards`, `/see-cards`):
    - `get_user_unique_cards()` returns distinct `card_id`s per user.
    - `user_pagination` dict stores pagination state per user.
    - `show_card_page()` renders a single card page with inline keyboard navigation.
  - **Image handling**:
    - `send_card_with_image()` and `show_card_page()` try multiple path variants to find the card image under `cards/`.

- Admin card management commands (restricted to the hard-coded owner ID `1999559891`):
  - `/ADM_add_card` → `add_card_to_system()` to extend the `cards` dict at runtime.
  - `/ADM_give_card` → gives a card to a user, optionally notifying them via DM.
  - `/ADM_remove_card` → `remove_card_from_system()`.
  - `/ADM_remove_user_card` → remove a card from a specific user.
  - `/ADM_list_cards`, `/ADM_check_images` → diagnostic utilities.

When editing or adding card-related features, keep the separation between **in-memory card metadata** (the `cards` dict) and **persistent ownership** (the `cards` table).

### Filter system

Filters are per-chat rules that trigger replies or media responses.

- Storage in the `filters` table:
  - `trigger` is either:
    - a plain text phrase, or
    - a regex pattern wrapped as `r"pattern"`.
  - `response` is plain text, or a special `b::` prefix for ban behavior.
  - `file_id`/`file_type` (photo, video, document, animation) for media filters.

- Commands:
  - `/filter` (text or media reply) → `cmd_filter()` parses the command, ensures uniqueness per trigger, and calls `add_filter()`.
  - `/filters` → list triggers using `get_chat_filters()`.
  - `/remove_filter`, `/remove_all_filters` → delete from DB.
  - `/export` → serializes all filters for a chat into a custom `GBTP001` format and sends it as a `.gbtp` document.
  - `/import` → only the chat owner can import; downloads a `.gbtp` file, parses it, wipes existing filters for the chat, and recreates them.

- Runtime matching:
  - `message_handler()` listens to all text messages (`@dp.message(F.text)`):
    - For each filter:
      - If trigger is regex-like (`r"pattern"`), uses `re.search` on the message text.
      - Otherwise, uses simple case-insensitive word-boundary style matching.
    - If matched, delegates to `send_filter_response()`.
  - `send_filter_response()`:
    - If `file_id`/`file_type` set, replies with the stored media.
    - If `response` starts with `b::`, interprets the suffix as a ban duration and bans the sender.
    - Else, replies with `response` text.

When adding new filter behaviors, prefer extending `send_filter_response()` or the GBTP import/export format rather than scattering new logic.

### Moderation

- `/ban` command implements timed or permanent bans based on arguments and/or replied message:
  - Parses user ID or mention, optional reason, and duration suffix (`d`, `h`, `m`).
  - Checks bot permissions and the caller's admin rights via `user_can_restrict()`.
  - Calls `bot.ban_chat_member()` with optional `until_date`.
  - Replies using localized `"banned"` message from translations.
- Filter-based bans (`b::...` responses) reuse the same Telegram ban API.

Any new moderation commands should follow the pattern of:

- A top-level handler function with `@dp.message(Command(...))`.
- Permission checks using `user_can_change_info()` / `user_can_restrict()` or analogous helpers.

### Internationalization (`translation.py`)

- `translation.py` exposes a `translation` dict keyed by language code (`"ru"`, `"eng"`).
- `lang(string: str)` in `main.py` currently returns `translation["eng"][string]` regardless of chat language.
- Translation usage patterns:
  - All user-facing text in command handlers should ideally be retrieved through `lang()` or the `translation` dict.
  - Messages often use `ParseMode.HTML` and rely on `escape_html()` for safe interpolation.

If you introduce new user-visible strings, add them to both language sections in `translation.py` and reference them via `lang()`.

### Admin-only flows & broadcasting

- Admin-only commands are guarded by a hard-coded user ID check (`1999559891`).
- Global broadcast:
  - `/ADM_send` (duplicated handler) uses `send_message_to_all_chats()` to send a text message to every chat known in the `chats` table.
  - `send_message_to_all_chats()` iterates over `get_all_chats()` and calls `bot.send_message()` for each, ignoring failures.

When modifying admin-only behavior, ensure the owner ID checks remain consistent or are refactored into a single constant.

## Notes for Future Changes

- If you add tests, linting, or type-checking, update **Common Commands** accordingly so future agents can run them.
- Keep new features aligned with the current architecture: asynchronous DB access in `main.py`, translation strings in `translation.py`, and aiogram handlers declared via decorators on the shared `Dispatcher` instance.
