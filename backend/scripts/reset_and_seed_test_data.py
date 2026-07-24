"""
One-off local dev script: wipes the entire database except one specified
Owner (by telegram_id), adds 5 extra test-only expense parent categories
(to trigger the >8 "Прочее" overflow case for Task 12 Part 2 testing),
and generates realistic income/expense test transactions for
2026-07-01 .. 2026-07-21.

Run from backend/: python -m scripts.reset_and_seed_test_data

DESTRUCTIVE. Only run against your local dev database.
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db import async_session_factory
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet

# --- Config -----------------------------------------------------------

KEEP_TELEGRAM_ID = 777130888  # the one Owner to preserve

EXTRA_EXPENSE_CATEGORIES: dict[str, list[str]] = {
    "Здоровье": ["Аптека", "Врач"],
    "Одежда": ["Обувь", "Аксессуары"],
    "Связь": ["Интернет", "Мобильная связь"],
    "Спорт": ["Абонемент", "Инвентарь"],
    "Питомцы": ["Корм", "Ветеринар"],
}

PERIOD_START = datetime(2026, 7, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 21, 23, 59, 59, tzinfo=timezone.utc)

TARGET_INCOME_UZS = 8_000_000
TARGET_EXPENSE_UZS = 6_000_000
TARGET_INCOME_USD = 400
TARGET_EXPENSE_USD = 300

INCOME_TXN_COUNT_UZS = 18
EXPENSE_TXN_COUNT_UZS = 65
INCOME_TXN_COUNT_USD = 5
EXPENSE_TXN_COUNT_USD = 10

INCOME_CATEGORY_WEIGHTS = {
    "Зарплата": 0.70,
    "Подработка": 0.20,
    "Подарки": 0.07,
    "Прочее": 0.03,
}

# --- Helpers ------------------------------------------------------------

def random_date_in_period() -> datetime:
    span_seconds = int((PERIOD_END - PERIOD_START).total_seconds())
    offset = random.randint(0, span_seconds)
    return PERIOD_START + timedelta(seconds=offset)


def split_amount(total: int, count: int, min_amount: int) -> list[int]:
    """Split `total` into `count` positive integer parts, roughly randomly,
    each at least min_amount, summing exactly to total."""
    if count * min_amount > total:
        raise ValueError("total too small for count * min_amount")
    weights = [random.random() + 0.2 for _ in range(count)]
    weight_sum = sum(weights)
    remaining = total - count * min_amount
    parts = [min_amount + int(remaining * w / weight_sum) for w in weights]
    diff = total - sum(parts)
    parts[-1] += diff  # fix rounding remainder
    return parts


def weighted_choice(weights: dict[str, float]):
    names = list(weights.keys())
    probs = list(weights.values())
    return random.choices(names, weights=probs, k=1)[0]


# --- Main -----------------------------------------------------------

async def main() -> None:
    async with async_session_factory() as session:
        target_user = await session.scalar(
            select(User).where(User.telegram_id == KEEP_TELEGRAM_ID, User.is_deleted.is_(False))
        )
        if target_user is None:
            print(f"[ABORT] No active user with telegram_id={KEEP_TELEGRAM_ID} found.")
            return

        keep_budget_id: uuid.UUID = target_user.family_budget_id
        print(f"Keeping user {target_user.id} (telegram_id={KEEP_TELEGRAM_ID}), "
              f"family_budget_id={keep_budget_id}")

        confirm = input(
            "This will DELETE every family_budget/user/wallet/category/transaction "
            f"except family_budget_id={keep_budget_id}. Type 'yes' to continue: "
        )
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return

        # Delete everything outside the kept family budget.
        await session.execute(
            delete(Transaction).where(Transaction.family_budget_id != keep_budget_id)
        )
        await session.execute(
            delete(Wallet).where(Wallet.family_budget_id != keep_budget_id)
        )
        await session.execute(
            delete(IncomeCategory).where(IncomeCategory.family_budget_id != keep_budget_id)
        )
        await session.execute(
            delete(ExpenseCategory).where(ExpenseCategory.family_budget_id != keep_budget_id)
        )
        await session.execute(
            delete(User).where(User.family_budget_id != keep_budget_id)
        )
        await session.execute(
            delete(FamilyBudget).where(FamilyBudget.id != keep_budget_id)
        )
        # Also clear any pre-existing transactions in the kept budget,
        # start fresh for this test dataset.
        await session.execute(
            delete(Transaction).where(Transaction.family_budget_id == keep_budget_id)
        )
        await session.commit()

        print("Wipe complete.")

        # --- Add 5 extra expense parent categories + subcategories ---
        for parent_name, sub_names in EXTRA_EXPENSE_CATEGORIES.items():
            parent = ExpenseCategory(
                family_budget_id=keep_budget_id,
                name=parent_name,
                parent_id=None,
            )
            session.add(parent)
            await session.flush()
            for sub_name in sub_names:
                session.add(
                    ExpenseCategory(
                        family_budget_id=keep_budget_id,
                        name=sub_name,
                        parent_id=parent.id,
                    )
                )
        await session.commit()
        print("Added 5 extra expense parent categories (10 total now).")

        # --- Load reference data ---
        wallets = (
            await session.scalars(
                select(Wallet).where(
                    Wallet.family_budget_id == keep_budget_id, Wallet.is_deleted.is_(False)
                )
            )
        ).all()
        wallets_uzs = [w for w in wallets if w.currency == "UZS"]
        wallets_usd = [w for w in wallets if w.currency == "USD"]

        income_categories = (
            await session.scalars(
                select(IncomeCategory).where(
                    IncomeCategory.family_budget_id == keep_budget_id,
                    IncomeCategory.is_deleted.is_(False),
                )
            )
        ).all()
        income_by_name = {c.name: c for c in income_categories}

        expense_subcategories = (
            await session.scalars(
                select(ExpenseCategory).where(
                    ExpenseCategory.family_budget_id == keep_budget_id,
                    ExpenseCategory.parent_id.is_not(None),
                    ExpenseCategory.is_deleted.is_(False),
                )
            )
        ).all()

        if not wallets_uzs or not wallets_usd:
            print("[ABORT] Expected both UZS and USD wallets, found:", 
                  len(wallets_uzs), "UZS /", len(wallets_usd), "USD")
            return
        if not expense_subcategories:
            print("[ABORT] No expense subcategories found.")
            return

        # --- Generate transactions ---
        # Income UZS
        amounts = split_amount(TARGET_INCOME_UZS, INCOME_TXN_COUNT_UZS, min_amount=10_000)
        for amount in amounts:
            cat_name = weighted_choice(INCOME_CATEGORY_WEIGHTS)
            session.add(Transaction(
                family_budget_id=keep_budget_id,
                type="income",
                wallet_id=random.choice(wallets_uzs).id,
                amount=amount,
                income_category_id=income_by_name[cat_name].id,
                created_by_user_id=target_user.id,
                transaction_date=random_date_in_period(),
            ))

        # Income USD
        amounts = split_amount(TARGET_INCOME_USD, INCOME_TXN_COUNT_USD, min_amount=10)
        for amount in amounts:
            cat_name = weighted_choice(INCOME_CATEGORY_WEIGHTS)
            session.add(Transaction(
                family_budget_id=keep_budget_id,
                type="income",
                wallet_id=random.choice(wallets_usd).id,
                amount=amount,
                income_category_id=income_by_name[cat_name].id,
                created_by_user_id=target_user.id,
                transaction_date=random_date_in_period(),
            ))

        # Expense UZS
        amounts = split_amount(TARGET_EXPENSE_UZS, EXPENSE_TXN_COUNT_UZS, min_amount=3_000)
        for amount in amounts:
            subcat = random.choice(expense_subcategories)
            session.add(Transaction(
                family_budget_id=keep_budget_id,
                type="expense",
                wallet_id=random.choice(wallets_uzs).id,
                amount=amount,
                expense_category_id=subcat.id,
                created_by_user_id=target_user.id,
                transaction_date=random_date_in_period(),
            ))

        # Expense USD
        amounts = split_amount(TARGET_EXPENSE_USD, EXPENSE_TXN_COUNT_USD, min_amount=5)
        for amount in amounts:
            subcat = random.choice(expense_subcategories)
            session.add(Transaction(
                family_budget_id=keep_budget_id,
                type="expense",
                wallet_id=random.choice(wallets_usd).id,
                amount=amount,
                expense_category_id=subcat.id,
                created_by_user_id=target_user.id,
                transaction_date=random_date_in_period(),
            ))
        await session.commit()

        total_txns = (
            INCOME_TXN_COUNT_UZS + INCOME_TXN_COUNT_USD
            + EXPENSE_TXN_COUNT_UZS + EXPENSE_TXN_COUNT_USD
        )
        print(f"Created {total_txns} transactions "
              f"(income: {TARGET_INCOME_UZS} UZS + {TARGET_INCOME_USD} USD, "
              f"expense: {TARGET_EXPENSE_UZS} UZS + {TARGET_EXPENSE_USD} USD) "
              f"across {PERIOD_START.date()} .. {PERIOD_END.date()}.")
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
