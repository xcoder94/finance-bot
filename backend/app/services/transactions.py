import uuid
from datetime import UTC, datetime
from decimal import Decimal

from aiogram import Bot
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.transactions import (
    ExpenseCreate,
    ExpenseUpdate,
    IncomeCreate,
    IncomeUpdate,
    TransactionResponse,
    TransferCreate,
    TransferUpdate,
)
from app.services.goals import check_goal_achievement
from app.services.wallet_visibility import require_wallet_visible
from app.services.wallets_categories import (
    get_active_expense_category,
    get_active_income_category,
    get_active_wallet,
)


async def _check_affected_wallets(
    session: AsyncSession,
    wallet_ids: set[uuid.UUID],
    *,
    bot: Bot | None = None,
) -> None:
    for wallet_id in wallet_ids:
        await check_goal_achievement(session, wallet_id, bot=bot)


def transaction_to_response(transaction: Transaction) -> TransactionResponse:
    return TransactionResponse.model_validate(transaction)


async def get_active_transaction(
    session: AsyncSession,
    transaction_id: uuid.UUID,
    family_budget_id: uuid.UUID,
) -> Transaction | None:
    stmt = select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.family_budget_id == family_budget_id,
        Transaction.is_deleted.is_(False),
    )
    return await session.scalar(stmt)


def require_modify_permission(user: User, transaction: Transaction) -> None:
    if user.role == "owner":
        return
    if transaction.created_by_user_id != user.id:
        raise HTTPException(status_code=403)


async def get_transaction_wallets(
    session: AsyncSession,
    transaction: Transaction,
    family_budget_id: uuid.UUID,
) -> tuple[Wallet | None, Wallet | None]:
    from_wallet = await get_active_wallet(session, transaction.wallet_id, family_budget_id)
    to_wallet = None
    if transaction.to_wallet_id is not None:
        to_wallet = await get_active_wallet(session, transaction.to_wallet_id, family_budget_id)
    return from_wallet, to_wallet


def is_personal_wallet_transaction(from_wallet: Wallet, to_wallet: Wallet | None) -> bool:
    return from_wallet.is_personal or (to_wallet is not None and to_wallet.is_personal)


def require_transaction_visible(
    from_wallet: Wallet | None,
    to_wallet: Wallet | None,
    user: User,
) -> None:
    if from_wallet is None:
        raise HTTPException(status_code=404)
    require_wallet_visible(from_wallet, user)
    if to_wallet is not None:
        require_wallet_visible(to_wallet, user)


def require_transaction_modify_permission(
    user: User,
    transaction: Transaction,
    from_wallet: Wallet,
    to_wallet: Wallet | None,
) -> None:
    require_transaction_visible(from_wallet, to_wallet, user)
    if is_personal_wallet_transaction(from_wallet, to_wallet):
        if from_wallet.is_personal and from_wallet.owner_user_id != user.id:
            raise HTTPException(status_code=404)
        if to_wallet is not None and to_wallet.is_personal and to_wallet.owner_user_id != user.id:
            raise HTTPException(status_code=404)
        return
    require_modify_permission(user, transaction)


def soft_delete_transaction(transaction: Transaction) -> None:
    transaction.is_deleted = True
    transaction.deleted_at = datetime.now(UTC)


async def validate_income_refs(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    income_category_id: uuid.UUID,
    user: User,
) -> None:
    wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    require_wallet_visible(wallet, user)
    category = await get_active_income_category(session, income_category_id, family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)


async def validate_expense_refs(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    expense_category_id: uuid.UUID,
    user: User,
) -> None:
    wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    require_wallet_visible(wallet, user)
    category = await get_active_expense_category(session, expense_category_id, family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)


async def validate_quick_entry_expense_refs(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    expense_category_id: uuid.UUID | None,
    user: User,
) -> None:
    wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    require_wallet_visible(wallet, user)
    if expense_category_id is None:
        return
    category = await get_active_expense_category(session, expense_category_id, family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)


async def validate_quick_entry_income_refs(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    income_category_id: uuid.UUID | None,
    user: User,
) -> None:
    wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    require_wallet_visible(wallet, user)
    if income_category_id is None:
        return
    category = await get_active_income_category(session, income_category_id, family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)


def compute_transfer_amounts(
    from_wallet: Wallet,
    to_wallet: Wallet,
    amount: int,
    rate: Decimal | None,
) -> tuple[int, Decimal | None]:
    if from_wallet.id == to_wallet.id:
        raise HTTPException(status_code=400, detail="wallet_id must not equal to_wallet_id")

    if from_wallet.currency == to_wallet.currency:
        if rate is not None:
            raise HTTPException(status_code=422, detail="rate must not be provided for same-currency transfer")
        return amount, None

    if rate is None or rate <= 0:
        raise HTTPException(status_code=422, detail="rate is required and must be greater than 0")

    if from_wallet.currency == "UZS" and to_wallet.currency == "USD":
        to_amount = round(amount / rate)
    elif from_wallet.currency == "USD" and to_wallet.currency == "UZS":
        to_amount = round(amount * rate)
    else:
        raise HTTPException(status_code=422, detail="Unsupported currency pair for transfer")

    return to_amount, rate


async def validate_transfer_refs(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    to_wallet_id: uuid.UUID,
    amount: int,
    rate: Decimal | None,
    user: User,
) -> tuple[Wallet, Wallet, int, Decimal | None]:
    from_wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    require_wallet_visible(from_wallet, user)
    to_wallet = await get_active_wallet(session, to_wallet_id, family_budget_id)
    require_wallet_visible(to_wallet, user)
    to_amount, stored_rate = compute_transfer_amounts(from_wallet, to_wallet, amount, rate)
    return from_wallet, to_wallet, to_amount, stored_rate


