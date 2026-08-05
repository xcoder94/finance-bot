import uuid

import pytest

from app.parsing.prefilter import PrefilterCategory, PrefilterReason, try_prefilter


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
        result = try_prefilter(
            "такси 25 тысяч",
            wallet_names=[],
            expense_categories=[transport, taxi],
            income_categories=[],
        )
        op = result.operation
        assert op is not None
        assert result.reason is None
        assert op.type == "expense"
        assert op.amount == 25_000
        assert op.category == "Такси"

    def test_renamed_food_by_new_name(self) -> None:
        food = _expense("Питание", translation_key="food")
        result = try_prefilter(
            "питание 10000",
            wallet_names=[],
            expense_categories=[food],
            income_categories=[],
        )
        op = result.operation
        assert op is not None
        assert result.reason is None
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
        result = try_prefilter(
            "транспорт такси 5000",
            wallet_names=[],
            expense_categories=[transport, taxi],
            income_categories=[],
        )
        op = result.operation
        assert op is not None
        assert result.reason is None
        assert op.category == "Такси"


class TestPrefilterFallThrough:
    def test_two_amounts(self) -> None:
        taxi = _expense("Такси", translation_key="taxi")
        result = try_prefilter(
            "10 тысяч и 500 тысяч такси",
            wallet_names=[],
            expense_categories=[taxi],
            income_categories=[],
        )
        assert result.operation is None
        assert result.reason == "multi_operation"

    def test_transfer_signal(self) -> None:
        taxi = _expense("Такси", translation_key="taxi")
        result = try_prefilter(
            "переложил 500 тысяч с карты на наличные",
            wallet_names=["Карта сум", "Наличный сум"],
            expense_categories=[taxi],
            income_categories=[],
        )
        assert result.operation is None
        assert result.reason == "transfer_signal"

    def test_ambiguous_two_categories(self) -> None:
        food = _expense("Еда", translation_key="food")
        taxi = _expense("Такси", translation_key="taxi")
        result = try_prefilter(
            "еда такси 10000",
            wallet_names=[],
            expense_categories=[food, taxi],
            income_categories=[],
        )
        assert result.operation is None
        assert result.reason == "category_ambiguous"

    def test_renamed_food_rejects_stock_keyword(self) -> None:
        food = _expense("Питание", translation_key="food")
        result = try_prefilter(
            "еда 10000",
            wallet_names=[],
            expense_categories=[food],
            income_categories=[],
        )
        assert result.operation is None
        assert result.reason == "no_category_match"

    def test_no_amount(self) -> None:
        taxi = _expense("Такси", translation_key="taxi")
        result = try_prefilter(
            "такси",
            wallet_names=[],
            expense_categories=[taxi],
            income_categories=[],
        )
        assert result.operation is None
        assert result.reason == "amount_not_singular"

    def test_two_wallets(self) -> None:
        taxi = _expense("Такси", translation_key="taxi")
        result = try_prefilter(
            "такси 5000 карта сум наличный сум",
            wallet_names=["Карта сум", "Наличный сум"],
            expense_categories=[taxi],
            income_categories=[],
        )
        assert result.operation is None
        assert result.reason == "wallet_ambiguous"


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
        result = try_prefilter(
            "продукты 200 тыс",
            wallet_names=[],
            expense_categories=[food, groceries],
            income_categories=[],
        )
        op = result.operation
        assert op is not None
        assert result.reason is None
        assert op.amount == 200_000

    def test_usd_suffix(self) -> None:
        salary = _income("Зарплата", translation_key="salary")
        result = try_prefilter(
            "зарплата 500$",
            wallet_names=[],
            expense_categories=[],
            income_categories=[salary],
        )
        op = result.operation
        assert op is not None
        assert result.reason is None
        assert op.type == "income"
        assert op.amount == 500
        assert op.currency == "USD"


class TestPrefilterReasons:
    @pytest.mark.parametrize(
        ("text", "expected_reason"),
        [
            ("", "amount_not_singular"),
            ("   ", "amount_not_singular"),
            (
                "переложил 500 тысяч с карты на наличные",
                "transfer_signal",
            ),
            ("10 тысяч и 500 тысяч такси", "multi_operation"),
            ("такси и еда 10000", "multi_operation"),
            ("такси", "amount_not_singular"),
            ("10000", "no_category_match"),
            ("еда такси 10000", "category_ambiguous"),
            (
                "такси 5000 карта сум наличный сум",
                "wallet_ambiguous",
            ),
        ],
    )
    def test_none_reason_codes(
        self,
        text: str,
        expected_reason: PrefilterReason,
    ) -> None:
        food = _expense("Еда", translation_key="food")
        taxi = _expense("Такси", translation_key="taxi")
        result = try_prefilter(
            text,
            wallet_names=["Карта сум", "Наличный сум"],
            expense_categories=[food, taxi],
            income_categories=[],
        )
        assert result.operation is None
        assert result.reason == expected_reason
