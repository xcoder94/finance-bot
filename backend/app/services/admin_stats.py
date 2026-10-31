"""Read-only admin statistics. Counts and dates only: no amounts, names of wallets/families,
categories or comments are ever selected here (admin-design §3)."""

from __future__ import annotations

import base64
import re
import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import DateTime, Integer, bindparam, func, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_tracking import UserDailyActivity
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.admin import (
    ActiveUsers,
    AdminOverview,
    AdminUserRow,
    AdminUsersPage,
    DailyActive,
    Retention,
    RetentionBlock,
    Totals,
    Windows,
)
from app.services.activity import TASHKENT, tashkent_today

CHART_DAYS = 30
MAX_QUERY_LENGTH = 64


class InvalidCursor(ValueError):
    pass


def day_start_utc(day: date) -> datetime:
    """00:00 of a Tashkent day as an aware UTC instant (Tashkent is UTC+5, no DST)."""
    return datetime.combine(day, time.min, TASHKENT).astimezone(UTC)


def _since(today: date, days: int) -> datetime:
    """Start of the window of `days` Tashkent days ending today (today included)."""
    return day_start_utc(today - timedelta(days=days - 1))


async def _windows(session: AsyncSession, model, today: date, *extra) -> Windows:
    s1, s7, s30 = _since(today, 1), _since(today, 7), _since(today, 30)
    row = (
        await session.execute(
            select(
                func.count().filter(model.created_at >= s1),
                func.count().filter(model.created_at >= s7),
                func.count(),
            ).where(model.created_at >= s30, model.is_deleted.is_(False), *extra)
        )
    ).one()
    return Windows(today=row[0], d7=row[1], d30=row[2])


async def _totals(session: AsyncSession) -> Totals:
    users = await session.scalar(
        select(func.count()).select_from(User).where(User.is_deleted.is_(False))
    )
    families = await session.scalar(
        select(func.count()).select_from(FamilyBudget).where(FamilyBudget.is_deleted.is_(False))
    )
    multi = (
        select(User.family_budget_id)
        .where(User.is_deleted.is_(False))
        .group_by(User.family_budget_id)
        .having(func.count() >= 2)
        .subquery()
    )
    families_multi = await session.scalar(
        select(func.count())
        .select_from(multi)
        .join(FamilyBudget, FamilyBudget.id == multi.c.family_budget_id)
        .where(FamilyBudget.is_deleted.is_(False))
    )
    return Totals(users=users or 0, families=families or 0, families_multi=families_multi or 0)


async def _active(session: AsyncSession, today: date) -> ActiveUsers:
    # Windows are nested (day <= week <= month): one scan, latest active day per user.
    last = (
        select(UserDailyActivity.user_id, func.max(UserDailyActivity.day).label("last_day"))
        .join(User, User.id == UserDailyActivity.user_id)
        .where(
            User.is_deleted.is_(False),
            UserDailyActivity.day.between(today - timedelta(days=CHART_DAYS - 1), today),
        )
        .group_by(UserDailyActivity.user_id)
        .subquery()
    )
    row = (
        await session.execute(
            select(
                func.count().filter(last.c.last_day >= today),
                func.count().filter(last.c.last_day >= today - timedelta(days=6)),
                func.count(),
            ).select_from(last)
        )
    ).one()
    return ActiveUsers(dau=row[0], wau=row[1], mau=row[2])


async def _chart(session: AsyncSession, today: date) -> list[DailyActive]:
    first = today - timedelta(days=CHART_DAYS - 1)
    rows = await session.execute(
        select(UserDailyActivity.day, func.count())
        .join(User, User.id == UserDailyActivity.user_id)
        .where(UserDailyActivity.day.between(first, today), User.is_deleted.is_(False))
        .group_by(UserDailyActivity.day)
    )
    counts = {day: n for day, n in rows}
    return [
        DailyActive(day=first + timedelta(days=i), users=counts.get(first + timedelta(days=i), 0))
        for i in range(CHART_DAYS)
    ]


_COHORT_SQL = text(
    """
    WITH c AS (
      SELECT id, (created_at AT TIME ZONE 'Asia/Tashkent')::date AS reg
        FROM users
       WHERE NOT is_deleted AND created_at >= :c_from AND created_at < :c_to)
    SELECT (SELECT count(*) FROM c),
           (SELECT count(DISTINCT c.id)
              FROM c JOIN user_daily_activity a
                ON a.user_id = c.id AND a.day BETWEEN c.reg + :lo AND c.reg + :hi
             WHERE a.day BETWEEN :b_from AND :b_to)
    """
).bindparams(
    bindparam("c_from", type_=DateTime(timezone=True)),
    bindparam("c_to", type_=DateTime(timezone=True)),
    bindparam("lo", type_=Integer),
    bindparam("hi", type_=Integer),
)


