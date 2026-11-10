"""ux-p6 backend: category set of NEW budgets (PRD-ux U7), old budgets untouched."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.parsing.cascade_keywords import CASCADE_KEYWORDS
from app.parsing.prefilter import PrefilterCategory, try_prefilter
from app.services.budget_seed import (
    LEGACY_SEED_EXPENSE_CATEGORIES,
    LEGACY_SEED_INCOME_CATEGORIES,
    SEED_EXPENSE_CATEGORIES,
    SEED_INCOME_CATEGORIES,
    copy_seed_categories_only,
    copy_seed_data,
    count_seed_rows,
)
from app.services.display_name import SEED_NAMES_UZ, build_seed_name_by_key, display_name
from tests.test_quick_entry_flow import create_user, pytestmark, rollback_session  # noqa: F401

TABLE = {
    "Еда": ["Продукты", "Кафе и доставка"],
    "Транспорт": ["Такси и проезд", "Автомобиль"],
    "Дом": ["Аренда", "Коммуналка и связь", "Ремонт и вещи для дома"],
    "Дети": ["Учёба и кружки", "Детские товары"],
    "Здоровье": ["Аптека", "Врачи"],
    "Тои и подарки": ["Тои и маърака", "Подарки", "Помощь родным"],
    "Личное и досуг": ["Одежда", "Красота и уход", "Развлечения и подписки"],
}
INCOME = ["Зарплата", "Бизнес и подработка", "Переводы и подарки", "Прочее"]
UZ_TABLE = {  # product-findings §1 (+ names already audited in the app for shared keys)
    "food": "Ovqat", "cafes_delivery": "Kafe va yetkazib berish", "transport": "Transport",
    "taxi_transit": "Taksi va yo'l haqi", "car": "Avtomobil", "home": "Uy", "rent": "Ijara",
    "utilities_telecom": "Kommunal va aloqa", "home_repairs": "Ta'mir va uy jihozlari",
    "children": "Bolalar", "kids_learning": "O'qish va to'garaklar", "health": "Sog'liq",
    "drugstore": "Dorixona", "doctors": "Shifokorlar", "toi_gifts": "To'ylar va sovg'alar",
    "toi_celebrations": "To'y va marosimlar", "event_gifts": "Sovg'alar",
    "family_help": "Yaqinlarga yordam", "personal_leisure": "Shaxsiy va dam olish",
    "fun_subscriptions": "Ko'ngilochar va obunalar", "business_side_job": "Biznes va qo'shimcha ish",
    "transfers_gifts": "O'tkazmalar va sovg'alar", "income_other": "Boshqa daromad",
    "salary": "Ish haqi",
}


def test_constants_match_the_table() -> None:
    assert {p: [n for n, _ in subs] for p, (_k, subs) in SEED_EXPENSE_CATEGORIES.items()} == TABLE
    assert [n for n, _ in SEED_INCOME_CATEGORIES] == INCOME
    assert len(SEED_EXPENSE_CATEGORIES) == 7
    assert sum(len(s) for _k, s in SEED_EXPENSE_CATEGORIES.values()) == 17
    keys = [k for k, _ in SEED_INCOME_CATEGORIES] + [
        x for pk, subs in SEED_EXPENSE_CATEGORIES.values() for x in [pk, *[k for _, k in subs]]
    ]
    assert len(keys) == len(set(keys))


async def test_new_budget_is_seeded_7_17_4_with_protected_parents() -> None:
    async with rollback_session() as session:
        _user, budget = await create_user(session, telegram_id=9_620_001)
        await copy_seed_data(session, budget.id)
        counts = await count_seed_rows(session, budget.id)
        assert counts["expense_top_level"] == 7
        assert counts["expense_subcategories"] == 17
        assert counts["income_categories"] == 4
        cats = list(await session.scalars(
            select(ExpenseCategory).where(ExpenseCategory.family_budget_id == budget.id)
        ))
        parents = {c.id: c for c in cats if c.parent_id is None}
        assert {p.name for p in parents.values()} == set(TABLE)
        assert {p.translation_key for p in parents.values() if p.is_protected} == {
            "food", "home", "health"}
        for c in cats:
            if c.parent_id is not None:
                assert c.name in TABLE[parents[c.parent_id].name]
                assert not c.is_protected
        # colours by the existing rule: every parent has its own colour
        assert len({p.color_index for p in parents.values()}) == 7
        incomes = list(await session.scalars(
            select(IncomeCategory).where(IncomeCategory.family_budget_id == budget.id)
        ))
        assert {i.name for i in incomes} == set(INCOME)


def test_uz_names_exist_for_every_new_key_and_match_the_table() -> None:
    for key, value in UZ_TABLE.items():
        assert SEED_NAMES_UZ[key] == value, key
    assert set(build_seed_name_by_key()) <= set(SEED_NAMES_UZ)
    for value in SEED_NAMES_UZ.values():
        assert "’" not in value and "ʻ" not in value


def test_key_shared_by_old_and_new_set_has_the_same_name() -> None:
    old = {k: n for n, k in LEGACY_SEED_INCOME_CATEGORIES}
    for pn, (pk, subs) in LEGACY_SEED_EXPENSE_CATEGORIES.items():
        old[pk] = pn
        old.update({k: n for n, k in subs})
    new = {k: n for n, k in SEED_INCOME_CATEGORIES}
    for pn, (pk, subs) in SEED_EXPENSE_CATEGORIES.items():
        new[pk] = pn
        new.update({k: n for n, k in subs})
    for key in set(old) & set(new):
        assert old[key] == new[key], key


def test_display_name_localises_new_names() -> None:
    assert display_name("Врачи", "doctors", language="uz") == "Shifokorlar"
    assert display_name("Врачи", "doctors", language="ru") == "Врачи"
    assert display_name("Мои врачи", "doctors", language="uz") == "Мои врачи"


async def test_old_budget_keeps_its_categories() -> None:
    async with rollback_session() as session:
        _user, budget = await create_user(session, telegram_id=9_620_002)
        await copy_seed_categories_only(session, budget.id, legacy=True)
        counts = await count_seed_rows(session, budget.id)
        assert counts["expense_top_level"] == 7 and counts["expense_subcategories"] == 23
        assert counts["income_categories"] == 5
        names = set(await session.scalars(
            select(ExpenseCategory.name).where(ExpenseCategory.family_budget_id == budget.id)
        ))
        assert {"События и тои", "Покупки и досуг", "Стоматология", "Доставка"} <= names


# ------------------------------------------------------------------------- keywords


def _budget_categories(seed):
    """PrefilterCategory lists (expense, income) for a seed set, built like the real budget."""
    income, expense = [], []
    for name, key in seed[0]:
        income.append(PrefilterCategory(uuid.uuid4(), name, key, None))
    for pname, (pkey, subs) in seed[1].items():
        parent = PrefilterCategory(uuid.uuid4(), pname, pkey, None)
        expense.append(parent)
        expense += [PrefilterCategory(uuid.uuid4(), n, k, parent.id) for n, k in subs]
    return expense, income


NEW = _budget_categories((SEED_INCOME_CATEGORIES, SEED_EXPENSE_CATEGORIES))
OLD = _budget_categories((LEGACY_SEED_INCOME_CATEGORIES, LEGACY_SEED_EXPENSE_CATEGORIES))


def _hit(text, budget):
    result = try_prefilter(text, wallet_names=[], expense_categories=budget[0],
                           income_categories=budget[1])
    return result.operation.category if result.operation else None


@pytest.mark.parametrize("text,expected", [
    ("стоматолог 200 тысяч", "Врачи"),
    ("stomatolog 200 ming", "Врачи"),
    ("врач 50 тысяч", "Врачи"),
    ("доставка 80 тысяч", "Кафе и доставка"),
    ("кафе 120 тысяч", "Кафе и доставка"),
    ("такси 25 тысяч", "Такси и проезд"),
    ("автобус 2 тысячи", "Такси и проезд"),
    ("метро 1400", "Такси и проезд"),
    ("бензин 200 тысяч", "Автомобиль"),
    ("техосмотр 150 тысяч", "Автомобиль"),
    ("садик 600 тысяч", "Учёба и кружки"),
    ("репетитор 300 тысяч", "Учёба и кружки"),
    ("коммуналка 300 тысяч", "Коммуналка и связь"),
    ("интернет 100 тысяч", "Коммуналка и связь"),
    ("аптека 40 тысяч", "Аптека"),
    ("родителям 500 тысяч", "Помощь родным"),
    ("маме 300 тысяч", "Помощь родным"),
    ("netflix 50 тысяч", "Развлечения и подписки"),
    ("кино 60 тысяч", "Развлечения и подписки"),
    ("ремонт 1 млн", "Ремонт и вещи для дома"),
    ("taksi 25 ming", "Такси и проезд"),
    ("yetkazib berish 80 ming", "Кафе и доставка"),
    ("benzin 200 ming", "Автомобиль"),
    ("stomatologga 300 ming", "Врачи"),
    ("onamga 500 ming", "Помощь родным"),
])
def test_new_budget_maps_merged_categories(text, expected) -> None:
    assert _hit(text, NEW) == expected


@pytest.mark.parametrize("text,expected", [
    ("зарплата 5 млн", "Зарплата"),
    ("подработка 500 тысяч", "Бизнес и подработка"),
    ("maosh 5 mln", "Зарплата"),
])
def test_new_budget_income_keywords(text, expected) -> None:
    assert _hit(text, NEW) == expected


def test_stomatolog_resolves_to_health_doctors_pair() -> None:
    expense, _ = NEW
    doctors = next(c for c in expense if c.name == "Врачи")
    health = next(c for c in expense if c.id == doctors.parent_id)
    assert health.name == "Здоровье"
    assert _hit("стоматолог 200 тысяч", NEW) == "Врачи"


@pytest.mark.parametrize("text,expected", [
    ("стоматолог 200 тысяч", "Стоматология"),
    ("доставка 80 тысяч", "Доставка"),
    ("бензин 200 тысяч", "Топливо"),
    ("автобус 2 тысячи", "Общественный транспорт"),
    ("кино 60 тысяч", "Развлечения"),
    ("зарплата 5 млн", "Зарплата"),
    ("подработка 500 тысяч", "Подработка"),
])
def test_old_budget_keeps_its_keyword_mapping(text, expected) -> None:
    assert _hit(text, OLD) == expected


@pytest.mark.parametrize("budget", [NEW, OLD], ids=["new", "old"])
def test_no_keyword_is_shared_by_unrelated_categories(budget) -> None:
    for categories in budget:
        parent_of = {c.id: c.parent_id for c in categories}
        seen: dict[str, PrefilterCategory] = {}
        for c in categories:
            for term in CASCADE_KEYWORDS.get(c.translation_key, []):
                other = seen.get(term.casefold())
                if other is not None and other.id != c.id:
                    related = parent_of[c.id] == other.id or parent_of[other.id] == c.id
                    assert related, (term, c.name, other.name)
                seen[term.casefold()] = c


async def test_podarki_button_resolves_in_new_and_old_budgets() -> None:
    from app.services.quick_entry_create import resolve_category_id

    async with rollback_session() as session:
        _u, new_budget = await create_user(session, telegram_id=9_620_010)
        await copy_seed_categories_only(session, new_budget.id)
        _u2, old_budget = await create_user(session, telegram_id=9_620_011)
        await copy_seed_categories_only(session, old_budget.id, legacy=True)
        for budget, income_name, parent_name in (
            (new_budget, "Переводы и подарки", "Тои и подарки"),
            (old_budget, "Подарки", "События и тои"),
        ):
            inc = await resolve_category_id(
                session, budget.id, op_type="income", category_name="Подарки", button_choice="income")
            exp = await resolve_category_id(
                session, budget.id, op_type="expense", category_name="Подарки", button_choice="expense")
            assert inc is not None and exp is not None
            assert (await session.get(IncomeCategory, inc)).name == income_name
            sub = await session.get(ExpenseCategory, exp)
            assert sub.name == "Подарки"
            assert (await session.get(ExpenseCategory, sub.parent_id)).name == parent_name
