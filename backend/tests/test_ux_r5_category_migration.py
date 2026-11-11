"""ux-r5: operations moving between budgets use a key-successor table; no parallel seed sets."""

from __future__ import annotations

import datetime
from collections import Counter
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.parsing.prefilter import PrefilterCategory, try_prefilter
from app.services.budget_seed import (
    LEGACY_SEED_EXPENSE_CATEGORIES,
    LEGACY_SEED_INCOME_CATEGORIES,
    LEGACY_TO_NEW_KEY,
    NEW_TO_LEGACY_KEY,
    PARENT_FALLBACK,
    SEED_EXPENSE_CATEGORIES,
    SEED_INCOME_CATEGORIES,
    budget_uses_legacy_set,
    copy_seed_categories_only,
)
from app.services.membership_lifecycle import (
    convert_join_with_own_budget,
    detach_member_to_own_budget,
)
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


def test_every_legacy_only_key_has_a_new_successor() -> None:
    for key in LEGACY - NEW:
        assert LEGACY_TO_NEW_KEY[key] in NEW, key
    assert set(LEGACY_TO_NEW_KEY) == LEGACY - NEW


def test_every_new_only_key_has_a_legacy_counterpart_or_parent_fallback() -> None:
    for key in NEW - LEGACY:
        if key in PARENT_FALLBACK:
            assert key not in NEW_TO_LEGACY_KEY
        else:
            assert NEW_TO_LEGACY_KEY[key] in LEGACY, key


async def _family(session, tg, *, legacy, members=1):
    owner, budget = await create_user(session, telegram_id=tg)
    await copy_seed_categories_only(session, budget.id, legacy=legacy)
    return owner, budget


async def _solo_with_ops(session, tg, *, legacy):
    """A solo user with one personal-style operation per seed key (+ a deleted category op)."""
    user, budget = await create_user(session, telegram_id=tg)
    await copy_seed_categories_only(session, budget.id, legacy=legacy)
    wallet = make_wallet(budget, name="Мой", is_personal=True, owner_user_id=user.id)
    session.add(wallet)
    await session.flush()
    user.default_wallet_id = wallet.id
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
    exp[("taxi" if legacy else "taxi_transit")].name = "Яндекс Такси"  # user rename
    custom = ExpenseCategory(
        family_budget_id=budget.id, name="Бассейн", parent_id=exp["transport"].id, color_index=2
    )
    dead = ExpenseCategory(
        family_budget_id=budget.id,
        name="Удалённая",
        parent_id=exp["food"].id,
        color_index=2,
        is_deleted=True,
        deleted_at=datetime.datetime.now(datetime.UTC),
    )
    session.add_all([custom, dead])
    await session.flush()
    txns = {}

    def add(label, **kw):
        t = Transaction(
            family_budget_id=budget.id,
            wallet_id=wallet.id,
            amount=1000,
            created_by_user_id=user.id,
            transaction_date=datetime.datetime.now(datetime.UTC),
            **kw,
        )
        session.add(t)
        txns[label] = t

    for key, cat in exp.items():
        add("e:" + key, type="expense", expense_category_id=cat.id)
    for key, cat in inc.items():
        add("i:" + key, type="income", income_category_id=cat.id)
    add("custom", type="expense", expense_category_id=custom.id)
    add("dead", type="expense", expense_category_id=dead.id)
    await session.flush()
    return user, budget, txns


async def _live(session, budget_id):
    exp = list(
        await session.scalars(
            select(ExpenseCategory).where(
                ExpenseCategory.family_budget_id == budget_id,
                ExpenseCategory.is_deleted.is_(False),
            )
        )
    )
    inc = list(
        await session.scalars(
            select(IncomeCategory).where(
                IncomeCategory.family_budget_id == budget_id,
                IncomeCategory.is_deleted.is_(False),
            )
        )
    )
    return exp, inc


