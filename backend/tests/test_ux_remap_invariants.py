"""ux-r10: category remap on join / leave follows invariants I1-I7 (work/review/ux-remap.md).

Property-style: every combination of direction x category set x source state x target state x kind
is moved, then the same invariants are checked on the budgets the person (and the family) sees.
"""

from __future__ import annotations

import datetime
import itertools
from collections import Counter
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.services.budget_seed import (
    LEGACY_SEED_EXPENSE_CATEGORIES,
    LEGACY_SEED_INCOME_CATEGORIES,
    SEED_EXPENSE_CATEGORIES,
    SEED_INCOME_CATEGORIES,
    budget_uses_legacy_set,
    copy_seed_categories_only,
)
from app.services.membership_lifecycle import (
    convert_join_with_own_budget,
    detach_member_to_own_budget,
)
from app.services.transaction_category_remap import _candidate_keys
from app.services.wallets_categories import get_active_expense_category
from tests.test_personal_wallet_privacy import make_wallet
from tests.test_quick_entry_flow import create_user, pytestmark, rollback_session  # noqa: F401


def _keys(income, expense):
    keys = {k for _n, k in income}
    for pk, subs in expense.values():
        keys.add(pk)
        keys |= {k for _n, k in subs}
    return keys


LEGACY = _keys(LEGACY_SEED_INCOME_CATEGORIES, LEGACY_SEED_EXPENSE_CATEGORIES)
NEW = _keys(SEED_INCOME_CATEGORIES, SEED_EXPENSE_CATEGORIES)
NOW = datetime.datetime.now(datetime.UTC)


# ---------------------------------------------------------------- helpers


async def _cats(session, budget_id):
    exp = list(
        await session.scalars(
            select(ExpenseCategory).where(ExpenseCategory.family_budget_id == budget_id)
        )
    )
    inc = list(
        await session.scalars(
            select(IncomeCategory).where(IncomeCategory.family_budget_id == budget_id)
        )
    )
    return exp, inc


async def _snap(session, budget_id):
    exp, inc = await _cats(session, budget_id)
    out = {
        c.id: ("e", c.translation_key, c.name, c.color_index, c.is_deleted, c.parent_id)
        for c in exp
    }
    out.update(
        {c.id: ("i", c.translation_key, c.name, c.color_index, c.is_deleted, None) for c in inc}
    )
    return out


async def _shape(session, budget_id):
    """Budget shape without ids: how it looks to a person."""
    exp, inc = await _cats(session, budget_id)
    by_id = {c.id: c for c in exp}
    rows = [
        ("e", c.translation_key, c.name, c.is_deleted,
         by_id[c.parent_id].name if c.parent_id else None)
        for c in exp
    ] + [("i", c.translation_key, c.name, c.is_deleted, None) for c in inc]
    return sorted(rows, key=repr)


async def assert_no_duplicate_keys(session, budget_id):
    """I1: one row per translation_key per budget, deleted rows counted."""
    exp, inc = await _cats(session, budget_id)
    for group in (exp, inc):
        counts = Counter(c.translation_key for c in group if c.translation_key)
        dup = {k: n for k, n in counts.items() if n > 1}
        assert not dup, dup


async def assert_no_live_orphans(session, budget_id):
    """I2: no live sub-category under a deleted parent."""
    exp, _inc = await _cats(session, budget_id)
    by_id = {c.id: c for c in exp}
    bad = [c.name for c in exp if not c.is_deleted and c.parent_id and by_id[c.parent_id].is_deleted]
    assert not bad, bad


async def _by_key(session, budget_id, key, model=ExpenseCategory):
    return await session.scalar(
        select(model).where(model.family_budget_id == budget_id, model.translation_key == key)
    )


def _custom(budget_id, name, parent=None, deleted=False):
    return ExpenseCategory(
        family_budget_id=budget_id,
        name=name,
        parent_id=parent.id if parent is not None else None,
        color_index=2,
        is_deleted=deleted,
        deleted_at=NOW if deleted else None,
    )


async def _cascade_delete(session, row):
    row.is_deleted = True
    row.deleted_at = NOW
    for ch in await session.scalars(
        select(ExpenseCategory).where(ExpenseCategory.parent_id == row.id)
    ):
        ch.is_deleted = True
        ch.deleted_at = NOW
    await session.flush()


