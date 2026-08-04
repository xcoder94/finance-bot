import secrets
import uuid
from typing import Literal

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.budget_seed import (
    assign_default_card_uzs,
    copy_seed_categories_only,
    copy_seed_wallets_only,
)
from app.services.goal_notify import resolve_bot
from app.services.member_texts import left_notice, removed_notice


class OwnerCannotDetachError(Exception):
    pass


async def count_active_members(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> int:
    stmt = (
        select(func.count())
        .select_from(User)
        .where(
            User.family_budget_id == family_budget_id,
            User.is_deleted.is_(False),
        )
    )
    return int(await session.scalar(stmt) or 0)


async def count_all_wallets_for_user_budget(
    session: AsyncSession, user: User
) -> int:
    stmt = (
        select(func.count())
        .select_from(Wallet)
        .where(
            Wallet.family_budget_id == user.family_budget_id,
            Wallet.is_deleted.is_(False),
        )
    )
    return int(await session.scalar(stmt) or 0)


async def detach_member_to_own_budget(
    session: AsyncSession,
    *,
    departing_user: User,
    old_budget: FamilyBudget,
    reason: Literal["removed", "left"],
    bot: Bot | None = None,
) -> FamilyBudget:
    if departing_user.role == "owner":
        raise OwnerCannotDetachError()

    old_budget_name = old_budget.name

    new_budget = FamilyBudget(invite_token=secrets.token_urlsafe(16))
    session.add(new_budget)
    await session.flush()

    personal_wallets_stmt = (
        select(Wallet)
        .where(
            Wallet.family_budget_id == old_budget.id,
            Wallet.is_personal.is_(True),
            Wallet.owner_user_id == departing_user.id,
            Wallet.is_deleted.is_(False),
        )
        .order_by(Wallet.created_at)
    )
    personal_wallets = (await session.scalars(personal_wallets_stmt)).all()

    for wallet in personal_wallets:
        wallet.family_budget_id = new_budget.id

    if personal_wallets:
        personal_wallet_ids = [wallet.id for wallet in personal_wallets]
        personal_txns = (
            await session.scalars(
                select(Transaction).where(
                    Transaction.wallet_id.in_(personal_wallet_ids),
                    Transaction.is_deleted.is_(False),
                )
            )
        ).all()
        for txn in personal_txns:
            txn.family_budget_id = new_budget.id

    departing_user.family_budget_id = new_budget.id
    departing_user.role = "owner"

    await copy_seed_categories_only(session, new_budget.id)

    if len(personal_wallets) == 0:
        await copy_seed_wallets_only(session, new_budget.id)
        await assign_default_card_uzs(session, departing_user)
    else:
        departing_user.default_wallet_id = personal_wallets[0].id

    resolved_bot, owned = await resolve_bot(bot)
    try:
        if reason == "removed":
            text = removed_notice(old_budget_name)
        else:
            text = left_notice(old_budget_name)
        await resolved_bot.send_message(departing_user.telegram_id, text)
    finally:
        if owned:
            await resolved_bot.session.close()

    return new_budget
