import uuid
from datetime import UTC, datetime
from decimal import Decimal

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
from app.services.wallets_categories import (
    get_active_expense_category,
    get_active_income_category,
    get_active_wallet,
)


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


def soft_delete_transaction(transaction: Transaction) -> None:
    transaction.is_deleted = True
    transaction.deleted_at = datetime.now(UTC)


async def validate_income_refs(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    income_category_id: uuid.UUID,
) -> None:
    wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    if wallet is None:
        raise HTTPException(status_code=404)
    category = await get_active_income_category(session, income_category_id, family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)


async def validate_expense_refs(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    expense_category_id: uuid.UUID,
) -> None:
    wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    if wallet is None:
        raise HTTPException(status_code=404)
    category = await get_active_expense_category(session, expense_category_id, family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)
    if category.parent_id is None:
        raise HTTPException(status_code=400, detail="Expense category must be a subcategory")


async def validate_quick_entry_expense_refs(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    expense_category_id: uuid.UUID | None,
) -> None:
    wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    if wallet is None:
        raise HTTPException(status_code=404)
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
) -> None:
    wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    if wallet is None:
        raise HTTPException(status_code=404)
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
) -> tuple[Wallet, Wallet, int, Decimal | None]:
    from_wallet = await get_active_wallet(session, wallet_id, family_budget_id)
    if from_wallet is None:
        raise HTTPException(status_code=404)
    to_wallet = await get_active_wallet(session, to_wallet_id, family_budget_id)
    if to_wallet is None:
        raise HTTPException(status_code=404)
    to_amount, stored_rate = compute_transfer_amounts(from_wallet, to_wallet, amount, rate)
    return from_wallet, to_wallet, to_amount, stored_rate


async def create_income_transaction(
    session: AsyncSession,
    user: User,
    body: IncomeCreate,
) -> Transaction:
    await validate_income_refs(
        session,
        user.family_budget_id,
        body.wallet_id,
        body.income_category_id,
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
    return transaction


async def create_expense_transaction(
    session: AsyncSession,
    user: User,
    body: ExpenseCreate,
) -> Transaction:
    await validate_expense_refs(
        session,
        user.family_budget_id,
        body.wallet_id,
        body.expense_category_id,
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
    return transaction


async def create_transfer_transaction(
    session: AsyncSession,
    user: User,
    body: TransferCreate,
) -> Transaction:
    _, _, to_amount, stored_rate = await validate_transfer_refs(
        session,
        user.family_budget_id,
        body.wallet_id,
        body.to_wallet_id,
        body.amount,
        body.rate,
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
    return transaction


async def update_income_transaction(
    session: AsyncSession,
    transaction: Transaction,
    body: IncomeUpdate,
) -> Transaction:
    await validate_income_refs(
        session,
        transaction.family_budget_id,
        body.wallet_id,
        body.income_category_id,
    )
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
    return transaction


async def update_expense_transaction(
    session: AsyncSession,
    transaction: Transaction,
    body: ExpenseUpdate,
) -> Transaction:
    await validate_expense_refs(
        session,
        transaction.family_budget_id,
        body.wallet_id,
        body.expense_category_id,
    )
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
    return transaction


async def update_transfer_transaction(
    session: AsyncSession,
    transaction: Transaction,
    body: TransferUpdate,
) -> Transaction:
    _, _, to_amount, stored_rate = await validate_transfer_refs(
        session,
        transaction.family_budget_id,
        body.wallet_id,
        body.to_wallet_id,
        body.amount,
        body.rate,
    )
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
    return transaction
