import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import CurrentUserDep, OwnerUserDep
from app.db import get_session
from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.schemas.wallets_categories import (
    ExpenseCategoryCreate,
    ExpenseCategoryDeleteResponse,
    ExpenseCategoryResponse,
    ExpenseCategoryUpdate,
    IncomeCategoryCreate,
    IncomeCategoryDeleteResponse,
    IncomeCategoryResponse,
    IncomeCategoryUpdate,
)
from app.services.entity_limits import (
    LIMIT_EXPENSE_PARENTS,
    LIMIT_INCOME_CATEGORIES,
    PARENT_CATEGORY_LIMIT,
    SUBCATEGORY_LIMIT,
    limit_subcategories,
)
from app.services.wallets_categories import (
    count_expense_category_transactions,
    count_income_category_transactions,
    get_active_expense_category,
    get_active_expense_parent,
    get_active_income_category,
    soft_delete,
)

router = APIRouter(prefix="/api/v1")


@router.get("/categories/income")
async def list_income_categories(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[IncomeCategoryResponse]:
    transaction_counts = (
        select(
            Transaction.income_category_id.label("category_id"),
            func.count().label("transaction_count"),
        )
        .where(
            Transaction.family_budget_id == user.family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.income_category_id.is_not(None),
        )
        .group_by(Transaction.income_category_id)
        .subquery()
    )
    stmt = (
        select(
            IncomeCategory,
            func.coalesce(transaction_counts.c.transaction_count, 0).label(
                "transaction_count"
            ),
        )
        .outerjoin(
            transaction_counts,
            transaction_counts.c.category_id == IncomeCategory.id,
        )
        .where(
            IncomeCategory.family_budget_id == user.family_budget_id,
            IncomeCategory.is_deleted.is_(False),
        )
        .order_by(IncomeCategory.created_at)
    )
    rows = (await session.execute(stmt)).all()
    return [
        IncomeCategoryResponse(
            id=category.id,
            name=category.name,
            translation_key=category.translation_key,
            transaction_count=int(transaction_count),
        )
        for category, transaction_count in rows
    ]


@router.post("/categories/income", status_code=201)
async def create_income_category(
    body: IncomeCategoryCreate,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IncomeCategoryResponse:
    income_count = await session.scalar(
        select(func.count())
        .select_from(IncomeCategory)
        .where(
            IncomeCategory.family_budget_id == user.family_budget_id,
            IncomeCategory.is_deleted.is_(False),
        )
    )
    if income_count is not None and income_count >= PARENT_CATEGORY_LIMIT:
        raise HTTPException(status_code=409, detail=LIMIT_INCOME_CATEGORIES)

    category = IncomeCategory(
        family_budget_id=user.family_budget_id,
        name=body.name,
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return IncomeCategoryResponse(
        id=category.id,
        name=category.name,
        translation_key=category.translation_key,
        transaction_count=0,
    )


@router.patch("/categories/income/{category_id}")
async def update_income_category(
    category_id: uuid.UUID,
    body: IncomeCategoryUpdate,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IncomeCategoryResponse:
    category = await get_active_income_category(session, category_id, user.family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)

    category.name = body.name
    await session.commit()
    await session.refresh(category)
    return IncomeCategoryResponse(
        id=category.id,
        name=category.name,
        translation_key=category.translation_key,
        transaction_count=await count_income_category_transactions(session, category.id),
    )


@router.delete("/categories/income/{category_id}")
async def delete_income_category(
    category_id: uuid.UUID,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IncomeCategoryDeleteResponse:
    category = await get_active_income_category(session, category_id, user.family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)

    affected_transactions_count = await count_income_category_transactions(session, category.id)
    soft_delete(category)
    await session.commit()
    return IncomeCategoryDeleteResponse(
        id=category.id,
        name=category.name,
        affected_transactions_count=affected_transactions_count,
    )


@router.get("/categories/expense")
async def list_expense_categories(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ExpenseCategoryResponse]:
    transaction_counts = (
        select(
            Transaction.expense_category_id.label("category_id"),
            func.count().label("transaction_count"),
        )
        .where(
            Transaction.family_budget_id == user.family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.expense_category_id.is_not(None),
        )
        .group_by(Transaction.expense_category_id)
        .subquery()
    )
    stmt = (
        select(
            ExpenseCategory,
            func.coalesce(transaction_counts.c.transaction_count, 0).label(
                "transaction_count"
            ),
        )
        .outerjoin(
            transaction_counts,
            transaction_counts.c.category_id == ExpenseCategory.id,
        )
        .where(
            ExpenseCategory.family_budget_id == user.family_budget_id,
            ExpenseCategory.is_deleted.is_(False),
        )
        .order_by(ExpenseCategory.created_at)
    )
    rows = (await session.execute(stmt)).all()
    return [
        ExpenseCategoryResponse(
            id=category.id,
            name=category.name,
            translation_key=category.translation_key,
            parent_id=category.parent_id,
            transaction_count=int(transaction_count),
        )
        for category, transaction_count in rows
    ]


@router.post("/categories/expense", status_code=201)
async def create_expense_category(
    body: ExpenseCategoryCreate,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExpenseCategoryResponse:
    if body.parent_id is None:
        parent_count = await session.scalar(
            select(func.count())
            .select_from(ExpenseCategory)
            .where(
                ExpenseCategory.family_budget_id == user.family_budget_id,
                ExpenseCategory.is_deleted.is_(False),
                ExpenseCategory.parent_id.is_(None),
            )
        )
        if parent_count is not None and parent_count >= PARENT_CATEGORY_LIMIT:
            raise HTTPException(status_code=409, detail=LIMIT_EXPENSE_PARENTS)
    else:
        parent = await get_active_expense_parent(session, body.parent_id, user.family_budget_id)
        if parent is None:
            raise HTTPException(status_code=404)
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=400,
                detail="parent_id must reference a top-level category",
            )
        subcategory_count = await session.scalar(
            select(func.count())
            .select_from(ExpenseCategory)
            .where(
                ExpenseCategory.family_budget_id == user.family_budget_id,
                ExpenseCategory.is_deleted.is_(False),
                ExpenseCategory.parent_id == body.parent_id,
            )
        )
        if subcategory_count is not None and subcategory_count >= SUBCATEGORY_LIMIT:
            raise HTTPException(
                status_code=409,
                detail=limit_subcategories(parent.name),
            )

    category = ExpenseCategory(
        family_budget_id=user.family_budget_id,
        name=body.name,
        parent_id=body.parent_id,
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return ExpenseCategoryResponse(
        id=category.id,
        name=category.name,
        translation_key=category.translation_key,
        parent_id=category.parent_id,
        transaction_count=0,
    )


@router.patch("/categories/expense/{category_id}")
async def update_expense_category(
    category_id: uuid.UUID,
    body: ExpenseCategoryUpdate,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExpenseCategoryResponse:
    category = await get_active_expense_category(session, category_id, user.family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)

    category.name = body.name
    await session.commit()
    await session.refresh(category)
    return ExpenseCategoryResponse(
        id=category.id,
        name=category.name,
        translation_key=category.translation_key,
        parent_id=category.parent_id,
        transaction_count=await count_expense_category_transactions(session, category.id),
    )


@router.delete("/categories/expense/{category_id}")
async def delete_expense_category(
    category_id: uuid.UUID,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExpenseCategoryDeleteResponse:
    category = await get_active_expense_category(session, category_id, user.family_budget_id)
    if category is None:
        raise HTTPException(status_code=404)

    affected_transactions_count = await count_expense_category_transactions(session, category.id)
    soft_delete(category)

    if category.parent_id is None:
        stmt = select(ExpenseCategory).where(
            ExpenseCategory.parent_id == category.id,
            ExpenseCategory.family_budget_id == user.family_budget_id,
            ExpenseCategory.is_deleted.is_(False),
        )
        subcategories = (await session.scalars(stmt)).all()
        for subcategory in subcategories:
            soft_delete(subcategory)

    await session.commit()
    return ExpenseCategoryDeleteResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        affected_transactions_count=affected_transactions_count,
    )
