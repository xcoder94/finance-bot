import uuid
from datetime import date
from typing import Literal

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


class OperationsByChannel(_Strict):
    text: int  # bot: text message
    voice: int  # bot: voice message
    photo: int  # bot: receipt photo
    app: int  # mini-app forms and manual purchase sum
    unknown: int  # created before channel tracking (channel IS NULL)
    total: int


class AiUsage(_Strict):
    calls: int  # requests to the model, every retry included
    error_calls: int  # of them: no answer / unusable answer
    calls_without_usage: int  # answered but carried no token counts -> cost is a lower bound
    cost_incomplete: bool  # calls_without_usage > 0: show the sum with "≈"
    input_tokens: int
    output_tokens: int
    cost_usd: float
    messages: int  # bot messages that went to parsing (N)
    unparsed: int  # of them: nothing usable found (n)
    errors: int  # of them: no model answer after all attempts / unusable answer
    threshold_usd: float | None  # None: no alert threshold configured
    cost_today_usd: float  # Tashkent today, regardless of the period


class AdminUsage(_Strict):
    period: Literal["day", "week", "month"]
    operations: OperationsByChannel
    ai: AiUsage
