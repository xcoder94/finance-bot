"""transaction_change_logs: structured payload (render in reader's language)

Revision ID: x4a5b6c7d8e9
Revises: w3f4a5b6c7d8
Create Date: 2026-11-01 12:00:00.000000

Expand-only. Adds format_version + payload, makes line_text nullable.
  format_version = 0 -> legacy row: line_text (Russian) is the only source, payload IS NULL.
  format_version = 1 -> payload (jsonb, v1 contract in work/db/m3-5-change-log.md) is the
                        source of truth; line_text is NULL for new rows, or keeps the original
                        Russian text for rows converted by the backfill below.
Backfill: a legacy row is converted only if it parses unambiguously AND the payload renders
back to exactly the same Russian text (round-trip) AND the day/month match the stored dates.
Anything else stays legacy and is served as is.
Downgrade is lossless for the text: rows without line_text get the Russian line the old code
would have written, then the new columns are dropped.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence, Union
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "x4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "w3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "transaction_change_logs"
CK_NAME = "ck_transaction_change_logs_format"
BATCH = 1000
TASHKENT = ZoneInfo("Asia/Tashkent")

# Frozen copy of the v1 Russian format (app/services/change_log_format.py as of m3-5).
MONTHS_RU = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
FIELD_RU = {
    "amount": "сумма",
    "category": "категория",
    "wallet": "кошелёк",
    "date": "дата",
    "comment": "комментарий",
    "from": "откуда",
    "to": "куда",
    "rate": "курс",
}
RU_FIELD = {v: k for k, v in FIELD_RU.items()}
ENTITY_FIELDS = ("category", "wallet", "from", "to")

CHECK_SQL = """
(format_version = 0 AND line_text IS NOT NULL AND payload IS NULL)
OR (
    format_version = 1
    AND payload IS NOT NULL
    AND jsonb_typeof(payload) = 'object'
    AND payload->>'kind' IN ('created', 'changed')
    AND (
        payload->>'kind' = 'created'
        OR payload->>'field' IN
           ('amount', 'category', 'wallet', 'date', 'comment', 'from', 'to', 'rate')
    )
)
"""


# ---------------------------------------------------------------- Russian render (v1)
def _day_month(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS_RU[d.month - 1]}"


def _amount_ru(value: int) -> str:
    negative = value < 0
    digits = str(abs(value))
    groups: list[str] = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    text = " ".join(groups)
    return f"-{text}" if negative else text


def _value_ru(field: str, value: Any) -> str:
    if value is None:
        return ""
    if field == "amount":
        return _amount_ru(int(value))
    if field == "date":
        return date.fromisoformat(value).strftime("%d.%m.%Y")
    if field in ENTITY_FIELDS:
        return value["name"]
    return str(value)  # comment, rate (already normalized decimal string)


def render_ru(payload: dict[str, Any]) -> str:
    head = _day_month(payload["on"])
    actor = payload["actor"]["name"]
    if payload["kind"] == "created":
        return f"{head} · создал {actor}"
    field = payload["field"]
    return (
        f"{head} · {actor}: {FIELD_RU[field]} "
        f"{_value_ru(field, payload['old'])} → {_value_ru(field, payload['new'])}"
    )


# ---------------------------------------------------------------- legacy parse
_MONTH_RE = "|".join(MONTHS_RU)
_HEAD_RE = re.compile(rf"^(\d{{1,2}}) ({_MONTH_RE}) · (.*)$", re.S)
_AMOUNT_RE = re.compile(r"^-?\d{1,3}( \d{3})*$")
_DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
_RATE_RE = re.compile(r"^\d+(\.\d+)?$")


def _parse_value(field: str, text: str) -> tuple[bool, Any]:
    if field == "amount":
        if not _AMOUNT_RE.match(text):
            return False, None
        return True, int(text.replace(" ", ""))
    if field == "date":
        m = _DATE_RE.match(text)
        if not m:
            return False, None
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return False, None
        return True, d.isoformat()
    if field == "rate":
        if text == "":
            return True, None
        if not _RATE_RE.match(text):
            return False, None
        try:
            Decimal(text)
        except InvalidOperation:
            return False, None
        return True, text
    if field == "comment":
        return True, (text or None)
    # entity: name snapshot only, id / translation key unknown for legacy rows
    return True, ({"id": None, "name": text, "tk": None} if text else None)


def _on_date(day: int, month_ru: str, at: datetime) -> str | None:
    local = at.astimezone(TASHKENT).date()
    if local.day != day or local.month != MONTHS_RU.index(month_ru) + 1:
        return None
    return local.isoformat()


def parse_legacy(line: str, row_created_at: datetime, tx_created_at: datetime) -> dict | None:
    if line.count(" · ") != 1:
        return None
    m = _HEAD_RE.match(line)
    if not m:
        return None
    day, month_ru, rest = int(m.group(1)), m.group(2), m.group(3)

    if rest.startswith("создал ") and ": " not in rest and " → " not in rest:
        on = _on_date(day, month_ru, tx_created_at)
        name = rest[len("создал "):]
        if on is None or not name:
            return None
        payload = {"kind": "created", "on": on, "actor": {"id": None, "name": name}}
    else:
        if rest.count(" → ") != 1:
            return None
        candidates = []
        for label, field in RU_FIELD.items():
            marker = f": {label} "
            idx = rest.find(marker)
            while idx != -1:
                candidates.append((idx, field, marker))
                idx = rest.find(marker, idx + 1)
        if len(candidates) != 1:
            return None
        idx, field, marker = candidates[0]
        actor = rest[:idx]
        old_text, new_text = rest[idx + len(marker):].split(" → ")
        ok_old, old = _parse_value(field, old_text)
        ok_new, new = _parse_value(field, new_text)
        on = _on_date(day, month_ru, row_created_at)
        if not (actor and ok_old and ok_new and on):
            return None
        payload = {
            "kind": "changed",
            "on": on,
            "actor": {"id": None, "name": actor},
            "field": field,
            "old": old,
            "new": new,
        }

    if render_ru(payload) != line:  # round-trip guard: convert only if exact
        return None
    return payload


# ---------------------------------------------------------------- migration
def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("format_version", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(TABLE, sa.Column("payload", postgresql.JSONB(), nullable=True))
    op.alter_column(TABLE, "line_text", existing_type=sa.Text(), nullable=True)
    op.execute(f"ALTER TABLE {TABLE} ADD CONSTRAINT {CK_NAME} CHECK ({CHECK_SQL}) NOT VALID")
    op.execute(f"ALTER TABLE {TABLE} VALIDATE CONSTRAINT {CK_NAME}")

    bind = op.get_bind()
    last_id = None
    while True:
        rows = bind.execute(
            sa.text(
                f"""
                SELECT l.id, l.line_text, l.created_at, t.created_at AS tx_created_at
                FROM {TABLE} l JOIN transactions t ON t.id = l.transaction_id
                WHERE l.format_version = 0
                  AND (CAST(:last_id AS uuid) IS NULL OR l.id > CAST(:last_id AS uuid))
                ORDER BY l.id
                LIMIT :lim
                """
            ),
            {"last_id": last_id, "lim": BATCH},
        ).all()
        if not rows:
            break
        updates = []
        for row in rows:
            payload = parse_legacy(row.line_text, row.created_at, row.tx_created_at)
            if payload is not None:
                updates.append({"id": row.id, "payload": json.dumps(payload, ensure_ascii=False)})
        if updates:
            bind.execute(
                sa.text(
                    f"UPDATE {TABLE} SET format_version = 1, payload = CAST(:payload AS jsonb) "
                    "WHERE id = :id"
                ),
                updates,
            )
        last_id = str(rows[-1].id)


def downgrade() -> None:
    bind = op.get_bind()
    while True:
        rows = bind.execute(
            sa.text(f"SELECT id, payload FROM {TABLE} WHERE line_text IS NULL LIMIT :lim"),
            {"lim": BATCH},
        ).all()
        if not rows:
            break
        bind.execute(
            sa.text(f"UPDATE {TABLE} SET line_text = :line WHERE id = :id"),
            [{"id": r.id, "line": render_ru(r.payload)} for r in rows],
        )
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {CK_NAME}")
    op.alter_column(TABLE, "line_text", existing_type=sa.Text(), nullable=False)
    op.drop_column(TABLE, "payload")
    op.drop_column(TABLE, "format_version")
