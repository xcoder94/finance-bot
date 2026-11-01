import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import CurrentUserDep
from app.db import get_session
from app.config import receipt_photo_enabled
from app.models.shopping import ShoppingPurchase
from app.schemas.shopping import (
    PendingAmount,
    PendingCreate,
    PendingStatus,
    PurchaseCreate,
    PurchaseResult,
    ShoppingItemBody,
    ShoppingItemResponse,
)
from app.services.shopping_pending_notify import send_pending_hint
from app.services.shopping import (
    CODE_LIMIT,
    CODE_RECEIPT_DISABLED,
    METHOD_FROM_DB,
    complete_pending_purchase,
    create_pending_purchase,
    get_own_purchase,
    add_shopping_items,
    complete_purchase_manual,
    delete_item,
    get_purchase_result,
    list_items,
    rename_item,
)

router = APIRouter(prefix="/api/v1/shopping")

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/items")
async def get_items(user: CurrentUserDep, session: SessionDep) -> list[ShoppingItemResponse]:
    items = await list_items(session, user.family_budget_id)
    return [ShoppingItemResponse.model_validate(i) for i in items]


@router.post("/items", status_code=201)
async def create_item(
    body: ShoppingItemBody, user: CurrentUserDep, session: SessionDep, response: Response
) -> ShoppingItemResponse:
    result = await add_shopping_items(session, user, [body.name])
    if result.over_limit:
        raise HTTPException(status_code=409, detail=CODE_LIMIT)
    if result.added:
        return ShoppingItemResponse.model_validate(result.added[0])
    response.status_code = 200
    return ShoppingItemResponse.model_validate(result.existing[0])


@router.patch("/items/{item_id}")
async def patch_item(
    item_id: uuid.UUID, body: ShoppingItemBody, user: CurrentUserDep, session: SessionDep
) -> ShoppingItemResponse:
    item = await rename_item(session, user, item_id, body.name)
    return ShoppingItemResponse.model_validate(item)


@router.delete("/items/{item_id}", status_code=204)
async def remove_item(item_id: uuid.UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    await delete_item(session, user, item_id)
    return Response(status_code=204)


@router.post("/purchases", status_code=201)
async def create_purchase(
    body: PurchaseCreate, user: CurrentUserDep, session: SessionDep, response: Response
) -> PurchaseResult:
    result, created = await complete_purchase_manual(
        session,
        user,
        item_ids=body.item_ids,
        amount=body.amount,
        client_token=body.client_token,
    )
    if not created:
        response.status_code = 200
    return result


def _pending_status(purchase: ShoppingPurchase) -> PendingStatus:
    done = purchase.status == "completed"
    return PendingStatus(
        id=purchase.id,
        status=purchase.status,
        method=METHOD_FROM_DB.get(purchase.method or ""),
        expires_at=purchase.expires_at,
        purchase_id=purchase.id if done else None,
        amount=purchase.amount,
    )


@router.post("/purchases/pending", status_code=201)
async def create_pending(
    body: PendingCreate, user: CurrentUserDep, session: SessionDep, response: Response
) -> PendingStatus:
    if body.method == "receipt" and not receipt_photo_enabled():
        raise HTTPException(status_code=409, detail=CODE_RECEIPT_DISABLED)
    purchase, created = await create_pending_purchase(
        session,
        user,
        item_ids=body.item_ids,
        method=body.method,
        client_token=body.client_token,
    )
    if created:
        await send_pending_hint(user, purchase.method)
    else:
        response.status_code = 200
    return _pending_status(purchase)


@router.get("/purchases/pending/{purchase_id}")
async def get_pending(
    purchase_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> PendingStatus:
    return _pending_status(await get_own_purchase(session, user, purchase_id))


@router.post("/purchases/pending/{purchase_id}/amount", status_code=201)
async def post_pending_amount(
    purchase_id: uuid.UUID,
    body: PendingAmount,
    user: CurrentUserDep,
    session: SessionDep,
    response: Response,
) -> PurchaseResult:
    result, created = await complete_pending_purchase(
        session, user, purchase_id, amount=body.amount, method="manual", channel="app"
    )
    if not created:
        response.status_code = 200
    return result


@router.get("/purchases/{purchase_id}")
async def get_purchase(
    purchase_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> PurchaseResult:
    return await get_purchase_result(session, user, purchase_id)
