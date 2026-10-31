from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.transaction_change_log import TransactionChangeLog
from app.models.user import User
from app.schemas.transactions import ExpenseUpdate, IncomeUpdate, TransferUpdate
from app.services.change_log_format import (
    render_change_payload,
    format_rate_text,
)
from app.services.wallets_categories import (
    get_active_expense_category,
    get_active_income_category,
    get_active_wallet,
)

TASHKENT = ZoneInfo("Asia/Tashkent")

# (field, old, new) with typed payload values (see work/db/m3-5-change-log.md)
FieldChange = tuple[str, Any, Any]


def _display_name(user: User) -> str:
    return user.first_name or user.username or "Unknown"


def _tashkent_today() -> date:
    return datetime.now(UTC).astimezone(TASHKENT).date()


def _tashkent_date(dt: datetime) -> date:
    return dt.astimezone(TASHKENT).date()


def _comment_value(comment: str | None) -> str | None:
    return comment or None


def _date_value(dt: datetime) -> str:
    return _tashkent_date(dt).isoformat()


def _entity(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    return {
        "id": str(obj.id),
        "name": obj.name,
        "tk": getattr(obj, "translation_key", None),
    }


def _same(field: str, old: Any, new: Any) -> bool:
    if field in ("category", "wallet", "from", "to"):
        return (old["name"] if old else None) == (new["name"] if new else None)
    return old == new


async def list_change_lines(
    session: AsyncSession, transaction_id: uuid.UUID, language: str = "ru"
) -> list[str]:
    """Change lines for the reader: legacy text as is, payload rows in `language`."""
    stmt = (
        select(
            TransactionChangeLog.format_version,
            TransactionChangeLog.payload,
            TransactionChangeLog.line_text,
        )
        .where(TransactionChangeLog.transaction_id == transaction_id)
        .order_by(TransactionChangeLog.created_at.asc(), TransactionChangeLog.id.asc())
    )
    lines: list[str] = []
    for version, payload, text in (await session.execute(stmt)).all():
        if version == 1 and payload is not None:
            lines.append(render_change_payload(payload, language))
        else:
            lines.append(text or "")
    return lines


async def _has_log_rows(session: AsyncSession, transaction_id: uuid.UUID) -> bool:
    stmt = select(func.count()).select_from(TransactionChangeLog).where(
        TransactionChangeLog.transaction_id == transaction_id
    )
    return int(await session.scalar(stmt) or 0) > 0


async def _append_payloads(
    session: AsyncSession,
    transaction_id: uuid.UUID,
    payloads: list[dict[str, Any]],
) -> None:
    base = datetime.now(UTC)
    for index, payload in enumerate(payloads):
        session.add(
            TransactionChangeLog(
                transaction_id=transaction_id,
                format_version=1,
                payload=payload,
                line_text=None,
                created_at=base + timedelta(microseconds=index),
            )
        )


async def _record_changes(
    session: AsyncSession,
    transaction: Transaction,
    editor: User,
    field_changes: list[FieldChange],
) -> None:
    if not field_changes:
        return

    edited_on = _tashkent_today().isoformat()
    editor_actor = {"id": str(editor.id), "name": _display_name(editor)}
    payloads: list[dict[str, Any]] = []

    if not await _has_log_rows(session, transaction.id):
        creator = await session.get(User, transaction.created_by_user_id)
        payloads.append(
            {
                "kind": "created",
                "on": _tashkent_date(transaction.created_at).isoformat(),
                "actor": {
                    "id": str(creator.id) if creator else None,
                    "name": _display_name(creator) if creator else "Unknown",
                },
            }
        )

    for field, old, new in field_changes:
        payloads.append(
            {
                "kind": "changed",
                "on": edited_on,
                "actor": editor_actor,
                "field": field,
                "old": old,
                "new": new,
            }
        )
    await _append_payloads(session, transaction.id, payloads)


def _collect_changes(pairs: list[FieldChange]) -> list[FieldChange]:
    return [(f, old, new) for f, old, new in pairs if not _same(f, old, new)]


async def record_income_changes(
    session: AsyncSession,
    transaction: Transaction,
    body: IncomeUpdate,
    editor: User,
) -> None:
    old_wallet = await get_active_wallet(
        session, transaction.wallet_id, transaction.family_budget_id
    )
    new_wallet = await get_active_wallet(
        session, body.wallet_id, transaction.family_budget_id
    )
    old_category = await get_active_income_category(
        session, transaction.income_category_id, transaction.family_budget_id
    )
    new_category = await get_active_income_category(
        session, body.income_category_id, transaction.family_budget_id
    )

    field_changes = _collect_changes(
        [
            (
                "amount",
                transaction.amount,
                body.amount,
            ),
            (
                "category",
                _entity(old_category),
                _entity(new_category),
            ),
            (
                "wallet",
                _entity(old_wallet),
                _entity(new_wallet),
            ),
            (
                "date",
                _date_value(transaction.transaction_date),
                _date_value(body.transaction_date),
            ),
            (
                "comment",
                _comment_value(transaction.comment),
                _comment_value(body.comment),
            ),
        ]
    )
    await _record_changes(session, transaction, editor, field_changes)


async def record_expense_changes(
    session: AsyncSession,
    transaction: Transaction,
    body: ExpenseUpdate,
    editor: User,
) -> None:
    old_wallet = await get_active_wallet(
        session, transaction.wallet_id, transaction.family_budget_id
    )
    new_wallet = await get_active_wallet(
        session, body.wallet_id, transaction.family_budget_id
    )
    old_category = await get_active_expense_category(
        session, transaction.expense_category_id, transaction.family_budget_id
    )
    new_category = await get_active_expense_category(
        session, body.expense_category_id, transaction.family_budget_id
    )

    field_changes = _collect_changes(
        [
            (
                "amount",
                transaction.amount,
                body.amount,
            ),
            (
                "category",
                _entity(old_category),
                _entity(new_category),
            ),
            (
                "wallet",
                _entity(old_wallet),
                _entity(new_wallet),
            ),
            (
                "date",
                _date_value(transaction.transaction_date),
                _date_value(body.transaction_date),
            ),
            (
                "comment",
                _comment_value(transaction.comment),
                _comment_value(body.comment),
            ),
        ]
    )
    await _record_changes(session, transaction, editor, field_changes)


async def record_transfer_changes(
    session: AsyncSession,
    transaction: Transaction,
    body: TransferUpdate,
    editor: User,
    *,
    stored_rate: Decimal | None,
) -> None:
    old_from = await get_active_wallet(
        session, transaction.wallet_id, transaction.family_budget_id
    )
    new_from = await get_active_wallet(
        session, body.wallet_id, transaction.family_budget_id
    )
    old_to = None
    if transaction.to_wallet_id is not None:
        old_to = await get_active_wallet(
            session, transaction.to_wallet_id, transaction.family_budget_id
        )
    new_to = await get_active_wallet(
        session, body.to_wallet_id, transaction.family_budget_id
    )

    pairs: list[FieldChange] = [
        (
            "amount",
            transaction.amount,
            body.amount,
        ),
        (
            "from",
            _entity(old_from),
            _entity(new_from),
        ),
        (
            "to",
            _entity(old_to),
            _entity(new_to),
        ),
    ]

    if transaction.rate is not None or stored_rate is not None:
        old_rate = (
            format_rate_text(transaction.rate)
            if transaction.rate is not None
            else None
        )
        new_rate = format_rate_text(stored_rate) if stored_rate is not None else None
        pairs.append(("rate", old_rate, new_rate))

    pairs.extend(
        [
            (
                "date",
                _date_value(transaction.transaction_date),
                _date_value(body.transaction_date),
            ),
            (
                "comment",
                _comment_value(transaction.comment),
                _comment_value(body.comment),
            ),
        ]
    )

    await _record_changes(session, transaction, editor, _collect_changes(pairs))