async def _assert_invariants(session, budget_id):
    # I1/I2 over ALL rows, deleted included: one row per key, no live row under a deleted parent
    all_exp = list(
        await session.scalars(
            select(ExpenseCategory).where(ExpenseCategory.family_budget_id == budget_id)
        )
    )
    all_inc = list(
        await session.scalars(
            select(IncomeCategory).where(IncomeCategory.family_budget_id == budget_id)
        )
    )
    for rows, label in ((all_exp, "expense"), (all_inc, "income")):
        counts = Counter(c.translation_key for c in rows if c.translation_key)
        assert all(n == 1 for n in counts.values()), (label, "duplicate key", counts)
    by_id = {c.id: c for c in all_exp}
    assert not [
        c.name for c in all_exp if not c.is_deleted and c.parent_id and by_id[c.parent_id].is_deleted
    ], "live child of a deleted parent"
    exp, inc = await _live(session, budget_id)
    keys = {c.translation_key for c in exp + inc if c.translation_key}
    assert not ((keys & (LEGACY - NEW)) and (keys & (NEW - LEGACY))), "mixed sets"
    pre = [PrefilterCategory(c.id, c.name, c.translation_key, c.parent_id) for c in exp]
    result = try_prefilter(
        "такси 20000", wallet_names=[], expense_categories=pre, income_categories=[]
    )
    taxi_keys = {"taxi", "taxi_transit"} & keys
    renamed = any(c.translation_key in taxi_keys and c.name not in ("Такси", "Такси и проезд")
                  for c in exp)
    if taxi_keys and not renamed:
        assert result.operation is not None, result.reason
        assert result.operation.category in ("Такси", "Такси и проезд")


async def _refresh(session, txns):
    for t in txns.values():
        await session.refresh(t)


async def test_old_user_joins_new_family_no_parallel_categories() -> None:
    async with rollback_session() as session:
        user, _b, txns = await _solo_with_ops(session, 9_800_010, legacy=True)
        _owner, target = await _family(session, 9_800_020, legacy=False)
        await convert_join_with_own_budget(session, user=user, target=target)
        await session.flush()
        await _refresh(session, txns)
        exp, inc = await _live(session, target.id)
        parents = [c for c in exp if c.parent_id is None]
        subs = [c for c in exp if c.parent_id is not None]
        # only the user's custom category was added; the seed set stays 7/17/4
        assert len(parents) == 7 and len(subs) == 17 + 1 and len(inc) == 4
        by_id = {c.id: c for c in exp}
        for old_key, new_key in [
            ("taxi", "taxi_transit"), ("public_transport", "taxi_transit"),
            ("fuel", "car"), ("dentistry", "doctors"), ("delivery", "cafes_delivery"),
            ("events_celebrations", "toi_gifts"), ("shopping_leisure", "personal_leisure"),
            ("subscriptions", "fun_subscriptions"), ("telecom_internet", "utilities_telecom"),
        ]:
            assert by_id[txns["e:" + old_key].expense_category_id].translation_key == new_key
        inc_by_id = {c.id: c for c in inc}
        assert inc_by_id[txns["i:gifts"].income_category_id].translation_key == "transfers_gifts"
        assert inc_by_id[txns["i:side_job"].income_category_id].translation_key == "business_side_job"
        # user's rename of a seed category is kept (the successor is not renamed by joining)
        custom = by_id[txns["custom"].expense_category_id]
        assert custom.name == "Бассейн"
        assert by_id[custom.parent_id].translation_key == "transport"
        await _assert_invariants(session, target.id)


async def test_new_user_joins_old_family_maps_to_legacy_set() -> None:
    async with rollback_session() as session:
        user, _b, txns = await _solo_with_ops(session, 9_800_030, legacy=False)
        _owner, target = await _family(session, 9_800_040, legacy=True)
        await convert_join_with_own_budget(session, user=user, target=target)
        await session.flush()
        await _refresh(session, txns)
        exp, inc = await _live(session, target.id)
        assert len([c for c in exp if c.parent_id is None]) == 7 + 0
        assert len([c for c in exp if c.parent_id is not None]) == 23 + 1
        assert len(inc) == 5
        by_id = {c.id: c for c in exp}
        for new_key, legacy_key in [
            ("taxi_transit", "taxi"), ("doctors", "doctors_clinics"),
            ("toi_gifts", "events_celebrations"), ("personal_leisure", "shopping_leisure"),
            ("cafes_delivery", "cafes_restaurants"),
        ]:
            assert by_id[txns["e:" + new_key].expense_category_id].translation_key == legacy_key
        # no legacy counterpart: nearest parent
        assert (
            by_id[txns["e:family_help"].expense_category_id].translation_key
            == "events_celebrations"
        )
        await _assert_invariants(session, target.id)


@pytest.mark.parametrize("legacy_user", [True, False])
async def test_deleted_category_stays_deleted_after_move(legacy_user) -> None:
    async with rollback_session() as session:
        user, _b, txns = await _solo_with_ops(session, 9_800_050, legacy=legacy_user)
        _owner, target = await _family(session, 9_800_060, legacy=False)
        await convert_join_with_own_budget(session, user=user, target=target)
        await session.flush()
        await _refresh(session, txns)
        dead = await session.get(ExpenseCategory, txns["dead"].expense_category_id)
        assert dead.family_budget_id == target.id and dead.is_deleted is True
        await _assert_invariants(session, target.id)


