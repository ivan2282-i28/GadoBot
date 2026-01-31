from typing import Optional, Tuple
from aiogram import types

async def parse_target_args(message: types.Message) -> Tuple[Optional[int], str, Optional[int]]:
    '''
    Parses arguments for moderation commands.
    Returns: (user_id, reason, duration_seconds)
    '''
    args = message.text.split()
    if args:
        args.pop(0) # Remove command

    user_id = None
    reason_parts = []
    timer = None

    # check reply
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id

    for arg in args:
        if arg.startswith("@"):
            # Handle mention logic if needed, usually we need ID
            pass 
        elif arg.isdigit():
            if not user_id:
                user_id = int(arg)
        elif arg.endswith(('d', 'h', 'm')) and arg[:-1].isdigit():
            val = int(arg[:-1])
            if arg.endswith('d'): timer = val * 86400
            elif arg.endswith('h'): timer = val * 3600
            elif arg.endswith('m'): timer = val * 60
        else:
            reason_parts.append(arg)

    reason = " ".join(reason_parts) if reason_parts else None
    return user_id, reason, timer