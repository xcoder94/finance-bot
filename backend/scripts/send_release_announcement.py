"""Send the MVP2 release announcement once to eligible existing users.

Customer-fired only. Never imported by bot startup, scheduler, or migrations.

Run from backend/:
    python scripts/send_release_announcement.py --cutoff 2026-08-04T12:00:00+00:00
    python scripts/send_release_announcement.py --cutoff 2026-08-04T12:00:00+00:00 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from aiogram import Bot

from app.config import BOT_TOKEN
from app.db import async_session_factory, dispose_engine
from app.services.release_announcement import send_release_announcements


def parse_cutoff(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise SystemExit("--cutoff must include a timezone offset (ISO-8601)")
    return dt


async def run(cutoff: datetime, dry_run: bool) -> int:
    bot = Bot(token=BOT_TOKEN)
    try:
        async with async_session_factory() as session:
            return await send_release_announcements(
                session, bot, cutoff, dry_run=dry_run
            )
    finally:
        await bot.session.close()
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cutoff",
        required=True,
        help="ISO-8601 timestamp; only users created BEFORE this receive the message.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many users would receive it; send nothing.",
    )
    args = parser.parse_args()
    cutoff = parse_cutoff(args.cutoff.strip())
    count = asyncio.run(run(cutoff, args.dry_run))
    if args.dry_run:
        print(f"dry-run: {count} user(s) would receive the announcement")
    else:
        print(f"sent: {count} user(s)")


if __name__ == "__main__":
    main()
