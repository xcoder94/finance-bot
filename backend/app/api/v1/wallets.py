import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import CurrentUserDep, OwnerUserDep
from app.db import get_session
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.schemas.wallets_categories import (
    WalletCreate,
    WalletDeleteResponse,
    WalletResponse,
    WalletUpdate,
)
from app.services.entity_limits import (
    LIMIT_SHARED_WALLETS,
    SHARED_WALLET_LIMIT,
)
from app.services.wallet_visibility import visible_wallets_clause
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
        )
        for wallet, transaction_count in rows
    ]


@router.post("/wallets", status_code=201)
async def create_wallet(
    body: WalletCreate,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WalletResponse:
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
    )


@router.patch("/wallets/{wallet_id}")
async def update_wallet(
    wallet_id: uuid.UUID,
    body: WalletUpdate,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WalletResponse:
    wallet = await get_active_wallet(session, wallet_id, user.family_budget_id)
    if wallet is None:
        raise HTTPException(status_code=404)

    wallet.name = body.name
    await session.commit()
    await session.refresh(wallet)
    return WalletResponse(
        id=wallet.id,
        name=wallet.name,
        currency=wallet.currency,
        translation_key=wallet.translation_key,
        is_personal=wallet.is_personal,
        transaction_count=await count_wallet_transactions(session, wallet.id),
    )


@router.delete("/wallets/{wallet_id}")
async def delete_wallet(
    wallet_id: uuid.UUID,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WalletDeleteResponse:
    wallet = await get_active_wallet(session, wallet_id, user.family_budget_id)
    if wallet is None:
        raise HTTPException(status_code=404)

    affected_transactions_count = await count_wallet_transactions(session, wallet.id)
    soft_delete(wallet)
    await session.commit()
    return WalletDeleteResponse(
        id=wallet.id,
        name=wallet.name,
        currency=wallet.currency,
        affected_transactions_count=affected_transactions_count,
    )
