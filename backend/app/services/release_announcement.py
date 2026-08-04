from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Sequence

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from bot.onboarding import open_app_keyboard

RELEASE_ANNOUNCEMENT_TEXT = (
    "Теперь трату можно записать прямо здесь, сообщением.\n"
    "Напишите, например: `такси 25 тысяч`\n"
    "\n"
    "В приложении появились личные кошельки, цели и управление участниками."
)


async def eligible_users(
    session: AsyncSession, cutoff: datetime
) -> Sequence[User]:
    stmt = (
        select(User)
        .where(
            User.is_deleted.is_(False),
            User.created_at < cutoff,
            User.release_announcement_delivered_at.is_(None),
        )
        .order_by(User.created_at.asc())
    )
    return list(await session.scalars(stmt))


async def send_release_announcements(
    session: AsyncSession,
    bot: Bot,
    cutoff: datetime,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> int:
    users = await eligible_users(session, cutoff)
    if dry_run:
        return len(users)

    delivered_at = now or datetime.now(timezone.utc)
    markup = open_app_keyboard()
    sent = 0
    for user in users:
        kwargs: dict = {"parse_mode": "Markdown"}
        if markup is not None:
            kwargs["reply_markup"] = markup
        await bot.send_message(
            user.telegram_id,
            RELEASE_ANNOUNCEMENT_TEXT,
            **kwargs,
        )
        user.release_announcement_delivered_at = delivered_at
        await session.commit()
        sent += 1
    return sent
