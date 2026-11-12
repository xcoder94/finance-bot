import uuid

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_budget import FamilyBudget
from app.models.ownership_transfer import OwnershipTransfer
from app.models.user import User
from app.services.goal_notify import queue_notice
from app.services.bot_texts import t
from app.services.member_texts import (
    transfer_accepted_to_former,
    transfer_accepted_to_others,
    transfer_offer,
    transfer_refused_to_former,
)


class InvalidTransferTargetError(Exception):
    pass


class TransferConflictError(Exception):
    """A concurrent request already created the pending offer for this family."""


class TransferNotFoundError(Exception):
    pass


class TransferNotPendingError(Exception):
    pass


class TransferActorError(Exception):
    pass


class TransferStaleError(Exception):
    def __init__(self, message: str = "Предложение больше не действует.") -> None:
        self.message = message
        super().__init__(message)


def display_name(user: User) -> str:
    return user.first_name or user.username or "Участник"


def transfer_offer_keyboard(
    transfer_id: uuid.UUID, language: str = "ru"
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(language, "button.transfer_accept"),
                    callback_data=f"own_xfer_accept:{transfer_id}",
                ),
                InlineKeyboardButton(
                    text=t(language, "button.transfer_refuse"),
                    callback_data=f"own_xfer_refuse:{transfer_id}",
                ),
            ]
        ]
    )