@pytest.mark.parametrize("src_legacy", [True, False])
async def test_leave_gets_source_set_and_no_mixture(src_legacy) -> None:
    async with rollback_session() as session:
        owner, budget = await _family(session, 9_800_070, legacy=src_legacy)
        member, _ = await create_user(session, telegram_id=9_800_071, role="member", budget=budget)
        new_budget = await detach_member_to_own_budget(
            session, departing_user=member, old_budget=budget, reason="left", bot=AsyncMock()
        )
        await session.flush()
        exp, _inc = await _live(session, new_budget.id)
        keys = {c.translation_key for c in exp}
        assert ("taxi" in keys) is src_legacy and ("taxi_transit" in keys) is (not src_legacy)
        await _assert_invariants(session, new_budget.id)


async def test_new_user_leaving_mixed_family_gets_new_set() -> None:
    """Existing mixed budgets: the leaver gets the new set; old keys map to successors."""
    async with rollback_session() as session:
        owner, budget = await _family(session, 9_800_080, legacy=False)
        member, _ = await create_user(session, telegram_id=9_800_081, role="member", budget=budget)
        # parallel legacy copy (what the old join code created)
        await copy_seed_categories_only(session, budget.id, legacy=True)
        wallet = make_wallet(budget, name="Л", is_personal=True, owner_user_id=member.id)
        session.add(wallet)
        await session.flush()
        taxi = await session.scalar(
            select(ExpenseCategory).where(
                ExpenseCategory.family_budget_id == budget.id,
                ExpenseCategory.translation_key == "taxi",
            )
        )
        t = Transaction(
            family_budget_id=budget.id, wallet_id=wallet.id, amount=1, type="expense",
            expense_category_id=taxi.id, created_by_user_id=member.id,
            transaction_date=datetime.datetime.now(datetime.UTC),
        )
        session.add(t)
        await session.flush()
        new_budget = await detach_member_to_own_budget(
            session, departing_user=member, old_budget=budget, reason="left", bot=AsyncMock()
        )
        await session.flush()
        await session.refresh(t)
        cat = await session.get(ExpenseCategory, t.expense_category_id)
        assert cat.family_budget_id == new_budget.id and cat.translation_key == "taxi_transit"
        await _assert_invariants(session, new_budget.id)


async def test_three_cycles_join_leave_delete_keep_invariants() -> None:
    async with rollback_session() as session:
        _owner, fam = await _family(session, 9_800_090, legacy=False)
        user, _b, txns = await _solo_with_ops(session, 9_800_100, legacy=True)
        current = None
        for _ in range(3):
            await convert_join_with_own_budget(session, user=user, target=fam)
            await session.flush()
            await _assert_invariants(session, fam.id)
            new_budget = await detach_member_to_own_budget(
                session, departing_user=user, old_budget=fam, reason="left", bot=AsyncMock()
            )
            await session.flush()
            await _assert_invariants(session, new_budget.id)
            await _assert_invariants(session, fam.id)
            current = new_budget
            # the ex-member is an owner of own budget again; join the family once more
            user.role = "owner"
        await _refresh(session, txns)
        exp, _inc = await _live(session, current.id)
        assert not {c.translation_key for c in exp} & (LEGACY - NEW)


# ---- ux-r8: a category deleted in the TARGET family never comes back to life on join ----


async def _delete_in(session, budget_id, *keys):
    now = datetime.datetime.now(datetime.UTC)
    for model in (ExpenseCategory, IncomeCategory):
        for c in await session.scalars(
            select(model).where(
                model.family_budget_id == budget_id, model.translation_key.in_(keys)
            )
        ):
            c.is_deleted = True
            c.deleted_at = now
    await session.flush()


async def _all_keys(session, budget_id, *, live):
    out = set()
    for model in (ExpenseCategory, IncomeCategory):
        stmt = select(model).where(model.family_budget_id == budget_id)
        if live:
            stmt = stmt.where(model.is_deleted.is_(False))
        out |= {c.translation_key for c in await session.scalars(stmt) if c.translation_key}
    return out


async def _txn_cats(session, txns):
    res = {}
    for label, t in txns.items():
        await session.refresh(t)
        if t.expense_category_id:
            res[label] = await session.get(ExpenseCategory, t.expense_category_id)
        else:
            res[label] = await session.get(IncomeCategory, t.income_category_id)
    return res