async def _retention_one(
    session: AsyncSession,
    today: date,
    since: date | None,
    *,
    cohort_from: int,
    cohort_to: int,
    lo: int,
    hi: int,
) -> Retention:
    """Cohort = registered (Tashkent day) in [today-cohort_from, today-cohort_to] AND after
    the first activity day (decision SA #2: nobody registered before accounting began).
    Returned = active on at least one day of [reg+lo, reg+hi]. Windows are always closed."""
    if since is None:
        return Retention(returned=0, cohort=0, percent=None)
    first = max(today - timedelta(days=cohort_from), since + timedelta(days=1))
    last = today - timedelta(days=cohort_to)
    if first > last:
        return Retention(returned=0, cohort=0, percent=None)
    n_cohort, n_returned = (
        await session.execute(
            _COHORT_SQL,
            {
                "c_from": day_start_utc(first),
                "c_to": day_start_utc(last + timedelta(days=1)),
                "lo": lo,
                "hi": hi,
                # constant bound: turns the activity probe into one PK range scan (R8)
                "b_from": today - timedelta(days=36),
                "b_to": today - timedelta(days=1),
            },
        )
    ).one()
    percent = round(n_returned * 100 / n_cohort, 1) if n_cohort else None
    return Retention(returned=n_returned, cohort=n_cohort, percent=percent)


async def build_overview(session: AsyncSession, now: datetime) -> AdminOverview:
    today = tashkent_today(now)
    since = await session.scalar(select(func.min(UserDailyActivity.day)))
    return AdminOverview(
        totals=await _totals(session),
        new_users=await _windows(session, User, today),
        new_families=await _windows(session, FamilyBudget, today),
        active=await _active(session, today),
        retention=RetentionBlock(
            d7=await _retention_one(
                session, today, since, cohort_from=43, cohort_to=14, lo=7, hi=13
            ),
            d30=await _retention_one(
                session, today, since, cohort_from=66, cohort_to=37, lo=30, hi=36
            ),
        ),
        daily_active=await _chart(session, today),
        activity_since=since,
    )


# ---- users list -------------------------------------------------------------------------


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _search_condition(q: str):
    pattern = f"%{_escape_like(q)}%"
    conditions = [
        User.first_name.ilike(pattern, escape="\\"),
        User.username.ilike(pattern, escape="\\"),
        User.phone.ilike(pattern, escape="\\"),
    ]
    if q.startswith("@") and len(q) > 1:
        conditions.append(User.username.ilike(f"%{_escape_like(q[1:])}%", escape="\\"))
    digits = re.sub(r"[\s\-()]", "", q)
    if digits and digits != q and re.fullmatch(r"\+?[0-9]+", digits):
        conditions.append(User.phone.ilike(f"%{_escape_like(digits)}%", escape="\\"))
    return or_(*conditions)


def encode_cursor(created_at: datetime, user_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{user_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        stamp, ident = base64.urlsafe_b64decode(padded.encode()).decode().split("|")
        created_at = datetime.fromisoformat(stamp)
        if created_at.tzinfo is None:
            raise ValueError
        return created_at, uuid.UUID(ident)
    except Exception:
        raise InvalidCursor from None


def _tashkent_iso(value: datetime | None) -> str | None:
    return value.astimezone(TASHKENT).isoformat() if value is not None else None


async def list_users(
    session: AsyncSession, *, q: str | None, cursor: str | None, limit: int
) -> AdminUsersPage:
    q = (q or "").strip()
    live = [User.is_deleted.is_(False)]
    if q:
        live.append(_search_condition(q))

    total = await session.scalar(select(func.count()).select_from(User).where(*live))

    page_filter = list(live)
    if cursor:
        c_at, c_id = decode_cursor(cursor)
        page_filter.append(tuple_(User.created_at, User.id) < tuple_(c_at, c_id))
    users = (
        (
            await session.execute(
                select(User)
                .where(*page_filter)
                .order_by(User.created_at.desc(), User.id.desc())
                .limit(limit + 1)
            )
        )
        .scalars()
        .all()
    )
    has_more = len(users) > limit
    users = users[:limit]

    family_sizes: dict[uuid.UUID, int] = {}
    op_counts: dict[uuid.UUID, int] = {}
    if users:
        family_ids = {u.family_budget_id for u in users}
        size_rows = await session.execute(
            select(User.family_budget_id, func.count())
            .where(User.family_budget_id.in_(family_ids), User.is_deleted.is_(False))
            .group_by(User.family_budget_id)
        )
        family_sizes = {fid: n for fid, n in size_rows}
        op_rows = await session.execute(
            select(Transaction.created_by_user_id, func.count())
            .where(
                Transaction.created_by_user_id.in_([u.id for u in users]),
                Transaction.is_deleted.is_(False),
                Transaction.is_demo.is_(False),
            )
            .group_by(Transaction.created_by_user_id)
        )
        op_counts = {uid: n for uid, n in op_rows}

    items = [
        AdminUserRow(
            id=u.id,
            first_name=u.first_name,
            username=u.username,
            phone=u.phone,
            language=u.language,
            registered_at=_tashkent_iso(u.created_at),
            last_seen_at=_tashkent_iso(u.last_seen_at),
            family_members=family_sizes.get(u.family_budget_id, 1),
            family_role=u.role,
            operations_count=op_counts.get(u.id, 0),
        )
        for u in users
    ]
    next_cursor = encode_cursor(users[-1].created_at, users[-1].id) if has_more else None
    return AdminUsersPage(items=items, total=total or 0, next_cursor=next_cursor)
