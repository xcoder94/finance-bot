from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.transaction_change_log import TransactionChangeLog
from app.models.user import User
from app.schemas.transactions import ExpenseUpdate, IncomeUpdate, TransferUpdate
from app.services.change_log_format import (
    FIELD_AMOUNT,
    FIELD_CATEGORY,
    FIELD_COMMENT,
    FIELD_DATE,
    FIELD_FROM,
    FIELD_RATE,
    FIELD_TO,
    FIELD_WALLET,
    change_line,
    creation_line,
    format_amount_text,
    format_rate_text,
    format_transaction_date_text,
)
from app.services.wallets_categories import (
    get_active_expense_category,
    get_active_income_category,
    get_active_wallet,
)

TASHKENT = ZoneInfo("Asia/Tashkent")


def _display_name(user: User) -> str:
    return user.first_name or user.username or "Unknown"


def _tashkent_today() -> date:
    return datetime.now(UTC).astimezone(TASHKENT).date()


def _tashkent_date(dt: datetime) -> date:
    return dt.astimezone(TASHKENT).date()


def _comment_text(comment: str | None) -> str:
    return comment or ""


async def list_change_lines(session: AsyncSession, transaction_id: uuid.UUID) -> list[str]:
    stmt = (
        select(TransactionChangeLog.line_text)
        .where(TransactionChangeLog.transaction_id == transaction_id)
        .order_by(TransactionChangeLog.created_at.asc(), TransactionChangeLog.id.asc())
    )
    return list(await session.scalars(stmt))


async def _has_log_rows(session: AsyncSession, transaction_id: uuid.UUID) -> bool:
    stmt = select(func.count()).select_from(TransactionChangeLog).where(
        TransactionChangeLog.transaction_id == transaction_id
    )
    return int(await session.scalar(stmt) or 0) > 0


async def _get_creator_name(session: AsyncSession, created_by_user_id: uuid.UUID) -> str:
    user = await session.get(User, created_by_user_id)
    if user is None:
        return "Unknown"
    return _display_name(user)


async def _append_lines(
    session: AsyncSession,
    transaction_id: uuid.UUID,
    lines: list[str],
) -> None:
    base = datetime.now(UTC)
    for index, line in enumerate(lines):
        session.add(
            TransactionChangeLog(
                transaction_id=transaction_id,
                line_text=line,
                created_at=base + timedelta(microseconds=index),
            )
        )


async def _record_changes(
    session: AsyncSession,
    transaction: Transaction,
    editor: User,
    field_changes: list[tuple[str, str, str]],
) -> None:
    if not field_changes:
        return

    edited_on = _tashkent_today()
    editor_name = _display_name(editor)
    change_lines = [
        change_line(
            edited_on=edited_on,
            editor_name=editor_name,
            field_label=label,
            old_value=old,
            new_value=new,
        )
        for label, old, new in field_changes
    ]

    lines_to_insert: list[str] = []
    if not await _has_log_rows(session, transaction.id):
        creator_name = await _get_creator_name(session, transaction.created_by_user_id)
        created_on = _tashkent_date(transaction.created_at)
        lines_to_insert.append(
            creation_line(created_on=created_on, creator_name=creator_name)
        )

    lines_to_insert.extend(change_lines)
    await _append_lines(session, transaction.id, lines_to_insert)


def _collect_changes(
    pairs: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    return [(label, old, new) for label, old, new in pairs if old != new]


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
                FIELD_AMOUNT,
                format_amount_text(transaction.amount),
                format_amount_text(body.amount),
            ),
            (
                FIELD_CATEGORY,
                old_category.name if old_category else "",
                new_category.name if new_category else "",
            ),
            (
                FIELD_WALLET,
                old_wallet.name if old_wallet else "",
                new_wallet.name if new_wallet else "",
            ),
            (
                FIELD_DATE,
                format_transaction_date_text(transaction.transaction_date),
                format_transaction_date_text(body.transaction_date),
            ),
            (
                FIELD_COMMENT,
                _comment_text(transaction.comment),
                _comment_text(body.comment),
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
                FIELD_AMOUNT,
                format_amount_text(transaction.amount),
                format_amount_text(body.amount),
            ),
            (
                FIELD_CATEGORY,
                old_category.name if old_category else "",
                new_category.name if new_category else "",
            ),
            (
                FIELD_WALLET,
                old_wallet.name if old_wallet else "",
                new_wallet.name if new_wallet else "",
            ),
            (
                FIELD_DATE,
                format_transaction_date_text(transaction.transaction_date),
                format_transaction_date_text(body.transaction_date),
            ),
            (
                FIELD_COMMENT,
                _comment_text(transaction.comment),
                _comment_text(body.comment),
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

    pairs: list[tuple[str, str, str]] = [
        (
            FIELD_AMOUNT,
            format_amount_text(transaction.amount),
            format_amount_text(body.amount),
        ),
        (
            FIELD_FROM,
            old_from.name if old_from else "",
            new_from.name if new_from else "",
        ),
        (
            FIELD_TO,
            old_to.name if old_to else "",
            new_to.name if new_to else "",
        ),
    ]

    if transaction.rate is not None or stored_rate is not None:
        old_rate = (
            format_rate_text(transaction.rate)
            if transaction.rate is not None
            else ""
        )
        new_rate = format_rate_text(stored_rate) if stored_rate is not None else ""
        pairs.append((FIELD_RATE, old_rate, new_rate))

    pairs.extend(
        [
            (
                FIELD_DATE,
                format_transaction_date_text(transaction.transaction_date),
                format_transaction_date_text(body.transaction_date),
            ),
            (
                FIELD_COMMENT,
                _comment_text(transaction.comment),
                _comment_text(body.comment),
            ),
        ]
    )

    await _record_changes(session, transaction, editor, _collect_changes(pairs))