async def _wallet(session, budget, user):
    w = make_wallet(budget, name="Мой", is_personal=True, owner_user_id=user.id)
    session.add(w)
    await session.flush()
    user.default_wallet_id = w.id
    return w


def _txn(budget, wallet, user, **kw):
    return Transaction(
        family_budget_id=budget.id,
        wallet_id=wallet.id,
        amount=1000,
        created_by_user_id=user.id,
        transaction_date=NOW,
        **kw,
    )


async def _family(session, tg, legacy):
    owner, budget = await create_user(session, telegram_id=tg)
    await copy_seed_categories_only(session, budget.id, legacy=legacy)
    return owner, budget


async def _pick_family_row(session, budget_id, key, model):
    rows = (await _cats(session, budget_id))[0 if model is ExpenseCategory else 1]
    for k in _candidate_keys(key):
        hit = next((c for c in rows if c.translation_key == k), None)
        if hit is not None:
            return hit
    return None


# ---------------------------------------------------------------- join: the case table

SRC_KEY = {
    "same": lambda ul: "groceries",
    "successor": lambda ul: "taxi" if ul else "taxi_transit",
    "fallback": lambda ul: "family_help",
    "income_same": lambda ul: "salary",
    "income_successor": lambda ul: "side_job" if ul else "business_side_job",
}


def _join_cases():
    for ul, fl, kind, src_deleted, state in itertools.product(
        [True, False],
        [True, False],
        ["same", "successor", "fallback", "custom", "custom_same_name",
         "income_same", "income_successor"],
        [False, True],
        ["live", "deleted_row", "deleted_parent"],
    ):
        if kind == "fallback" and ul:
            continue  # family_help exists only in the new set
        if kind == "custom" and state == "deleted_row":
            continue  # no counterpart row to delete
        if kind.startswith("income") and state == "deleted_parent":
            continue  # income has no parents
        yield pytest.param(
            ul, fl, kind, src_deleted, state,
            id=f"user_{'old' if ul else 'new'}-fam_{'old' if fl else 'new'}-{kind}"
               f"-src_{'del' if src_deleted else 'live'}-{state}",
        )


@pytest.mark.parametrize(("ul", "fl", "kind", "src_deleted", "state"), list(_join_cases()))
async def test_join_moves_operation_by_identity_and_keeps_family_intact(
    ul, fl, kind, src_deleted, state
) -> None:
    async with rollback_session() as session:
        # --- the joiner's solo budget with one operation
        user, solo = await create_user(session, telegram_id=9_810_001)
        await copy_seed_categories_only(session, solo.id, legacy=ul)
        wallet = await _wallet(session, solo, user)
        income = kind.startswith("income")
        model = IncomeCategory if income else ExpenseCategory
        if kind.startswith("custom"):
            src = _custom(solo.id, "Самокат", await _by_key(session, solo.id, "transport"))
            session.add(src)
        else:
            src = await _by_key(session, solo.id, SRC_KEY[kind](ul), model)
        src.is_deleted = src_deleted
        src.deleted_at = NOW if src_deleted else None
        await session.flush()
        txn = _txn(solo, wallet, user, type="income" if income else "expense")
        if income:
            txn.income_category_id = src.id
        else:
            txn.expense_category_id = src.id
        session.add(txn)

        # --- the family and its state
        _owner, fam = await _family(session, 9_810_002, fl)
        target = None
        transport = await _by_key(session, fam.id, "transport")
        if kind == "custom_same_name":
            target = _custom(fam.id, "Самокат", transport)
            session.add(target)
            await session.flush()
        elif kind != "custom":
            target = await _pick_family_row(session, fam.id, src.translation_key, model)
            if target is None:  # family_help in an old family: the nearest parent
                target = await _by_key(session, fam.id, "events_celebrations")
        if state == "deleted_row":
            if getattr(target, "parent_id", None) is None and not income:
                await _cascade_delete(session, target)
            else:
                target.is_deleted, target.deleted_at = True, NOW
        elif state == "deleted_parent":
            root = target if target is None or target.parent_id is None else await session.get(
                ExpenseCategory, target.parent_id
            )
            await _cascade_delete(session, root or transport)
        await session.flush()

        before = await _snap(session, fam.id)
        set_before = await budget_uses_legacy_set(session, fam.id)

        await convert_join_with_own_budget(session, user=user, target=fam)
        await session.flush()
        await session.refresh(txn)

        # --- invariants I1-I5
        await assert_no_duplicate_keys(session, fam.id)
        await assert_no_live_orphans(session, fam.id)
        after = await _snap(session, fam.id)
        assert {i: v for i, v in after.items() if i in before} == before  # I3: nothing changed
        added = [v for i, v in after.items() if i not in before]
        assert all(v[1] is None for v in added), added  # I3: only customs are added
        assert await budget_uses_legacy_set(session, fam.id) is set_before  # I4
        cat_id = txn.income_category_id if income else txn.expense_category_id
        assert cat_id is not None
        reached = await session.get(model, cat_id)
        assert reached.family_budget_id == fam.id
        assert txn.amount == 1000
        if target is not None:  # I5: the identity mapping, whatever its state
            assert reached.id == target.id
        else:  # an own custom category of the joiner is added under the family's parent
            assert reached.translation_key is None and reached.name == "Самокат"
            assert reached.parent_id == transport.id
            assert reached.is_deleted is (src_deleted or transport.is_deleted)


