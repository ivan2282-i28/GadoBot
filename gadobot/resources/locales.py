# Centralized translation strings
TR = {
    "eng": {
        "bot_started": "Bot started",
        "bot_no_perm": "I don't have permission to restrict members.",
        "user_no_perm": "You don't have permission to use this.",
        "invalid_user": "User not found or invalid.",
        "mention_error": "I cannot resolve mentions. Please reply to the user or use their ID.",
        "self_action_error": "I cannot perform this action on myself.",
        "action_failed": "Failed to perform action.",
        
        "banned": "<a href='tg://user?id={user_id}'>User</a> banned. {timer} {reason}",
        "muted": "<a href='tg://user?id={user_id}'>User</a> muted. {timer} {reason}",
        "kicked": "<a href='tg://user?id={user_id}'>User</a> kicked. {reason}",
        "warned": "<a href='tg://user?id={user_id}'>User</a> warned. {reason} ({count}/{limit})",
        "unwarned": "<a href='tg://user?id={user_id}'>User</a> unwarned.",
        "unbanned": "User {user_id} unbanned.",
        "unmuted": "User {user_id} unmuted.",
        
        "warn_limit_curr": "Current warn limit: {limit}",
        "warn_limit_set": "Warn limit set to {limit}",
        "warn_limit_invalid": "Invalid limit number.",
        
        "blacklist_added": "User {user_id} added to blacklist.",
        "blacklist_removed": "User {user_id} removed from blacklist.",
        "blacklist_not_found": "User is not in blacklist.",
        "blacklist_empty": "Blacklist is empty.",
        "blacklist_list": "Blacklist: \
{entries}",
        
        "history": "History for {user_id}: \
Warns: {warns}/{limit} \
Blacklisted: {bl}",
        "kickme_admin": "Sorry, you must work.",
        "kickme_self": "User {user_id} kicked themselves.",
        
        "filter_added": "Filter added: {trigger}",
        "filter_removed": "Filter removed.",
        "filters_cleared": "All filters cleared."
    }
}

def lang(key: str, **kwargs) -> str:
    # Defaults to English for now
    text = TR["eng"].get(key, f"MISSING:{key}")
    if kwargs:
        return text.format(**kwargs)
    return text