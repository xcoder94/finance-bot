from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import is_admin_telegram_id
from app.auth.deps import AppPassClaimsDep
from app.auth.user_deps import CurrentUserDep, WriteUserDep
from app.config import receipt_photo_enabled
from app.db import async_session_factory, get_session
from app.models.family_budget import FamilyBudget
from app.models.user import User
from app.models.transaction import Transaction
from app.schemas.auth import MeResponse, MeUpdate, OnboardingResponse, OnboardingSteps
from app.services.activity import touch_activity
from app.services.wallet_visibility import require_wallet_visible
from app.services.wallets_categories import get_active_wallet

router = APIRouter(prefix="/api/v1")


async def _build_me_response(session: AsyncSession, db_user: User) -> MeResponse:
    budget = await session.scalar(
        select(FamilyBudget).where(FamilyBudget.id == db_user.family_budget_id)
    )
    member_count = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.family_budget_id == db_user.family_budget_id,
            User.is_deleted.is_(False),
        )
    )
    return MeResponse(
        id=db_user.id,
        telegram_id=db_user.telegram_id,
        family_budget_id=db_user.family_budget_id,
        role=db_user.role,
        first_name=db_user.first_name,
        username=db_user.username,
        language=db_user.language,
        budget_name=budget.name if budget is not None else "",
        member_count=member_count or 0,
        default_wallet_id=db_user.default_wallet_id,
        evening_reminder_enabled=db_user.evening_reminder_enabled,
        weekly_digest_enabled=db_user.weekly_digest_enabled,
        receipt_photo_enabled=receipt_photo_enabled(),
        is_admin=is_admin_telegram_id(db_user.telegram_id),
    )


@router.get("/me")
async def get_me(
    claims: AppPassClaimsDep, background_tasks: BackgroundTasks
) -> MeResponse:
    telegram_id = int(claims["sub"])
    async with async_session_factory() as session:
        db_user = await session.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )

        if db_user is None:
            raise HTTPException(status_code=404, detail="not_onboarded")

        if db_user.is_deleted:
            raise HTTPException(status_code=403, detail="removed_from_family")

        background_tasks.add_task(
            touch_activity, telegram_id=telegram_id, user_id=db_user.id, app=True
        )
        return await _build_me_response(session, db_user)


@router.patch("/me")
async def patch_me(
    body: MeUpdate,
    user: WriteUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    if "default_wallet_id" in body.model_fields_set:
        if body.default_wallet_id is not None:
            wallet = await get_active_wallet(
                session, body.default_wallet_id, user.family_budget_id
            )
            require_wallet_visible(wallet, user)
            user.default_wallet_id = body.default_wallet_id
        else:
            user.default_wallet_id = None

    if "language" in body.model_fields_set and body.language is not None:
        user.language = body.language

    if "evening_reminder_enabled" in body.model_fields_set:
        if body.evening_reminder_enabled is not None:
            user.evening_reminder_enabled = body.evening_reminder_enabled

    if "weekly_digest_enabled" in body.model_fields_set:
        if body.weekly_digest_enabled is not None:
            user.weekly_digest_enabled = body.weekly_digest_enabled

    await session.commit()
    await session.refresh(user)
    return await _build_me_response(session, user)


async def _build_onboarding(session: AsyncSession, user: User) -> OnboardingResponse:
    budget_id = user.family_budget_id
    has_operation = await session.scalar(
        select(
            select(Transaction.id)
            .where(
                Transaction.family_budget_id == budget_id,
                Transaction.is_deleted.is_(False),
                Transaction.is_demo.is_(False),
            )
            .limit(1)
            .exists()
        )
    )
    member_count = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.family_budget_id == budget_id, User.is_deleted.is_(False))
    )
    # Step 2 ("add this month's income") is done once the budget has any income.
    has_income = await session.scalar(
        select(
            select(Transaction.id)
            .where(
                Transaction.family_budget_id == budget_id,
                Transaction.type == "income",
                Transaction.is_deleted.is_(False),
                Transaction.is_demo.is_(False),
            )
            .limit(1)
            .exists()
        )
    )
    link_opened_at = await session.scalar(
        select(FamilyBudget.invite_link_opened_at).where(FamilyBudget.id == budget_id)
    )
    steps = OnboardingSteps(
        first_operation=bool(has_operation),
        default_wallet_checked=bool(has_income),
        family_invited=(member_count or 0) > 1 or link_opened_at is not None,
    )
    show = user.role == "owner" and not all(
        (steps.first_operation, steps.default_wallet_checked, steps.family_invited)
    )
    return OnboardingResponse(show=show, steps=steps)


@router.get("/me/onboarding")
async def get_onboarding(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingResponse:
    return await _build_onboarding(session, user)


@router.post("/me/onboarding/default-wallet-checked")
async def mark_default_wallet_checked(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingResponse:
    if user.default_wallet_screen_opened_at is None:
        user.default_wallet_screen_opened_at = datetime.now(UTC)
        await session.commit()
    return await _build_onboarding(session, user)
