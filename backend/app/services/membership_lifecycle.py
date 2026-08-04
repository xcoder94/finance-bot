import secrets
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from aiogram import Bot
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_budget import FamilyBudget
from app.models.goal import Goal
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.budget_seed import (
    assign_default_card_uzs,
    copy_seed_categories_only,
    copy_seed_wallets_only,
)
from app.services.entity_limits import MEMBER_LIMIT, PERSONAL_WALLET_LIMIT
from app.services.goal_notify import resolve_bot
from app.services.member_texts import left_notice, removed_notice
from app.services.ownership_transfer import cancel_pending_transfers_for_user
from app.services.transaction_category_remap import remap_transaction_categories_to_budget


class OwnerCannotDetachError(Exception):
    pass


class JoinBlockReason(str, Enum):
    HAS_OTHER_MEMBERS = "has_other_members"
    PERSONAL_WALLET_CAP = "personal_wallet_cap"


class FamilyFullError(Exception):
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


async def evaluate_join_from_own_budget(
    session: AsyncSession,
    user: User,
    target_budget: FamilyBudget,
) -> JoinBlockReason | None:
    del target_budget
    if await count_active_members(session, user.family_budget_id) > 1:
        return JoinBlockReason.HAS_OTHER_MEMBERS
    if await count_all_wallets_for_user_budget(session, user) > PERSONAL_WALLET_LIMIT:
        return JoinBlockReason.PERSONAL_WALLET_CAP
    return None


async def convert_join_with_own_budget(
    session: AsyncSession,
    *,
    user: User,
    target: FamilyBudget,
) -> None:
    if await count_active_members(session, target.id) >= MEMBER_LIMIT:
        raise FamilyFullError()

    old_budget_id = user.family_budget_id
    old_budget = await session.get(FamilyBudget, old_budget_id)
    if old_budget is None or old_budget.is_deleted:
        raise ValueError("user has no active budget to convert")

    wallets = (
        await session.scalars(
            select(Wallet)
            .where(
                Wallet.family_budget_id == old_budget_id,
                Wallet.is_deleted.is_(False),
            )
            .order_by(Wallet.created_at)
        )
    ).all()
    wallet_ids = [wallet.id for wallet in wallets]

    if wallet_ids:
        await session.execute(delete(Goal).where(Goal.wallet_id.in_(wallet_ids)))

    for wallet in wallets:
        wallet.family_budget_id = target.id
        wallet.is_personal = True
        wallet.owner_user_id = user.id

    if wallet_ids:
        moved_txns = (
            await session.scalars(
                select(Transaction).where(
                    Transaction.wallet_id.in_(wallet_ids),
                    Transaction.is_deleted.is_(False),
                )
            )
        ).all()
        for txn in moved_txns:
            txn.family_budget_id = target.id
        await remap_transaction_categories_to_budget(session, moved_txns, target.id)

    old_budget.is_deleted = True
    old_budget.deleted_at = datetime.now(UTC)

    user.family_budget_id = target.id
    user.role = "member"


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

    await cancel_pending_transfers_for_user(session, departing_user.id)

    old_budget_name = old_budget.name

    new_budget = FamilyBudget(invite_token=secrets.token_urlsafe(16))
    session.add(new_budget)
    await session.flush()

    await copy_seed_categories_only(session, new_budget.id)

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

    personal_txns: list[Transaction] = []
    if personal_wallets:
        personal_wallet_ids = [wallet.id for wallet in personal_wallets]
        personal_txns = list(
            await session.scalars(
                select(Transaction).where(
                    Transaction.wallet_id.in_(personal_wallet_ids),
                    Transaction.is_deleted.is_(False),
                )
            )
        )
        for txn in personal_txns:
            txn.family_budget_id = new_budget.id
        await remap_transaction_categories_to_budget(
            session, personal_txns, new_budget.id
        )

    departing_user.family_budget_id = new_budget.id
    departing_user.role = "owner"

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


async def reassign_defaults_after_shared_wallet_deleted(
    session: AsyncSession,
    *,
    family_budget_id: uuid.UUID,
    deleted_wallet_id: uuid.UUID,
) -> None:
    oldest_shared = await session.scalar(
        select(Wallet)
        .where(
            Wallet.family_budget_id == family_budget_id,
            Wallet.is_deleted.is_(False),
            Wallet.is_personal.is_(False),
        )
        .order_by(Wallet.created_at)
        .limit(1)
    )
    if oldest_shared is None:
        return

    users = (
        await session.scalars(
            select(User).where(
                User.family_budget_id == family_budget_id,
                User.is_deleted.is_(False),
                User.default_wallet_id == deleted_wallet_id,
            )
        )
    ).all()
    for user in users:
        user.default_wallet_id = oldest_shared.id
