import uuid

import pytest

from app.parsing.prefilter import PrefilterCategory, try_prefilter


def _expense(
    name: str,
    *,
    translation_key: str | None = None,
    parent_id: object | None = None,
) -> PrefilterCategory:
    return PrefilterCategory(
        id=uuid.uuid4(),
        name=name,
        translation_key=translation_key,
        parent_id=parent_id,
    )


def _income(name: str, *, translation_key: str | None = None) -> PrefilterCategory:
    return PrefilterCategory(
        id=uuid.uuid4(),
        name=name,
        translation_key=translation_key,
        parent_id=None,
    )


class TestPrefilterHits:
    def test_taxi_thousands(self) -> None:
        transport_id = uuid.uuid4()
        transport = PrefilterCategory(
            id=transport_id,
            name="Транспорт",
            translation_key="transport",
            parent_id=None,
        )
        taxi = PrefilterCategory(
            id=uuid.uuid4(),
            name="Такси",
            translation_key="taxi",
            parent_id=transport_id,
        )
        op = try_prefilter(
            "такси 25 тысяч",
            wallet_names=[],
            expense_categories=[transport, taxi],
            income_categories=[],
        )
        assert op is not None
        assert op.type == "expense"
        assert op.amount == 25_000
        assert op.category == "Такси"

    def test_renamed_food_by_new_name(self) -> None:
        food = _expense("Питание", translation_key="food")
        op = try_prefilter(
            "питание 10000",
            wallet_names=[],
            expense_categories=[food],
            income_categories=[],
        )
        assert op is not None
        assert op.category == "Питание"
        assert op.amount == 10_000

    def test_subcategory_beats_parent(self) -> None:
        transport_id = uuid.uuid4()
        transport = PrefilterCategory(
            id=transport_id,
            name="Транспорт",
            translation_key="transport",
            parent_id=None,
        )
        taxi = PrefilterCategory(
            id=uuid.uuid4(),
            name="Такси",
            translation_key="taxi",
            parent_id=transport_id,
        )
        op = try_prefilter(
            "транспорт такси 5000",
            wallet_names=[],
            expense_categories=[transport, taxi],
            income_categories=[],
        )
        assert op is not None
        assert op.category == "Такси"


class TestPrefilterFallThrough:
    def test_two_amounts(self) -> None:
        taxi = _expense("Такси", translation_key="taxi")
        assert (
            try_prefilter(
                "10 тысяч и 500 тысяч такси",
                wallet_names=[],
                expense_categories=[taxi],
                income_categories=[],
            )
            is None
        )

    def test_transfer_signal(self) -> None:
        taxi = _expense("Такси", translation_key="taxi")
        assert (
            try_prefilter(
                "переложил 500 тысяч с карты на наличные",
                wallet_names=["Карта сум", "Наличный сум"],
                expense_categories=[taxi],
                income_categories=[],
            )
            is None
        )

    def test_ambiguous_two_categories(self) -> None:
        food = _expense("Еда", translation_key="food")
        taxi = _expense("Такси", translation_key="taxi")
        assert (
            try_prefilter(
                "еда такси 10000",
                wallet_names=[],
                expense_categories=[food, taxi],
                income_categories=[],
            )
            is None
        )

    def test_renamed_food_rejects_stock_keyword(self) -> None:
        food = _expense("Питание", translation_key="food")
        assert (
            try_prefilter(
                "еда 10000",
                wallet_names=[],
                expense_categories=[food],
                income_categories=[],
            )
            is None
        )

    def test_no_amount(self) -> None:
        taxi = _expense("Такси", translation_key="taxi")
        assert (
            try_prefilter(
                "такси",
                wallet_names=[],
                expense_categories=[taxi],
                income_categories=[],
            )
            is None
        )

    def test_two_wallets(self) -> None:
        taxi = _expense("Такси", translation_key="taxi")
        assert (
            try_prefilter(
                "такси 5000 с карты сум",
                wallet_names=["Карта сум", "Наличный сум"],
                expense_categories=[taxi],
                income_categories=[],
            )
            is None
        )


class TestPrefilterAmounts:
    def test_tys_suffix(self) -> None:
        food_id = uuid.uuid4()
        food = PrefilterCategory(
            id=food_id,
            name="Еда",
            translation_key="food",
            parent_id=None,
        )
        groceries = PrefilterCategory(
            id=uuid.uuid4(),
            name="Продукты",
            translation_key="groceries",
            parent_id=food_id,
        )
        op = try_prefilter(
            "продукты 200 тыс",
            wallet_names=[],
            expense_categories=[food, groceries],
            income_categories=[],
        )
        assert op is not None
        assert op.amount == 200_000

    def test_usd_suffix(self) -> None:
        salary = _income("Зарплата", translation_key="salary")
        op = try_prefilter(
            "зарплата 500$",
            wallet_names=[],
            expense_categories=[],
            income_categories=[salary],
        )
        assert op is not None
        assert op.type == "income"
        assert op.amount == 500
        assert op.currency == "USD"
