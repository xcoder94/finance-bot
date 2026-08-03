from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo("Asia/Tashkent")
MAX_LOOKBACK_DAYS = 31
COMMENT_MAX_LEN = 200

_WEEKDAY_FORMS: dict[str, int] = {
    "понедельник": 0,
    "вторник": 1,
    "среда": 2,
    "среду": 2,
    "четверг": 3,
    "пятница": 4,
    "пятницу": 4,
    "пятницы": 4,
    "суббота": 5,
    "субботу": 5,
    "субботы": 5,
    "воскресенье": 6,
    "воскресенья": 6,
}

_DAYS_AGO_RE = re.compile(r"(\d+)\s+дн(?:я|ей)\s+назад", re.IGNORECASE)
_WEEKDAY_RE = re.compile(
    r"(?:в\s+)?(?:прошл(?:ый|ую|ое|ая)\s+)?"
    r"(понедельник|вторник|сред[уа]|четверг|пятниц[ауы]|суббот[ауы]|воскресень[ея])",
    re.IGNORECASE,
)
_PROSHL_RE = re.compile(r"прошл(?:ый|ую|ое|ая)", re.IGNORECASE)
_DATE_MARKER_RES = [
    re.compile(r"позавчера", re.IGNORECASE),
    re.compile(r"вчера", re.IGNORECASE),
    _DAYS_AGO_RE,
    _WEEKDAY_RE,
]


def tashkent_today() -> date:
    return datetime.now(TASHKENT).date()


def _reference_today(now: datetime | None) -> date:
    if now is None:
        return tashkent_today()
    if now.tzinfo is None:
        return now.date()
    return now.astimezone(TASHKENT).date()


def _finalize_date(resolved: date, today: date) -> date:
    if resolved > today:
        return today
    if (today - resolved).days > MAX_LOOKBACK_DAYS:
        return today
    return resolved


def _weekday_to_index(word: str) -> int:
    return _WEEKDAY_FORMS[word.casefold()]


def _resolve_weekday(match: re.Match[str], today: date) -> date:
    word = match.group(1)
    target = _weekday_to_index(word)
    days_back = (today.weekday() - target) % 7
    if days_back == 0:
        days_back = 7
    if _PROSHL_RE.search(match.group(0)):
        days_back += 7
    return today - timedelta(days=days_back)


def resolve_operation_date(text: str, now: datetime | None = None) -> date:
    today = _reference_today(now)

    if re.search(r"позавчера", text, re.IGNORECASE):
        return _finalize_date(today - timedelta(days=2), today)

    if re.search(r"вчера", text, re.IGNORECASE):
        return _finalize_date(today - timedelta(days=1), today)

    days_ago_match = _DAYS_AGO_RE.search(text)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        return _finalize_date(today - timedelta(days=days), today)

    weekday_match = _WEEKDAY_RE.search(text)
    if weekday_match:
        return _finalize_date(_resolve_weekday(weekday_match, today), today)

    return today


def _date_markers_in_text(text: str) -> list[str]:
    markers: list[str] = []
    for pattern in _DATE_MARKER_RES:
        for match in pattern.finditer(text):
            markers.append(match.group(0))
    return markers


def strip_date_words(comment: str | None, original_text: str) -> str | None:
    if comment is None:
        return None

    cleaned = comment
    for marker in _date_markers_in_text(original_text):
        cleaned = re.sub(re.escape(marker), "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    if len(cleaned) > COMMENT_MAX_LEN:
        return cleaned[:COMMENT_MAX_LEN]
    return cleaned