async def create_income_transaction(
    session: AsyncSession,
    user: User,
    body: IncomeCreate,
    *,
    bot: Bot | None = None,
) -> Transaction:
    await validate_income_refs(
        session,
        user.family_budget_id,
        body.wallet_id,
        body.income_category_id,
        user,
    )
    transaction = Transaction(
        family_budget_id=user.family_budget_id,
        type="income",
        wallet_id=body.wallet_id,
        amount=body.amount,
        income_category_id=body.income_category_id,
        comment=body.comment,
        created_by_user_id=user.id,
        transaction_date=body.transaction_date,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    await _check_affected_wallets(session, {body.wallet_id}, bot=bot)
    return transaction


async def create_expense_transaction(
    session: AsyncSession,
    user: User,
    body: ExpenseCreate,
    *,
    bot: Bot | None = None,
) -> Transaction:
    await validate_expense_refs(
        session,
        user.family_budget_id,
        body.wallet_id,
        body.expense_category_id,
        user,
    )
    transaction = Transaction(
        family_budget_id=user.family_budget_id,
        type="expense",
        wallet_id=body.wallet_id,
        amount=body.amount,
        expense_category_id=body.expense_category_id,
        comment=body.comment,
        created_by_user_id=user.id,
        transaction_date=body.transaction_date,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    await _check_affected_wallets(session, {body.wallet_id}, bot=bot)
    return transaction


async def create_transfer_transaction(
    session: AsyncSession,
    user: User,
    body: TransferCreate,
    *,
    bot: Bot | None = None,
) -> Transaction:
    _, _, to_amount, stored_rate = await validate_transfer_refs(
        session,
        user.family_budget_id,
        body.wallet_id,
        body.to_wallet_id,
        body.amount,
        body.rate,
        user,
    )
    transaction = Transaction(
        family_budget_id=user.family_budget_id,
        type="transfer",
        wallet_id=body.wallet_id,
        to_wallet_id=body.to_wallet_id,
        amount=body.amount,
        to_amount=to_amount,
        rate=stored_rate,
        comment=body.comment,
        created_by_user_id=user.id,
        transaction_date=body.transaction_date,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    await _check_affected_wallets(
        session,
        {body.wallet_id, body.to_wallet_id},
        bot=bot,
    )
    return transaction


async def update_income_transaction(
    session: AsyncSession,
    transaction: Transaction,
    body: IncomeUpdate,
    user: User,
    *,
    bot: Bot | None = None,
) -> Transaction:
    await validate_income_refs(
        session,
        transaction.family_budget_id,
        body.wallet_id,
        body.income_category_id,
        user,
    )
    affected = {transaction.wallet_id, body.wallet_id}
    transaction.transaction_date = body.transaction_date
    transaction.amount = body.amount
    transaction.wallet_id = body.wallet_id
    transaction.income_category_id = body.income_category_id
    transaction.comment = body.comment
    transaction.to_wallet_id = None
    transaction.to_amount = None
    transaction.rate = None
    transaction.expense_category_id = None
    await session.commit()
    await session.refresh(transaction)
    await _check_affected_wallets(session, affected, bot=bot)
    return transaction


async def update_expense_transaction(
    session: AsyncSession,
    transaction: Transaction,
    body: ExpenseUpdate,
    user: User,
    *,
    bot: Bot | None = None,
) -> Transaction:
    await validate_expense_refs(
        session,
        transaction.family_budget_id,
        body.wallet_id,
        body.expense_category_id,
        user,
    )
    affected = {transaction.wallet_id, body.wallet_id}
    transaction.transaction_date = body.transaction_date
    transaction.amount = body.amount
    transaction.wallet_id = body.wallet_id
    transaction.expense_category_id = body.expense_category_id
    transaction.comment = body.comment
    transaction.to_wallet_id = None
    transaction.to_amount = None
    transaction.rate = None
    transaction.income_category_id = None
    await session.commit()
    await session.refresh(transaction)
    await _check_affected_wallets(session, affected, bot=bot)
    return transaction


async def update_transfer_transaction(
    session: AsyncSession,
    transaction: Transaction,
    body: TransferUpdate,
    user: User,
    *,
    bot: Bot | None = None,
) -> Transaction:
    _, _, to_amount, stored_rate = await validate_transfer_refs(
        session,
        transaction.family_budget_id,
        body.wallet_id,
        body.to_wallet_id,
        body.amount,
        body.rate,
        user,
    )
    affected = {transaction.wallet_id, body.wallet_id}
    if transaction.to_wallet_id is not None:
        affected.add(transaction.to_wallet_id)
    affected.add(body.to_wallet_id)
    transaction.transaction_date = body.transaction_date
    transaction.wallet_id = body.wallet_id
    transaction.to_wallet_id = body.to_wallet_id
    transaction.amount = body.amount
    transaction.to_amount = to_amount
    transaction.rate = stored_rate
    transaction.comment = body.comment
    transaction.income_category_id = None
    transaction.expense_category_id = None
    await session.commit()
    await session.refresh(transaction)
    await _check_affected_wallets(session, affected, bot=bot)
    return transaction


async def delete_transaction_record(
    session: AsyncSession,
    transaction: Transaction,
    *,
    bot: Bot | None = None,
) -> Transaction:
    affected = {transaction.wallet_id}
    if transaction.to_wallet_id is not None:
        affected.add(transaction.to_wallet_id)
    soft_delete_transaction(transaction)
    await session.commit()
    await _check_affected_wallets(session, affected, bot=bot)
    return transaction
