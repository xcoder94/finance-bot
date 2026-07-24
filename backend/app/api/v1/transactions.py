import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import CurrentUserDep
from app.db import get_session
from app.schemas.transactions import (
    ExpenseCreate,
    ExpenseUpdate,
    IncomeCreate,
    IncomeUpdate,
    TransactionResponse,
    TransferCreate,
    TransferUpdate,
)
from app.services.transactions import (
    create_expense_transaction,
    create_income_transaction,
    create_transfer_transaction,
    get_active_transaction,
    require_modify_permission,
    soft_delete_transaction,
    transaction_to_response,
    update_expense_transaction,
    update_income_transaction,
    update_transfer_transaction,
)

router = APIRouter(prefix="/api/v1")


@router.post("/transactions/income", status_code=201)
async def create_income(
    body: IncomeCreate,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TransactionResponse:
    transaction = await create_income_transaction(session, user, body)
    return transaction_to_response(transaction)


@router.post("/transactions/expense", status_code=201)
async def create_expense(
    body: ExpenseCreate,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TransactionResponse:
    transaction = await create_expense_transaction(session, user, body)
    return transaction_to_response(transaction)


@router.post("/transactions/transfer", status_code=201)
async def create_transfer(
    body: TransferCreate,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TransactionResponse:
    transaction = await create_transfer_transaction(session, user, body)
    return transaction_to_response(transaction)


@router.get("/transactions/{transaction_id}")
async def get_transaction(
    transaction_id: uuid.UUID,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TransactionResponse:
    transaction = await get_active_transaction(session, transaction_id, user.family_budget_id)
    if transaction is None:
        raise HTTPException(status_code=404)
    return transaction_to_response(transaction)


@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: uuid.UUID,
    request: Request,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TransactionResponse:
    transaction = await get_active_transaction(session, transaction_id, user.family_budget_id)
    if transaction is None:
        raise HTTPException(status_code=404)
    require_modify_permission(user, transaction)

    body = await request.json()
    if transaction.type == "income":
        parsed = IncomeUpdate.model_validate(body)
        updated = await update_income_transaction(session, transaction, parsed)
    elif transaction.type == "expense":
        parsed = ExpenseUpdate.model_validate(body)
        updated = await update_expense_transaction(session, transaction, parsed)
    elif transaction.type == "transfer":
        parsed = TransferUpdate.model_validate(body)
        updated = await update_transfer_transaction(session, transaction, parsed)
    else:
        raise HTTPException(status_code=422, detail="Unknown transaction type")

    return transaction_to_response(updated)


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: uuid.UUID,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TransactionResponse:
    transaction = await get_active_transaction(session, transaction_id, user.family_budget_id)
    if transaction is None:
        raise HTTPException(status_code=404)
    require_modify_permission(user, transaction)
    soft_delete_transaction(transaction)
    await session.commit()
    return transaction_to_response(transaction)