# ---------------------------------------------------------------- join: every operation at once


async def _solo_all(session, tg, legacy, deleted_keys):
    user, budget = await create_user(session, telegram_id=tg)
    await copy_seed_categories_only(session, budget.id, legacy=legacy)
    wallet = await _wallet(session, budget, user)
    exp, inc = await _cats(session, budget.id)
    transport = next(c for c in exp if c.translation_key == "transport")
    custom = _custom(budget.id, "Бассейн", transport)
    dead_custom = _custom(budget.id, "Удалённая", transport, deleted=True)
    session.add_all([custom, dead_custom])
    await session.flush()
    n = 0
    for c in exp + [custom, dead_custom]:
        session.add(_txn(budget, wallet, user, type="expense", expense_category_id=c.id))
        n += 1
    for c in inc:
        session.add(_txn(budget, wallet, user, type="income", income_category_id=c.id))
        n += 1
    for c in exp + inc:
        if c.translation_key in deleted_keys:
            c.is_deleted, c.deleted_at = True, NOW
    await session.flush()
    return user, budget, n


FAMILY_STATES = {
    "none": [],
    "sub": [("taxi_transit", False), ("taxi", False), ("salary", False)],
    "parent_cascade": [("food", True), ("health", True)],
    "legacy_parents": [("transport", True), ("home", True), ("side_job", False)],
    "many": [("cafes_delivery", False), ("groceries", False), ("children", True),
             ("business_side_job", False), ("doctors", False)],
}
SOLO_DELETED = {
    "none": set(),
    "drugstore": {"drugstore", "pharmacy"},
    "sub_and_income": {"taxi", "taxi_transit", "gifts", "groceries"},
}


@pytest.mark.parametrize("solo_del", list(SOLO_DELETED))
@pytest.mark.parametrize("fam_state", list(FAMILY_STATES))
@pytest.mark.parametrize("fl", [True, False])
@pytest.mark.parametrize("ul", [True, False])
async def test_join_with_all_operations_never_duplicates_or_orphans(
    ul, fl, fam_state, solo_del
) -> None:
    async with rollback_session() as session:
        user, solo, n_ops = await _solo_all(session, 9_810_011, ul, SOLO_DELETED[solo_del])
        _owner, fam = await _family(session, 9_810_012, fl)
        for key, cascade in FAMILY_STATES[fam_state]:
            for model in (ExpenseCategory, IncomeCategory):
                row = await _by_key(session, fam.id, key, model)
                if row is None:
                    continue
                if cascade:
                    await _cascade_delete(session, row)
                else:
                    row.is_deleted, row.deleted_at = True, NOW
        await session.flush()
        before = await _snap(session, fam.id)
        set_before = await budget_uses_legacy_set(session, fam.id)
        await convert_join_with_own_budget(session, user=user, target=fam)
        await session.flush()

        await assert_no_duplicate_keys(session, fam.id)
        await assert_no_live_orphans(session, fam.id)
        after = await _snap(session, fam.id)
        assert {i: v for i, v in after.items() if i in before} == before
        assert all(v[1] is None for i, v in after.items() if i not in before)
        assert await budget_uses_legacy_set(session, fam.id) is set_before
        txns = list(
            await session.scalars(select(Transaction).where(Transaction.family_budget_id == fam.id))
        )
        assert len(txns) == n_ops and sum(t.amount for t in txns) == 1000 * n_ops
        for t in txns:
            assert (t.expense_category_id or t.income_category_id) is not None
            cat = await session.get(
                ExpenseCategory if t.expense_category_id else IncomeCategory,
                t.expense_category_id or t.income_category_id,
            )
            assert cat.family_budget_id == fam.id