async def _cancel_pending_for_family(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> None:
    pending = (
        await session.scalars(
            select(OwnershipTransfer).where(
                OwnershipTransfer.family_budget_id == family_budget_id,
                OwnershipTransfer.status == "pending",
            )
        )
    ).all()
    for row in pending:
        row.status = "cancelled"


async def cancel_pending_transfers_for_user(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    pending = (
        await session.scalars(
            select(OwnershipTransfer).where(
                OwnershipTransfer.status == "pending",
                (
                    (OwnershipTransfer.to_user_id == user_id)
                    | (OwnershipTransfer.from_user_id == user_id)
                ),
            )
        )
    ).all()
    for row in pending:
        row.status = "cancelled"


async def _get_transfer(
    session: AsyncSession, transfer_id: uuid.UUID
) -> OwnershipTransfer | None:
    return await session.get(OwnershipTransfer, transfer_id)


async def _get_pending_transfer(
    session: AsyncSession, transfer_id: uuid.UUID
) -> OwnershipTransfer | None:
    transfer = await _get_transfer(session, transfer_id)
    if transfer is None or transfer.status != "pending":
        return None
    return transfer


def _transfer_participants_stale(
    transfer: OwnershipTransfer,
    former_owner: User | None,
    new_owner: User | None,
    budget: FamilyBudget | None,
) -> bool:
    if (
        former_owner is None
        or new_owner is None
        or budget is None
        or budget.is_deleted
        or former_owner.is_deleted
        or new_owner.is_deleted
    ):
        return True
    if former_owner.family_budget_id != transfer.family_budget_id:
        return True
    if new_owner.family_budget_id != transfer.family_budget_id:
        return True
    if former_owner.role != "owner":
        return True
    if new_owner.role != "member":
        return True
    return False


async def _lock_users(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, User]:
    """Row-lock users in sorted id order and return their CURRENT state (not the cached one)."""
    rows = (
        await session.scalars(
            select(User)
            .where(User.id.in_(user_ids))
            .order_by(User.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()
    return {row.id: row for row in rows}


async def request_ownership_transfer(
    session: AsyncSession,
    *,
    owner: User,
    recipient: User,
    budget: FamilyBudget,
    bot: Bot | None = None,
) -> OwnershipTransfer:
    if owner.role != "owner":
        raise InvalidTransferTargetError()
    if recipient.id == owner.id:
        raise InvalidTransferTargetError()
    if recipient.role != "member":
        raise InvalidTransferTargetError()
    if recipient.family_budget_id != owner.family_budget_id:
        raise InvalidTransferTargetError()
    if recipient.is_deleted:
        raise InvalidTransferTargetError()

    await _cancel_pending_for_family(session, owner.family_budget_id)

    transfer = OwnershipTransfer(
        family_budget_id=owner.family_budget_id,
        from_user_id=owner.id,
        to_user_id=recipient.id,
        status="pending",
    )
    session.add(transfer)
    try:
        await session.flush()
    except IntegrityError as exc:  # parallel duplicate: the one-pending-per-family index
        await session.rollback()  # also drops the queued notices of this request
        raise TransferConflictError() from exc

    queue_notice(
        session,
        bot,
        recipient.telegram_id,
        transfer_offer(budget.name, recipient),
        reply_markup=transfer_offer_keyboard(transfer.id, recipient.language),
    )

    return transfer


async def accept_ownership_transfer(
    session: AsyncSession,
    *,
    transfer_id: uuid.UUID,
    actor: User,
    bot: Bot | None = None,
) -> None:
    transfer = await _get_transfer(session, transfer_id)
    if transfer is None:
        raise TransferNotFoundError()
    if transfer.status != "pending":
        raise TransferNotPendingError()
    if actor.id != transfer.to_user_id:
        raise TransferActorError()

    # Lock both people (sorted ids), then the offer, and only then look at them: a parallel
    # leave / remove / delete of either person either finishes before we look (-> stale) or
    # waits for us. Same order as detach (user first, then the offer) - no deadlock.
    locked = await _lock_users(session, [transfer.from_user_id, transfer.to_user_id])
    await session.refresh(transfer, with_for_update=True)
    if transfer.status != "pending":
        raise TransferNotPendingError()
    former_owner = locked.get(transfer.from_user_id)
    new_owner = locked.get(transfer.to_user_id)
    budget = await session.get(
        FamilyBudget, transfer.family_budget_id, populate_existing=True
    )

    if _transfer_participants_stale(transfer, former_owner, new_owner, budget):
        transfer.status = "cancelled"
        raise TransferStaleError()

    assert former_owner is not None
    assert new_owner is not None
    assert budget is not None

    former_owner.role = "member"
    new_owner.role = "owner"
    transfer.status = "accepted"

    new_owner_name = display_name(new_owner)
    budget_name = budget.name

    remaining = (
        await session.scalars(
            select(User).where(
                User.family_budget_id == transfer.family_budget_id,
                User.is_deleted.is_(False),
                User.id.not_in([former_owner.id, new_owner.id]),
            )
        )
    ).all()

    queue_notice(
        session,
        bot,
        former_owner.telegram_id,
        transfer_accepted_to_former(new_owner_name, budget_name, former_owner),
    )
    for member in remaining:
        queue_notice(
            session,
            bot,
            member.telegram_id,
            transfer_accepted_to_others(new_owner_name, budget_name, member),
        )


async def refuse_ownership_transfer(
    session: AsyncSession,
    *,
    transfer_id: uuid.UUID,
    actor: User,
    bot: Bot | None = None,
) -> None:
    transfer = await _get_transfer(session, transfer_id)
    if transfer is not None:
        # lock the offer so a parallel accept/refuse is decided once (no lost update)
        await session.refresh(transfer, with_for_update=True)
        if transfer.status != "pending":
            transfer = None
    if transfer is None:
        raise TransferNotFoundError()
    if transfer.status != "pending":
        raise TransferNotPendingError()
    if actor.id != transfer.to_user_id:
        raise TransferActorError()

    former_owner = await session.get(User, transfer.from_user_id)
    recipient = await session.get(User, transfer.to_user_id)
    if (
        former_owner is None
        or recipient is None
        or former_owner.is_deleted
        or recipient.is_deleted
    ):
        raise TransferNotFoundError()

    transfer.status = "refused"
    recipient_name = display_name(recipient)

    queue_notice(
        session,
        bot,
        former_owner.telegram_id,
        transfer_refused_to_former(recipient_name, former_owner),
    )
