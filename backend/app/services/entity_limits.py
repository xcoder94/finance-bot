import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_budget import FamilyBudget

SHARED_WALLET_LIMIT = 10
PERSONAL_WALLET_LIMIT = 5
PARENT_CATEGORY_LIMIT = 8
SUBCATEGORY_LIMIT = 8
MEMBER_LIMIT = 4
ENTITY_NAME_MAX = 30

LIMIT_SHARED_WALLETS = (
    "Больше 10 общих кошельков создать нельзя. Удалите ненужный — место освободится."
)
LIMIT_PERSONAL_WALLETS = (
    "Больше 5 личных кошельков создать нельзя. Удалите ненужный — место освободится."
)
LIMIT_EXPENSE_PARENTS = (
    "Больше 8 категорий расходов создать нельзя. Удалите ненужную — место освободится."
)
LIMIT_INCOME_CATEGORIES = (
    "Больше 8 категорий доходов создать нельзя. Удалите ненужную — место освободится."
)
LIMIT_MEMBERS = "В семейном бюджете уже 4 участника — это предел."


def limit_subcategories(parent_name: str) -> str:
    return (
        f"В категории «{parent_name}» уже 8 подкатегорий — это предел. "
        "Удалите ненужную, чтобы добавить новую."
    )


async def lock_family_budget(session: AsyncSession, budget_id: uuid.UUID) -> None:
    """Serialise concurrent cap checks (members, wallets, categories) against
    one family budget.

    Every cap in this app is enforced by "count rows, then insert" inside a
    single DB transaction, with nothing stopping two concurrent transactions
    from both counting the same value and both inserting. This takes a real
    row-level write lock on the parent ``FamilyBudget`` row before the count,
    so a second concurrent transaction touching the same budget blocks until
    the first commits (or rolls back) and re-reads a fresh, correct count.

    Implemented as a no-op ``UPDATE`` (not ``SELECT ... FOR UPDATE``) on
    purpose: SQLite silently drops ``FOR UPDATE`` entirely (no lock is taken),
    which would make this function a no-op under the sqlite test suite while
    still working on Postgres in production — exactly the kind of test that
    "passes for the wrong reason". A real ``UPDATE`` takes a write lock that
    both Postgres and SQLite honour, so the same code path is exercised, and
    is provably effective, on both.
    """
    await session.execute(
        update(FamilyBudget)
        .where(FamilyBudget.id == budget_id)
        .values(daily_model_calls=FamilyBudget.daily_model_calls)
    )


def normalize_entity_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ValueError("name must not be empty")
    if len(normalized) > ENTITY_NAME_MAX:
        raise ValueError(f"name must be at most {ENTITY_NAME_MAX} characters")
    return normalized
