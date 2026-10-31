import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Totals(_Strict):
    users: int
    families: int
    families_multi: int


class Windows(_Strict):
    today: int
    d7: int
    d30: int


class ActiveUsers(_Strict):
    dau: int
    wau: int
    mau: int


class Retention(_Strict):
    returned: int  # n
    cohort: int  # N
    percent: float | None  # None when cohort == 0


class RetentionBlock(_Strict):
    d7: Retention
    d30: Retention


class DailyActive(_Strict):
    day: date
    users: int


class AdminOverview(_Strict):
    totals: Totals
    new_users: Windows
    new_families: Windows
    active: ActiveUsers
    retention: RetentionBlock
    daily_active: list[DailyActive]  # last 30 Tashkent days, oldest first, today last
    activity_since: date | None  # first day with any activity record


class AdminUserRow(_Strict):
    id: uuid.UUID
    first_name: str | None
    username: str | None
    phone: str | None
    language: str
    registered_at: str  # ISO 8601, Asia/Tashkent offset
    last_seen_at: str | None  # ISO 8601, Asia/Tashkent offset
    family_members: int
    family_role: str  # owner | member
    operations_count: int


class AdminUsersPage(_Strict):
    items: list[AdminUserRow]
    total: int
    next_cursor: str | None
