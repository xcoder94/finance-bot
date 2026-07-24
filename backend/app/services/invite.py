from aiogram import Bot


_bot_username: str | None = None


async def cache_bot_username(bot: Bot) -> None:
    global _bot_username
    bot_info = await bot.get_me()
    if bot_info.username is None:
        raise RuntimeError("Telegram bot has no username")
    _bot_username = bot_info.username


def get_cached_bot_username() -> str | None:
    return _bot_username


def build_invite_link(bot_username: str, invite_token: str) -> str:
    return f"https://t.me/{bot_username}?start=invite_{invite_token}"
