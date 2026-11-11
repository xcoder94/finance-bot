"""Notices are sent by a background task after commit (ux-r7); tests settle them explicitly."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import goal_notify


async def settle(session: AsyncSession | None = None) -> None:
    """Commit (releases the queue of a session used directly) and wait for background sends."""
    if session is not None:
        await session.commit()
    await goal_notify.drain_background()
