"""Shopping list and one-sum purchase completion (MVP 3, m3-3).

``add_shopping_items`` is shared with the bot (m3-4). Every function that checks
the 100-item cap or the purchase idempotency runs under ``lock_family_budget``.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.shopping import ShoppingItem, ShoppingPurchase
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.shopping import PurchaseResult, normalize_item_name
from app.services.entity_limits import lock_family_budget
from app.services.goals import check_goal_achievement
from app.services.history_analytics import get_summary
from app.services.wallet_visibility import visible_wallets_clause

SHOPPING_ITEMS_LIMIT = 100
COMMENT_MAX = 200
UNCATEGORISED_LABEL = "Без категории"
TASHKENT = ZoneInfo("Asia/Tashkent")

# Machine-readable codes in HTTPException.detail (the frontend maps them to texts).
CODE_LIMIT = "shopping_limit"
CODE_ALREADY_IN_LIST = "already_in_list"
CODE_NO_WALLET = "no_wallet"
CODE_NOT_COMPLETED = "purchase_not_completed"


@dataclass
class AddItemsResult:
    added: list[ShoppingItem] = field(default_factory=list)
    existing: list[ShoppingItem] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    over_limit: list[str] = field(default_factory=list)


async def list_items(session: AsyncSession, family_budget_id: uuid.UUID) -> list[ShoppingItem]:
    stmt = (
        select(ShoppingItem)
        .where(ShoppingItem.family_budget_id == family_budget_id)
        .order_by(ShoppingItem.created_at, ShoppingItem.id)
    )
    return list((await session.scalars(stmt)).all())


async def _count_items(session: AsyncSession, family_budget_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(ShoppingItem)
            .where(ShoppingItem.family_budget_id == family_budget_id)
        )
        or 0
    )


async def _find_by_lname(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    name: str,
    *,
    exclude_id: uuid.UUID | None = None,
) -> ShoppingItem | None:
    stmt = select(ShoppingItem).where(
        ShoppingItem.family_budget_id == family_budget_id,
        func.lower(ShoppingItem.name) == func.lower(name),
    )
    if exclude_id is not None:
        stmt = stmt.where(ShoppingItem.id != exclude_id)
    return await session.scalar(stmt)


async def add_shopping_items(
    session: AsyncSession, user: User, names: list[str]
) -> AddItemsResult:
    """Add names to the family list: trim/collapse, dedupe without case, cap at 100.

    Existing names are returned in ``existing`` (not duplicated). Names that no
    longer fit under the cap land in ``over_limit``; empty/too long ones in
    ``invalid``. All of it happens in one transaction under the family lock.
    """
    result = AddItemsResult()
    await lock_family_budget(session, user.family_budget_id)
    count = await _count_items(session, user.family_budget_id)
    seen: set[str] = set()
    for raw in names:
        try:
            name = normalize_item_name(raw)
        except ValueError:
            result.invalid.append(raw)
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        existing = await _find_by_lname(session, user.family_budget_id, name)
        if existing is not None:
            result.existing.append(existing)
            continue
        if count >= SHOPPING_ITEMS_LIMIT:
            result.over_limit.append(name)
            continue
        item = ShoppingItem(
            family_budget_id=user.family_budget_id,
            name=name,
            added_by_user_id=user.id,
            # app-side clock: now() is the transaction start, so a batch from
            # the bot would otherwise get identical timestamps and lose its order
            created_at=datetime.now(UTC),
        )
        session.add(item)
        await session.flush()
        await session.refresh(item)
        result.added.append(item)
        count += 1
    await session.commit()
    return result


async def get_family_item(
    session: AsyncSession, family_budget_id: uuid.UUID, item_id: uuid.UUID
) -> ShoppingItem:
    item = await session.scalar(
        select(ShoppingItem).where(
            ShoppingItem.id == item_id, ShoppingItem.family_budget_id == family_budget_id
        )
    )
    if item is None:
        raise HTTPException(status_code=404)
    return item


async def rename_item(
    session: AsyncSession, user: User, item_id: uuid.UUID, name: str
) -> ShoppingItem:
    await lock_family_budget(session, user.family_budget_id)
    item = await get_family_item(session, user.family_budget_id, item_id)
    clash = await _find_by_lname(session, user.family_budget_id, name, exclude_id=item.id)
    if clash is not None:
        raise HTTPException(status_code=409, detail=CODE_ALREADY_IN_LIST)
    item.name = name
    await session.commit()
    await session.refresh(item)
    return item


async def delete_item(session: AsyncSession, user: User, item_id: uuid.UUID) -> None:
    item = await get_family_item(session, user.family_budget_id, item_id)
    await session.delete(item)
    await session.commit()


# ---------------------------------------------------------------------------
# Purchases
# ---------------------------------------------------------------------------


async def _resolve_wallet(session: AsyncSession, user: User) -> Wallet:
    """Default wallet of the user if usable, else the oldest shared active wallet."""
    base = (
        select(Wallet)
        .where(
            Wallet.family_budget_id == user.family_budget_id,
            Wallet.is_deleted.is_(False),
            visible_wallets_clause(user),
        )
    )
    if user.default_wallet_id is not None:
        wallet = await session.scalar(base.where(Wallet.id == user.default_wallet_id))
        if wallet is not None:
            return wallet
    wallet = await session.scalar(
        base.where(Wallet.is_personal.is_(False)).order_by(Wallet.created_at, Wallet.id).limit(1)
    )
    if wallet is None:
        raise HTTPException(status_code=409, detail=CODE_NO_WALLET)
    return wallet


async def _resolve_category_id(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> uuid.UUID | None:
    """«Продукты» (seed key groceries) -> parent «Еда» (food) -> None («Без категории»)."""
    base = select(ExpenseCategory.id).where(
        ExpenseCategory.family_budget_id == family_budget_id,
        ExpenseCategory.is_deleted.is_(False),
    )
    order = (ExpenseCategory.created_at, ExpenseCategory.id)
    groceries = await session.scalar(
        base.where(
            ExpenseCategory.translation_key == "groceries",
            ExpenseCategory.parent_id.is_not(None),
        )
        .order_by(*order)
        .limit(1)
    )
    if groceries is not None:
        return groceries
    return await session.scalar(
        base.where(
            ExpenseCategory.translation_key == "food", ExpenseCategory.parent_id.is_(None)
        )
        .order_by(*order)
        .limit(1)
    )


async def _category_label(session: AsyncSession, category_id: uuid.UUID | None) -> str:
    if category_id is None:
        return UNCATEGORISED_LABEL
    category = await session.get(ExpenseCategory, category_id)
    if category is None:
        return UNCATEGORISED_LABEL
    if category.parent_id is None:
        return category.name
    parent = await session.get(ExpenseCategory, category.parent_id)
    return f"{parent.name} · {category.name}" if parent is not None else category.name


async def _month_remaining(session: AsyncSession, family_budget_id: uuid.UUID) -> int:
    """Same number as «Осталось до конца месяца» on Home: UZS income - expense
    of the current Tashkent month over shared wallets (analytics summary)."""
    now_local = datetime.now(TASHKENT)
    start = datetime(now_local.year, now_local.month, 1, tzinfo=TASHKENT)
    if now_local.month == 12:
        next_start = datetime(now_local.year + 1, 1, 1, tzinfo=TASHKENT)
    else:
        next_start = datetime(now_local.year, now_local.month + 1, 1, tzinfo=TASHKENT)
    end = next_start.astimezone(UTC) - timedelta(microseconds=1)
    summary = await get_summary(session, family_budget_id, start.astimezone(UTC), end)
    for row in summary.by_currency:
        if row.currency == "UZS":
            return row.income - row.expense
    return 0


async def build_purchase_result(
    session: AsyncSession, purchase: ShoppingPurchase
) -> PurchaseResult:
    if purchase.status != "completed" or purchase.transaction_id is None:
        raise HTTPException(status_code=404)
    transaction = await session.get(Transaction, purchase.transaction_id)
    wallet = await session.get(Wallet, transaction.wallet_id)
    return PurchaseResult(
        id=purchase.id,
        transaction_id=transaction.id,
        items_recorded=len(purchase.bought_item_names or []),
        amount=purchase.amount,
        currency=wallet.currency,
        category_label=await _category_label(session, transaction.expense_category_id),
        wallet_name=wallet.name,
        remaining=await _month_remaining(session, purchase.family_budget_id),
        items_left=await _count_items(session, purchase.family_budget_id),
    )


async def get_purchase_result(
    session: AsyncSession, user: User, purchase_id: uuid.UUID
) -> PurchaseResult:
    purchase = await session.scalar(
        select(ShoppingPurchase).where(
            ShoppingPurchase.id == purchase_id,
            ShoppingPurchase.family_budget_id == user.family_budget_id,
        )
    )
    if purchase is None:
        raise HTTPException(status_code=404)
    return await build_purchase_result(session, purchase)


async def _write_off(
    session: AsyncSession, user: User, ids: list[uuid.UUID], amount: int
) -> tuple[Transaction, Wallet, list[str]]:
    """Under the family lock: wallet/category, DELETE items RETURNING, one expense.

    Raises 409 no_wallet before touching anything. Does not commit.
    """
    wallet = await _resolve_wallet(session, user)
    category_id = await _resolve_category_id(session, user.family_budget_id)

    rows = (
        await session.execute(
            delete(ShoppingItem)
            .where(
                ShoppingItem.id.in_(ids),
                ShoppingItem.family_budget_id == user.family_budget_id,
            )
            .returning(ShoppingItem.id, ShoppingItem.name)
        )
    ).all()
    name_by_id = {row.id: row.name for row in rows}
    names = [name_by_id[i] for i in ids if i in name_by_id]

    transaction = Transaction(
        family_budget_id=user.family_budget_id,
        type="expense",
        wallet_id=wallet.id,
        amount=amount,
        expense_category_id=category_id,
        comment=(", ".join(names)[:COMMENT_MAX] or None),
        created_by_user_id=user.id,
        transaction_date=datetime.now(UTC),
    )
    session.add(transaction)
    await session.flush()
    return transaction, wallet, names


async def complete_purchase_manual(
    session: AsyncSession,
    user: User,
    *,
    item_ids: list[uuid.UUID],
    amount: int,
    client_token: uuid.UUID,
) -> tuple[PurchaseResult, bool]:
    """Complete a purchase with one manual sum. Returns (result, created).

    ``created`` is False for an idempotent replay of the same client_token.
    Algorithm (work/db/m3-schema.md §2): family lock -> replay check -> wallet ->
    DELETE items RETURNING -> one expense -> purchase row, in one transaction.
    """
    ids = list(dict.fromkeys(item_ids))

    # Items that exist but belong to ANOTHER family -> 404 and nothing is done.
    foreign = await session.scalar(
        select(func.count())
        .select_from(ShoppingItem)
        .where(
            ShoppingItem.id.in_(ids),
            ShoppingItem.family_budget_id != user.family_budget_id,
        )
    )
    if foreign:
        raise HTTPException(status_code=404)

    await lock_family_budget(session, user.family_budget_id)

    existing = await session.scalar(
        select(ShoppingPurchase).where(
            ShoppingPurchase.created_by_user_id == user.id,
            ShoppingPurchase.client_token == client_token,
        )
    )
    if existing is not None:
        if existing.status != "completed":
            raise HTTPException(status_code=409, detail=CODE_NOT_COMPLETED)
        return await build_purchase_result(session, existing), False

    transaction, wallet, names = await _write_off(session, user, ids, amount)

    now = datetime.now(UTC)
    purchase = ShoppingPurchase(
        family_budget_id=user.family_budget_id,
        created_by_user_id=user.id,
        client_token=client_token,
        status="completed",
        method="manual",
        item_ids=ids,
        bought_item_names=names,
        amount=amount,
        transaction_id=transaction.id,
        closed_at=now,
    )
    session.add(purchase)
    await session.commit()
    await session.refresh(purchase)
    await check_goal_achievement(session, wallet.id)
    return await build_purchase_result(session, purchase), True


# ---------------------------------------------------------------------------
# Purchases waiting for a sum from the bot (photo / voice), m3-4b
# ---------------------------------------------------------------------------

OPEN_STATUSES = ("awaiting", "unrecognized")
PENDING_TTL = timedelta(minutes=30)
PURCHASE_RETENTION = timedelta(days=30)
PURGE_BATCH = 5000

CODE_RECEIPT_DISABLED = "receipt_disabled"
CODE_PURCHASE_CLOSED = "purchase_closed"
CODE_TOKEN_CONFLICT = "token_conflict"

# API method name -> stored method
METHOD_TO_DB = {"receipt": "photo", "voice": "voice"}
METHOD_FROM_DB = {"photo": "receipt", "voice": "voice", "manual": "manual"}


def _is_open(purchase: ShoppingPurchase) -> bool:
    return purchase.status in OPEN_STATUSES


def _close(purchase: ShoppingPurchase, status: str) -> None:
    purchase.status = status
    purchase.closed_at = datetime.now(UTC)


async def _expire_if_due(session: AsyncSession, purchase: ShoppingPurchase) -> bool:
    """Lazy expiry: an open row past expires_at becomes expired. True if it flipped."""
    if _is_open(purchase) and purchase.expires_at < datetime.now(UTC):
        _close(purchase, "expired")
        await session.commit()
        return True
    return False


async def create_pending_purchase(
    session: AsyncSession,
    user: User,
    *,
    item_ids: list[uuid.UUID],
    method: str,
    client_token: uuid.UUID | None,
) -> tuple[ShoppingPurchase, bool]:
    """Open a purchase that waits for a sum from the bot. Returns (row, created)."""
    ids = list(dict.fromkeys(item_ids))
    foreign = await session.scalar(
        select(func.count())
        .select_from(ShoppingItem)
        .where(
            ShoppingItem.id.in_(ids),
            ShoppingItem.family_budget_id != user.family_budget_id,
        )
    )
    if foreign:
        raise HTTPException(status_code=404)

    await lock_family_budget(session, user.family_budget_id)

    if client_token is not None:
        existing = await session.scalar(
            select(ShoppingPurchase).where(
                ShoppingPurchase.created_by_user_id == user.id,
                ShoppingPurchase.client_token == client_token,
            )
        )
        if existing is not None:
            same_items = set(existing.item_ids) == set(ids)
            same_method = (not _is_open(existing)) or existing.method == METHOD_TO_DB[method]
            if not (same_items and same_method):
                raise HTTPException(status_code=409, detail=CODE_TOKEN_CONFLICT)
            return existing, False

    previous = await session.scalar(
        select(ShoppingPurchase)
        .where(
            ShoppingPurchase.created_by_user_id == user.id,
            ShoppingPurchase.status.in_(OPEN_STATUSES),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if previous is not None:
        _close(
            previous,
            "expired" if previous.expires_at < datetime.now(UTC) else "cancelled",
        )
        await session.flush()

    purchase = ShoppingPurchase(
        family_budget_id=user.family_budget_id,
        created_by_user_id=user.id,
        client_token=client_token or uuid.uuid4(),
        status="awaiting",
        method=METHOD_TO_DB[method],
        item_ids=ids,
        expires_at=datetime.now(UTC) + PENDING_TTL,
    )
    session.add(purchase)
    await session.commit()
    await session.refresh(purchase)
    return purchase, True


async def get_own_purchase(
    session: AsyncSession, user: User, purchase_id: uuid.UUID
) -> ShoppingPurchase:
    """The user's own purchase (lazy expiry applied); 404 for anyone else's."""
    purchase = await session.scalar(
        select(ShoppingPurchase).where(
            ShoppingPurchase.id == purchase_id,
            ShoppingPurchase.created_by_user_id == user.id,
            ShoppingPurchase.family_budget_id == user.family_budget_id,
        )
    )
    if purchase is None:
        raise HTTPException(status_code=404)
    await _expire_if_due(session, purchase)
    return purchase


async def find_open_purchase(
    session: AsyncSession, user_id: uuid.UUID
) -> ShoppingPurchase | None:
    """The bot's lookup: the user's open purchase, or None (expired rows are closed)."""
    purchase = await session.scalar(
        select(ShoppingPurchase).where(
            ShoppingPurchase.created_by_user_id == user_id,
            ShoppingPurchase.status.in_(OPEN_STATUSES),
        )
    )
    if purchase is None:
        return None
    if await _expire_if_due(session, purchase):
        return None
    return purchase


async def mark_unrecognized(session: AsyncSession, purchase_id: uuid.UUID) -> None:
    """awaiting/unrecognized -> unrecognized; the manual screen gets a fresh 30 min."""
    purchase = await session.scalar(
        select(ShoppingPurchase)
        .where(
            ShoppingPurchase.id == purchase_id,
            ShoppingPurchase.status.in_(OPEN_STATUSES),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if purchase is None:
        return
    purchase.status = "unrecognized"
    purchase.expires_at = datetime.now(UTC) + PENDING_TTL
    await session.commit()


async def complete_pending_purchase(
    session: AsyncSession,
    user: User,
    purchase_id: uuid.UUID,
    *,
    amount: int,
    method: str,
) -> tuple[PurchaseResult, bool]:
    """Complete an open purchase with one sum (bot photo/voice/text or manual).

    Same algorithm as the manual path (family lock -> row FOR UPDATE -> write-off ->
    row completed, one commit). A completed row is an idempotent replay: stored
    result, nothing created. cancelled/expired -> 410 purchase_closed.
    """
    await lock_family_budget(session, user.family_budget_id)
    purchase = await session.scalar(
        select(ShoppingPurchase)
        .where(
            ShoppingPurchase.id == purchase_id,
            ShoppingPurchase.created_by_user_id == user.id,
            ShoppingPurchase.family_budget_id == user.family_budget_id,
        )
        .with_for_update()
        # the bot may hold a stale copy of this row (expire_on_commit=False): re-read under the lock
        .execution_options(populate_existing=True)
    )
    if purchase is None:
        raise HTTPException(status_code=404)
    if purchase.status == "completed":
        return await build_purchase_result(session, purchase), False
    if not _is_open(purchase):
        raise HTTPException(status_code=410, detail=CODE_PURCHASE_CLOSED)
    if await _expire_if_due(session, purchase):
        raise HTTPException(status_code=410, detail=CODE_PURCHASE_CLOSED)

    ids = list(purchase.item_ids)
    transaction, wallet, names = await _write_off(session, user, ids, amount)
    purchase.status = "completed"
    purchase.method = method
    purchase.amount = amount
    purchase.bought_item_names = names
    purchase.transaction_id = transaction.id
    purchase.closed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(purchase)
    await check_goal_achievement(session, wallet.id)
    return await build_purchase_result(session, purchase), True


# --- background jobs and membership cascades ---------------------------------


async def expire_open_purchases(session: AsyncSession) -> int:
    """Minute sweeper: open rows past expires_at -> expired."""
    result = await session.execute(
        update(ShoppingPurchase)
        .where(
            ShoppingPurchase.status.in_(OPEN_STATUSES),
            ShoppingPurchase.expires_at < func.now(),
        )
        .values(status="expired", closed_at=func.now())
    )
    return int(result.rowcount or 0)


async def purge_closed_purchases(session: AsyncSession) -> int:
    """Daily retention: terminal rows older than 30 days after closed_at, in batches."""
    total = 0
    cutoff = datetime.now(UTC) - PURCHASE_RETENTION
    while True:
        ids = (
            await session.scalars(
                select(ShoppingPurchase.id)
                .where(ShoppingPurchase.closed_at < cutoff)
                .limit(PURGE_BATCH)
            )
        ).all()
        if not ids:
            return total
        await session.execute(delete(ShoppingPurchase).where(ShoppingPurchase.id.in_(ids)))
        total += len(ids)


async def cancel_open_purchase_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Member left/was removed/joined another family: drop their waiting purchase."""
    await session.execute(
        update(ShoppingPurchase)
        .where(
            ShoppingPurchase.created_by_user_id == user_id,
            ShoppingPurchase.status.in_(OPEN_STATUSES),
        )
        .values(status="cancelled", closed_at=func.now())
    )


async def clear_family_shopping_list(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> None:
    await session.execute(
        delete(ShoppingItem).where(ShoppingItem.family_budget_id == family_budget_id)
    )