# ---------------------------------------------------------------- leave


LEAVE_STATES = {
    "none": [],
    "sub_and_parent": [("taxi_transit", False), ("taxi", False), ("food", True)],
    "income_and_many": [("salary", False), ("doctors", False), ("pharmacy", False),
                        ("transport", True), ("home", True)],
}


@pytest.mark.parametrize("state", list(LEAVE_STATES))
@pytest.mark.parametrize("fl", [True, False])
async def test_leave_lands_every_operation_in_a_live_row_of_a_clean_budget(fl, state) -> None:
    async with rollback_session() as session:
        _owner, fam = await _family(session, 9_810_021, fl)
        member, _ = await create_user(session, telegram_id=9_810_022, role="member", budget=fam)
        wallet = await _wallet(session, fam, member)
        food = await _by_key(session, fam.id, "food")
        transport = await _by_key(session, fam.id, "transport")
        customs = [
            _custom(fam.id, "Бассейн", transport),
            _custom(fam.id, "Самокат", transport),
            _custom(fam.id, "Старая", food, deleted=True),
            _custom(fam.id, "Папка", None, deleted=True),
        ]
        session.add_all(customs)
        await session.flush()
        customs.append(_custom(fam.id, "Дитя папки", customs[3], deleted=True))
        session.add(customs[-1])
        await session.flush()
        for key, cascade in LEAVE_STATES[state]:
            for model in (ExpenseCategory, IncomeCategory):
                row = await _by_key(session, fam.id, key, model)
                if row is None:
                    continue
                if cascade:
                    await _cascade_delete(session, row)
                else:
                    row.is_deleted, row.deleted_at = True, NOW
        await session.flush()

        exp, inc = await _cats(session, fam.id)
        n_ops = 0
        for c in exp:
            session.add(_txn(fam, wallet, member, type="expense", expense_category_id=c.id))
            n_ops += 1
        for c in inc:
            session.add(_txn(fam, wallet, member, type="income", income_category_id=c.id))
            n_ops += 1
        await session.flush()
        fam_before = await _snap(session, fam.id)
        fresh_legacy = await budget_uses_legacy_set(session, fam.id)

        new_budget = await detach_member_to_own_budget(
            session, departing_user=member, old_budget=fam, reason="left", bot=AsyncMock()
        )
        await session.flush()

        await assert_no_duplicate_keys(session, new_budget.id)
        await assert_no_live_orphans(session, new_budget.id)
        assert await _snap(session, fam.id) == fam_before  # the family is untouched
        fresh_keys = LEGACY if fresh_legacy else NEW
        txns = list(
            await session.scalars(
                select(Transaction).where(Transaction.family_budget_id == new_budget.id)
            )
        )
        assert len(txns) == n_ops and sum(t.amount for t in txns) == 1000 * n_ops
        old_of = {}
        for t in txns:
            is_exp = t.expense_category_id is not None
            cat_id = t.expense_category_id or t.income_category_id
            assert cat_id is not None
            cat = await session.get(ExpenseCategory if is_exp else IncomeCategory, cat_id)
            assert cat.family_budget_id == new_budget.id
            assert cat.is_deleted is False, cat.name  # the leaver sees every operation's category
            if is_exp:  # what PATCH / the history filter do
                assert await get_active_expense_category(session, cat.id, new_budget.id)
            old_of[cat.id] = cat
        # one result per old category: seed keys map to the same / successor key, customs by name
        sources = {c.id: c for c in exp}
        for old in list(sources.values()):
            if old.translation_key is None:
                hit = [c for c in old_of.values() if c.translation_key is None
                       and c.name == old.name]
                assert hit, old.name
            else:
                want = next((k for k in _candidate_keys(old.translation_key) if k in fresh_keys),
                            None)
                if want is None:  # family_help leaving to an old-set budget: its parent
                    want = "events_celebrations"
                assert any(c.translation_key == want for c in old_of.values()), old.translation_key


