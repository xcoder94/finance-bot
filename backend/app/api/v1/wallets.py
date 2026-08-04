import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import CurrentUserDep
from app.db import get_session
from app.models.goal import Goal
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.schemas.wallets_categories import (
    WalletCreate,
    WalletDeleteResponse,
    WalletResponse,
    WalletUpdate,
)
from app.services.entity_limits import (
    LIMIT_PERSONAL_WALLETS,
    LIMIT_SHARED_WALLETS,
    PERSONAL_WALLET_LIMIT,
    SHARED_WALLET_LIMIT,
)
from app.services.goals import get_active_goal_for_wallet
from app.services.wallet_visibility import require_wallet_visible, visible_wallets_clause
from app.services.wallets_categories import (
    count_wallet_transactions,
    get_active_wallet,
    soft_delete,
)

router = APIRouter(prefix="/api/v1")


@router.get("/wallets")
async def list_wallets(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[WalletResponse]:
    wallet_references = union_all(
        select(Transaction.wallet_id.label("wallet_id")).where(
            Transaction.family_budget_id == user.family_budget_id,
            Transaction.is_deleted.is_(False),
        ),
        select(Transaction.to_wallet_id.label("wallet_id")).where(
            Transaction.family_budget_id == user.family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.to_wallet_id.is_not(None),
        ),
    ).subquery()
    transaction_counts = (
        select(
            wallet_references.c.wallet_id,
            func.count().label("transaction_count"),
        )
        .group_by(wallet_references.c.wallet_id)
        .subquery()
    )
    stmt = (
        select(
            Wallet,
            func.coalesce(transaction_counts.c.transaction_count, 0).label(
                "transaction_count"
            ),
            exists(
                select(1).where(
                    Goal.wallet_id == Wallet.id,
                    Goal.status == "active",
                )
            ).label("has_active_goal"),
        )
        .outerjoin(transaction_counts, transaction_counts.c.wallet_id == Wallet.id)
        .where(
            Wallet.family_budget_id == user.family_budget_id,
            Wallet.is_deleted.is_(False),
            visible_wallets_clause(user),
        )
        .order_by(Wallet.created_at)
    )
    rows = (await session.execute(stmt)).all()
    return [
        WalletResponse(
            id=wallet.id,
            name=wallet.name,
            currency=wallet.currency,
            translation_key=wallet.translation_key,
            is_personal=wallet.is_personal,
            transaction_count=int(transaction_count),
            has_active_goal=bool(has_active_goal),
        )
        for wallet, transaction_count, has_active_goal in rows
    ]


@router.post("/wallets", status_code=201)
async def create_wallet(
    body: WalletCreate,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WalletResponse:
    if body.is_personal:
        personal_count = await session.scalar(
            select(func.count())
            .select_from(Wallet)
            .where(
                Wallet.family_budget_id == user.family_budget_id,
                Wallet.is_deleted.is_(False),
                Wallet.is_personal.is_(True),
                Wallet.owner_user_id == user.id,
            )
        )
        if personal_count is not None and personal_count >= PERSONAL_WALLET_LIMIT:
            raise HTTPException(status_code=409, detail=LIMIT_PERSONAL_WALLETS)

        wallet = Wallet(
            family_budget_id=user.family_budget_id,
            name=body.name,
            currency=body.currency,
            is_personal=True,
            owner_user_id=user.id,
        )
    else:
        if user.role != "owner":
            raise HTTPException(status_code=403)

        shared_count = await session.scalar(
            select(func.count())
            .select_from(Wallet)
            .where(
                Wallet.family_budget_id == user.family_budget_id,
                Wallet.is_deleted.is_(False),
                Wallet.is_personal.is_(False),
            )
        )
        if shared_count is not None and shared_count >= SHARED_WALLET_LIMIT:
            raise HTTPException(status_code=409, detail=LIMIT_SHARED_WALLETS)

        wallet = Wallet(
            family_budget_id=user.family_budget_id,
            name=body.name,
            currency=body.currency,
            is_personal=False,
            owner_user_id=None,
        )
    session.add(wallet)
    await session.commit()
    await session.refresh(wallet)
    return WalletResponse(
        id=wallet.id,
        name=wallet.name,
        currency=wallet.currency,
        translation_key=wallet.translation_key,
        is_personal=wallet.is_personal,
        transaction_count=0,
        has_active_goal=False,
    )


@router.patch("/wallets/{wallet_id}")
async def update_wallet(
    wallet_id: uuid.UUID,
    body: WalletUpdate,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WalletResponse:
    wallet = await get_active_wallet(session, wallet_id, user.family_budget_id)
    if wallet is None:
        raise HTTPException(status_code=404)

    if wallet.is_personal:
        require_wallet_visible(wallet, user)
    elif user.role != "owner":
        raise HTTPException(status_code=403)

    wallet.name = body.name
    await session.commit()
    await session.refresh(wallet)
    active_goal = await get_active_goal_for_wallet(session, wallet.id)
    return WalletResponse(
        id=wallet.id,
        name=wallet.name,
        currency=wallet.currency,
        translation_key=wallet.translation_key,
        is_personal=wallet.is_personal,
        transaction_count=await count_wallet_transactions(session, wallet.id),
        has_active_goal=active_goal is not None,
    )


@router.delete("/wallets/{wallet_id}")
async def delete_wallet(
    wallet_id: uuid.UUID,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WalletDeleteResponse:
    wallet = await get_active_wallet(session, wallet_id, user.family_budget_id)
    if wallet is None:
        raise HTTPException(status_code=404)

    if wallet.is_personal:
        require_wallet_visible(wallet, user)
    elif user.role != "owner":
        raise HTTPException(status_code=403)

    affected_transactions_count = await count_wallet_transactions(session, wallet.id)
    soft_delete(wallet)
    await session.commit()
    return WalletDeleteResponse(
        id=wallet.id,
        name=wallet.name,
        currency=wallet.currency,
        affected_transactions_count=affected_transactions_count,
    )
