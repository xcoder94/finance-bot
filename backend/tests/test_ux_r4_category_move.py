"""ux-r4: operations that move to another/new budget never lose their category."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.services.budget_seed import (
    LEGACY_SEED_EXPENSE_CATEGORIES,
    LEGACY_SEED_INCOME_CATEGORIES,
    copy_seed_categories_only,
)
from app.services.membership_lifecycle import (
    convert_join_with_own_budget,
    detach_member_to_own_budget,
)
from app.models.family_budget import FamilyBudget
from tests.test_personal_wallet_privacy import make_wallet
from tests.test_quick_entry_flow import create_user, pytestmark, rollback_session  # noqa: F401

EXPENSE_KEYS = [
    (sub_key, parent_key)
    for parent_key, subs in LEGACY_SEED_EXPENSE_CATEGORIES.values()
    for _n, sub_key in subs
]
INCOME_KEYS = [key for _n, key in LEGACY_SEED_INCOME_CATEGORIES]


async def _old_family(session, tg: int, *, custom: bool = True):
    owner, budget = await create_user(session, telegram_id=tg)
    member, _ = await create_user(session, telegram_id=tg + 1, role="member", budget=budget)
    await copy_seed_categories_only(session, budget.id, legacy=True)
    wallet = make_wallet(budget, name="Личный", is_personal=True, owner_user_id=member.id)
    session.add(wallet)
    await session.flush()
    member.default_wallet_id = wallet.id
    exp = {
        c.translation_key: c
        for c in await session.scalars(
            select(ExpenseCategory).where(ExpenseCategory.family_budget_id == budget.id)
        )
    }
    inc = {
        c.translation_key: c
        for c in await session.scalars(
            select(IncomeCategory).where(IncomeCategory.family_budget_id == budget.id)
        )
    }
    exp["taxi"].name = "Мой Яндекс"  # user rename
    extra = {}
    if custom:
        parent = exp["transport"]
        extra["custom_sub"] = ExpenseCategory(
            family_budget_id=budget.id, name="Самокат", parent_id=parent.id, color_index=3
        )
        extra["custom_parent"] = ExpenseCategory(
            family_budget_id=budget.id, name="Хобби", color_index=5
        )
        extra["custom_income"] = IncomeCategory(
            family_budget_id=budget.id, name="Кэшбэк", color_index=2
        )
        session.add_all(extra.values())
        await session.flush()
    txns: dict[str, Transaction] = {}

    def add(label, **kw):
        t = Transaction(
            family_budget_id=budget.id,
            wallet_id=wallet.id,
            amount=1000,
            created_by_user_id=member.id,
            transaction_date=datetime.datetime.now(datetime.UTC),
            **kw,
        )
        session.add(t)
        txns[label] = t

    for key, cat in exp.items():
        add("e:" + key, type="expense", expense_category_id=cat.id)
    for key, cat in inc.items():
        add("i:" + key, type="income", income_category_id=cat.id)
    for key, cat in extra.items():
        if key == "custom_income":
            add(key, type="income", income_category_id=cat.id)
        else:
            add(key, type="expense", expense_category_id=cat.id)
    await session.flush()
    return owner, member, budget, txns, exp, extra


def _assert_all_categorised(txns):
    for label, t in txns.items():
        if t.type == "income":
            assert t.income_category_id is not None, label
        else:
            assert t.expense_category_id is not None, label


@pytest.mark.parametrize("reason", ["left", "removed"])
async def test_detach_from_old_family_keeps_every_category(reason) -> None:
    async with rollback_session() as session:
        _owner, member, budget, txns, exp, extra = await _old_family(session, 9_700_010)
        new_budget = await detach_member_to_own_budget(
            session, departing_user=member, old_budget=budget, reason=reason, bot=AsyncMock()
        )
        await session.flush()
        for t in txns.values():
            await session.refresh(t)
        _assert_all_categorised(txns)
        # budget seeded with the SAME (old) set as the source budget
        keys = set(
            await session.scalars(
                select(ExpenseCategory.translation_key).where(
                    ExpenseCategory.family_budget_id == new_budget.id,
                    ExpenseCategory.translation_key.is_not(None),
                )
            )
        )
        assert {"taxi", "fuel", "cafes_restaurants", "pharmacy", "utilities"} <= keys
        by_id = {
            c.id: c
            for c in await session.scalars(
                select(ExpenseCategory).where(ExpenseCategory.family_budget_id == new_budget.id)
            )
        }
        for key in EXPENSE_KEYS:
            cat = by_id[txns["e:" + key[0]].expense_category_id]
            assert cat.translation_key == key[0]
            assert cat.family_budget_id == new_budget.id
        assert by_id[txns["e:taxi"].expense_category_id].name == "Мой Яндекс"
        custom = by_id[txns["custom_sub"].expense_category_id]
        assert custom.name == "Самокат"
        assert by_id[custom.parent_id].translation_key == "transport"
        assert by_id[txns["custom_parent"].expense_category_id].parent_id is None
        income = await session.get(IncomeCategory, txns["i:gifts"].income_category_id)
        assert income.family_budget_id == new_budget.id and income.name == "Подарки"
        kb = await session.get(IncomeCategory, txns["custom_income"].income_category_id)
        assert kb.name == "Кэшбэк" and kb.family_budget_id == new_budget.id


async def test_new_user_budget_still_gets_new_set_after_detach_of_new_family() -> None:
    from app.services.budget_seed import copy_seed_data

    async with rollback_session() as session:
        owner, budget = await create_user(session, telegram_id=9_700_030)
        member, _ = await create_user(session, telegram_id=9_700_031, role="member", budget=budget)
        await copy_seed_data(session, budget.id)
        new_budget = await detach_member_to_own_budget(
            session, departing_user=member, old_budget=budget, reason="left", bot=AsyncMock()
        )
        await session.flush()
        keys = set(
            await session.scalars(
                select(ExpenseCategory.translation_key).where(
                    ExpenseCategory.family_budget_id == new_budget.id
                )
            )
        )
        assert "taxi_transit" in keys and "taxi" not in keys


async def test_subcategory_whose_parent_is_missing_in_target_creates_parent() -> None:
    async with rollback_session() as session:
        _o, member, budget, txns, exp, _extra = await _old_family(session, 9_700_040, custom=False)
        # target: a new-set budget lacking the old parent "events_celebrations"
        target_owner, target = await create_user(session, telegram_id=9_700_050)
        await copy_seed_categories_only(session, target.id)
        await convert_join_with_own_budget(session, user=member, target=target)
        await session.flush()
        for t in txns.values():
            await session.refresh(t)
        _assert_all_categorised(txns)
        sub = await session.get(ExpenseCategory, txns["e:toi_celebrations"].expense_category_id)
        assert sub.family_budget_id == target.id
        parent = await session.get(ExpenseCategory, sub.parent_id)
        # target already had the new-set sub with this key under toi_gifts: reused, not duplicated
        assert parent.family_budget_id == target.id
        dentist = await session.get(ExpenseCategory, txns["e:dentistry"].expense_category_id)
        assert dentist.family_budget_id == target.id and dentist.parent_id is not None
        no_dup = list(
            await session.scalars(
                select(ExpenseCategory).where(
                    ExpenseCategory.family_budget_id == target.id,
                    ExpenseCategory.translation_key == "toi_celebrations",
                )
            )
        )
        assert len(no_dup) == 1 or all(c.parent_id is not None for c in no_dup)


async def test_orphan_subcategory_without_parent_row() -> None:
    from app.services.transaction_category_remap import remap_transaction_categories_to_budget

    async with rollback_session() as session:
        _o, member, budget, txns, exp, _e = await _old_family(session, 9_700_060, custom=False)
        _o2, target = await create_user(session, telegram_id=9_700_070)
        sub = exp["dentistry"]
        sub.parent_id = None  # subcategory with no parent
        await session.flush()
        await remap_transaction_categories_to_budget(session, [txns["e:dentistry"]], target.id)
        got = await session.get(ExpenseCategory, txns["e:dentistry"].expense_category_id)
        assert got.family_budget_id == target.id and got.name == "Стоматология"