async def test_leave_filter_by_category_returns_the_leavers_operations() -> None:
    """r8 bug 2: family deleted a seed sub; after leaving, the category of the operation is
    unique in the new budget, active, and the history filter by it returns the operation."""
    async with rollback_session() as session:
        _owner, fam = await _family(session, 9_810_031, False)
        member, _ = await create_user(session, telegram_id=9_810_032, role="member", budget=fam)
        wallet = await _wallet(session, fam, member)
        cafes = await _by_key(session, fam.id, "cafes_delivery")
        cafes.is_deleted, cafes.deleted_at = True, NOW
        txn = _txn(fam, wallet, member, type="expense", expense_category_id=cafes.id)
        session.add(txn)
        await session.flush()
        new_budget = await detach_member_to_own_budget(
            session, departing_user=member, old_budget=fam, reason="left", bot=AsyncMock()
        )
        await session.flush()
        await session.refresh(txn)
        rows = list(
            await session.scalars(
                select(ExpenseCategory).where(
                    ExpenseCategory.family_budget_id == new_budget.id,
                    ExpenseCategory.translation_key == "cafes_delivery",
                )
            )
        )
        assert len(rows) == 1 and rows[0].is_deleted is False
        assert txn.expense_category_id == rows[0].id
        assert await get_active_expense_category(session, rows[0].id, new_budget.id)
        n = await session.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.family_budget_id == new_budget.id,
                Transaction.expense_category_id == rows[0].id,
            )
        )
        assert n == 1


# ---------------------------------------------------------------- I7: cycles


async def test_three_join_leave_cycles_do_not_grow_family_or_leaver_budget() -> None:
    async with rollback_session() as session:
        _owner, fam = await _family(session, 9_810_041, False)
        for key, cascade in [("taxi_transit", False), ("health", True), ("business_side_job", False)]:
            for model in (ExpenseCategory, IncomeCategory):
                row = await _by_key(session, fam.id, key, model)
                if row is not None and cascade:
                    await _cascade_delete(session, row)
                elif row is not None:
                    row.is_deleted, row.deleted_at = True, NOW
        transport = await _by_key(session, fam.id, "transport")
        session.add(_custom(fam.id, "Семейная", transport, deleted=True))
        await session.flush()
        user, _solo, n_ops = await _solo_all(session, 9_810_042, True, {"taxi", "pharmacy"})

        family_after_join = None
        leaver_shape = None
        for cycle in range(3):
            await convert_join_with_own_budget(session, user=user, target=fam)
            await session.flush()
            joined = await _snap(session, fam.id)
            if family_after_join is None:
                family_after_join = joined
            assert joined == family_after_join, f"family changed on join {cycle}"
            await assert_no_duplicate_keys(session, fam.id)
            await assert_no_live_orphans(session, fam.id)
            nb = await detach_member_to_own_budget(
                session, departing_user=user, old_budget=fam, reason="left", bot=AsyncMock()
            )
            await session.flush()
            assert await _snap(session, fam.id) == family_after_join, f"family changed on leave {cycle}"
            await assert_no_duplicate_keys(session, nb.id)
            await assert_no_live_orphans(session, nb.id)
            shape = await _shape(session, nb.id)
            if leaver_shape is None:
                leaver_shape = shape
            assert shape == leaver_shape, f"leaver budget changed on cycle {cycle}"
            n = await session.scalar(
                select(func.count()).select_from(Transaction).where(
                    Transaction.family_budget_id == nb.id
                )
            )
            assert n == n_ops
            user.role = "owner"