@pytest.mark.parametrize(
    ("user_legacy", "family_legacy", "deleted", "moved"),
    [
        # QA repeat 1: new family deleted taxi; old user (taxi, public_transport) joins
        (True, False, ["taxi_transit"], ["e:taxi", "e:public_transport"]),
        # QA repeat 2: new family deleted cafes_delivery; old user with delivery joins
        (True, False, ["cafes_delivery"], ["e:delivery", "e:cafes_restaurants"]),
        # QA repeat 3: old family deleted fuel; new user (car) joins
        (False, True, ["fuel"], ["e:car"]),
        # incomes, both directions
        (True, False, ["business_side_job"], ["i:side_job"]),
        (False, True, ["side_job"], ["i:business_side_job"]),
    ],
)
async def test_category_deleted_in_target_family_stays_deleted(
    user_legacy, family_legacy, deleted, moved
) -> None:
    async with rollback_session() as session:
        user, _b, txns = await _solo_with_ops(session, 9_800_110, legacy=user_legacy)
        _owner, target = await _family(session, 9_800_120, legacy=family_legacy)
        await _delete_in(session, target.id, *deleted)
        live_before = await _all_keys(session, target.id, live=True)
        set_before = await budget_uses_legacy_set(session, target.id)
        await convert_join_with_own_budget(session, user=user, target=target)
        await session.flush()
        cats = await _txn_cats(session, txns)
        # nothing deleted came back: live keys of the family are unchanged by the join
        assert (await _all_keys(session, target.id, live=True)) - live_before <= set()
        assert await budget_uses_legacy_set(session, target.id) is set_before
        for label in moved:
            cat = cats[label]
            assert cat.family_budget_id == target.id
            # the operation lies in the family's deleted category, not in a resurrected one
            assert cat.is_deleted is True, (label, cat.name)
        await _assert_invariants(session, target.id)


async def test_member_returning_to_family_with_deleted_category_changes_nothing() -> None:
    async with rollback_session() as session:
        _owner, fam = await _family(session, 9_800_130, legacy=False)
        await _delete_in(session, fam.id, "taxi_transit")
        user, _b, txns = await _solo_with_ops(session, 9_800_140, legacy=True)
        live_before = await _all_keys(session, fam.id, live=True)
        for _ in range(2):
            await convert_join_with_own_budget(session, user=user, target=fam)
            await session.flush()
            new_budget = await detach_member_to_own_budget(
                session, departing_user=user, old_budget=fam, reason="left", bot=AsyncMock()
            )
            await session.flush()
            user.role = "owner"
            assert await _all_keys(session, fam.id, live=True) == live_before
            assert await budget_uses_legacy_set(session, fam.id) is False
        assert new_budget is not None


async def test_bot_word_taxi_after_join_lands_in_the_live_family_category() -> None:
    """The joiner deleted his own (not renamed) taxi; the family has a live taxi category.
    After the join the word 'такси' writes into the family's live category, exactly one."""
    async with rollback_session() as session:
        user, solo = await create_user(session, telegram_id=9_800_150)
        await copy_seed_categories_only(session, solo.id, legacy=True)
        taxi = await session.scalar(
            select(ExpenseCategory).where(
                ExpenseCategory.family_budget_id == solo.id, ExpenseCategory.translation_key == "taxi"
            )
        )
        wallet = make_wallet(solo, name="Мой", is_personal=True, owner_user_id=user.id)
        session.add(wallet)
        await session.flush()
        session.add(
            Transaction(
                family_budget_id=solo.id, wallet_id=wallet.id, amount=1, type="expense",
                expense_category_id=taxi.id, created_by_user_id=user.id,
                transaction_date=datetime.datetime.now(datetime.UTC),
            )
        )
        taxi.is_deleted, taxi.deleted_at = True, datetime.datetime.now(datetime.UTC)
        _owner, target = await _family(session, 9_800_160, legacy=False)
        await convert_join_with_own_budget(session, user=user, target=target)
        await session.flush()
        await _assert_invariants(session, target.id)
        exp, _inc = await _live(session, target.id)
        pre = [PrefilterCategory(c.id, c.name, c.translation_key, c.parent_id) for c in exp]
        result = try_prefilter(
            "такси 20000", wallet_names=[], expense_categories=pre, income_categories=[]
        )
        assert result.operation is not None and result.operation.category == "Такси и проезд"
        assert len([c for c in exp if c.translation_key in ("taxi", "taxi_transit")]) == 1
