import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.db import async_session_factory
from app.services.member_texts import (
    invite_already_member,
    invite_family_full_chat,
    invite_link_invalid,
    join_has_other_members,
    join_personal_wallet_cap,
    welcome_invited,
)
from app.services.membership_lifecycle import (
    FamilyFullError,
    JoinBlockReason,
    convert_join_with_own_budget,
    count_active_members,
    count_all_wallets_for_user_budget,
    evaluate_join_from_own_budget,
)
from app.services.entity_limits import MEMBER_LIMIT
from app.services.ownership_transfer import (
    TransferActorError,
    TransferNotFoundError,
    TransferNotPendingError,
    TransferStaleError,
    accept_ownership_transfer,
    refuse_ownership_transfer,
)
from bot.onboarding import (
    get_active_user_by_telegram_id,
    get_family_budget_by_invite_token,
    open_app_keyboard,
)

router = Router()


async def _refusal_for_join_block(
    session, user, block: JoinBlockReason
) -> str:
    if block == JoinBlockReason.HAS_OTHER_MEMBERS:
        return join_has_other_members()
    wallet_count = await count_all_wallets_for_user_budget(session, user)
    return join_personal_wallet_cap(wallet_count)


@router.callback_query(F.data.startswith("join_accept:"))
async def join_accept(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    token = callback.data.split(":", 1)[1] if callback.data else ""
    if not token:
        await callback.answer()
        return

    budget_name = ""

    async with async_session_factory() as session:
        async with session.begin():
            user = await get_active_user_by_telegram_id(
                session, callback.from_user.id
            )
            if user is None:
                await callback.answer()
                return

            budget = await get_family_budget_by_invite_token(session, token)
            if budget is None:
                await callback.message.edit_text(invite_link_invalid())
                await callback.answer()
                return

            budget_name = budget.name

            if user.family_budget_id == budget.id:
                await callback.message.edit_text(invite_already_member(budget.name))
                await callback.answer()
                return

            if await count_active_members(session, budget.id) >= MEMBER_LIMIT:
                await callback.message.edit_text(invite_family_full_chat())
                await callback.answer()
                return

            block = await evaluate_join_from_own_budget(session, user, budget)
            if block is not None:
                await callback.message.edit_text(
                    await _refusal_for_join_block(session, user, block)
                )
                await callback.answer()
                return

            try:
                await convert_join_with_own_budget(
                    session, user=user, target=budget
                )
            except FamilyFullError:
                await callback.message.edit_text(invite_family_full_chat())
                await callback.answer()
                return

    await callback.message.answer(
        welcome_invited(budget_name),
        reply_markup=open_app_keyboard(user.language),
        parse_mode="Markdown",
    )
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "join_cancel")
async def join_cancel(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.startswith("own_xfer_accept:"))
async def own_xfer_accept(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    raw_id = callback.data.split(":", 1)[1] if callback.data else ""
    try:
        transfer_id = uuid.UUID(raw_id)
    except ValueError:
        await callback.answer()
        return

    async with async_session_factory() as session:
        async with session.begin():
            user = await get_active_user_by_telegram_id(
                session, callback.from_user.id
            )
            if user is None:
                await callback.answer()
                return

            try:
                await accept_ownership_transfer(
                    session,
                    transfer_id=transfer_id,
                    actor=user,
                    bot=None,
                )
            except TransferStaleError as exc:
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.answer(exc.message)
                return
            except (TransferNotFoundError, TransferNotPendingError, TransferActorError):
                await callback.answer()
                return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.startswith("own_xfer_refuse:"))
async def own_xfer_refuse(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    raw_id = callback.data.split(":", 1)[1] if callback.data else ""
    try:
        transfer_id = uuid.UUID(raw_id)
    except ValueError:
        await callback.answer()
        return

    async with async_session_factory() as session:
        async with session.begin():
            user = await get_active_user_by_telegram_id(
                session, callback.from_user.id
            )
            if user is None:
                await callback.answer()
                return

            try:
                await refuse_ownership_transfer(
                    session,
                    transfer_id=transfer_id,
                    actor=user,
                    bot=None,
                )
            except (TransferNotFoundError, TransferNotPendingError, TransferActorError):
                await callback.answer()
                return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
