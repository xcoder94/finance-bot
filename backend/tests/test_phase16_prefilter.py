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


class TestDirectionVerbGuard:
    """Verb decides the type; a category from the other list is dropped (qarz bug)."""

    def _run(self, text: str, *, expense=(), income=()):  # type: ignore[no-untyped-def]
        return try_prefilter(
            text,
            wallet_names=[],
            expense_categories=list(expense),
            income_categories=list(income),
        )

    def test_toladim_with_income_only_qarz_is_expense_without_category(self) -> None:
        result = self._run("250000 qarz toladim", income=[_income("Qarz")])
        op = result.operation
        assert op is not None and result.reason is None
        assert op.type == "expense"
        assert op.amount == 250_000
        assert op.category is None

    def test_toladim_with_both_lists_picks_expense(self) -> None:
        result = self._run(
            "250000 qarz toladim",
            expense=[_expense("Qarz")],
            income=[_income("Qarz")],
        )
        op = result.operation
        assert op is not None
        assert op.type == "expense"
        assert op.category == "Qarz"

    def test_toladim_with_expense_only_qarz_keeps_category(self) -> None:
        result = self._run("250000 qarz toladim", expense=[_expense("Qarz")])
        op = result.operation
        assert op is not None
        assert (op.type, op.category, op.comment) == ("expense", "Qarz", "toladim")

    def test_apostrophe_verb_variant(self) -> None:
        for apos in ("'", "’", "ʻ", "ʼ"):
            result = self._run(
                f"250000 qarz to{apos}ladim", income=[_income("Qarz")]
            )
            assert result.operation is not None
            assert result.operation.type == "expense"
            assert result.operation.category is None

    def test_oldim_with_expense_only_qarz_is_income_without_category(self) -> None:
        result = self._run("qarz oldim 250000", expense=[_expense("Qarz")])
        op = result.operation
        assert op is not None
        assert op.type == "income"
        assert op.category is None

    def test_both_lists_oldim_picks_income(self) -> None:
        result = self._run(
            "qarz oldim 250000",
            expense=[_expense("Qarz")],
            income=[_income("Qarz")],
        )
        op = result.operation
        assert op is not None
        assert (op.type, op.category) == ("income", "Qarz")

    def test_ru_verb_with_income_dolg(self) -> None:
        result = self._run("вернул долг 250000", income=[_income("Долг")])
        op = result.operation
        assert op is not None
        assert op.type == "expense"
        assert op.category is None

    def test_ru_take_debt_with_expense_dolg(self) -> None:
        result = self._run("взял в долг 250000", expense=[_expense("Долг")])
        op = result.operation
        assert op is not None
        assert op.type == "income"
        assert op.category is None

    def test_no_verb_no_regression(self) -> None:
        result = self._run("250000 qarz", income=[_income("Qarz")])
        op = result.operation
        assert op is not None
        assert (op.type, op.category) == ("income", "Qarz")

    def test_both_lists_without_verb_stays_ambiguous(self) -> None:
        result = self._run(
            "250000 qarz", expense=[_expense("Qarz")], income=[_income("Qarz")]
        )
        assert result.operation is None
        assert result.reason == "category_ambiguous"

    def test_conflicting_verbs_fall_through(self) -> None:
        result = self._run(
            "qarz oldim va berdim 250000", income=[_income("Qarz")]
        )
        assert result.operation is None

    def test_verb_inside_other_word_ignored(self) -> None:
        result = self._run("250000 qarz boldim", income=[_income("Qarz")])
        op = result.operation
        assert op is not None
        assert (op.type, op.category) == ("income", "Qarz")

    def test_same_type_verb_keeps_category(self) -> None:
        result = self._run("получил 100000 Зарплата", income=[_income("Зарплата")])
        op = result.operation
        assert op is not None
        assert (op.type, op.category) == ("income", "Зарплата")


class TestPlainVerbsAreNotDirection:
    """oldim/keldi/взял/получил outside a debt context must not flip an expense (QA P1)."""

    def _run(self, text: str):  # type: ignore[no-untyped-def]
        return try_prefilter(
            text,
            wallet_names=[],
            expense_categories=[
                _expense("Такси"),
                _expense("Одежда"),
                _expense("Продукты"),
                _expense("Коммунальные"),
            ],
            income_categories=[_income("Зарплата")],
        )

    @pytest.mark.parametrize(
        ("text", "category"),
        [
            ("20000 taksi oldim", "Такси"),
            ("Такси oldim 20000", "Такси"),
            ("взял такси 30000", "Такси"),
            ("kiyim oldim 300000", "Одежда"),
            ("Одежда oldim 300000", "Одежда"),
            ("продукты взял 80000", "Продукты"),
            ("взяла Продукты 80000", "Продукты"),
            ("Коммунальные keldi 150000", "Коммунальные"),
            ("получил Такси 20000", "Такси"),
        ],
    )
    def test_plain_verb_keeps_expense_category(self, text: str, category: str) -> None:
        result = self._run(text)
        op = result.operation
        if op is None:
            # Not resolved by the prefilter is acceptable, but never as income.
            return
        assert op.type == "expense"
        assert op.category in (category, None)

    @pytest.mark.parametrize(
        "text",
        ["Такси oldim 20000", "Одежда oldim 300000", "взял Такси 30000"],
    )
    def test_plain_verb_with_known_category_is_expense_with_category(self, text: str) -> None:
        op = self._run(text).operation
        assert op is not None
        assert op.type == "expense"
        assert op.category is not None

    @pytest.mark.parametrize(
        "text",
        ["qarzga oldim 250000", "qarzni qaytardim 250000", "взял в долг 250000"],
    )
    def test_debt_phrase_without_category_is_resolved_by_verb(self, text: str) -> None:
        op = self._run(text).operation
        assert op is not None
        assert op.category is None
        assert op.type == ("expense" if "qaytardim" in text else "income")

    def test_debt_oldim_still_income(self) -> None:
        op = self._run("qarz oldim 250000").operation
        assert op is not None and op.type == "income" and op.category is None


class TestDebtContextRound2:
    """QA round 2: purchase on credit stays an expense; debt word only at word start."""

    def _run(self, text: str, extra_expense=(), extra_income=()):  # type: ignore[no-untyped-def]
        return try_prefilter(
            text,
            wallet_names=[],
            expense_categories=[
                _expense("Такси"),
                _expense("Taksi"),
                _expense("Telefon"),
                *extra_expense,
            ],
            income_categories=[_income("Зарплата"), *extra_income],
        )

    @pytest.mark.parametrize(
        ("text", "category"),
        [
            ("qarzga telefon oldim 3000000", "Telefon"),
            ("telefon qarzga oldim 3000000", "Telefon"),
            ("qarzga taksi oldim 20000", "Taksi"),
            ("в долг такси взял 20000", "Такси"),
        ],
    )
    def test_credit_purchase_with_ordinary_category_is_expense(
        self, text: str, category: str
    ) -> None:
        op = self._run(text).operation
        assert op is not None
        assert (op.type, op.category) == ("expense", category)

    @pytest.mark.parametrize(
        "text",
        [
            "взял такси надолго 200000",
            "задолго такси взял 200000",
            "долговечный такси взял 200000",
        ],
    )
    def test_debt_word_inside_word_is_not_debt_context(self, text: str) -> None:
        op = self._run(text).operation
        assert op is not None
        assert (op.type, op.category) == ("expense", "Такси")

    @pytest.mark.parametrize("text", ["взял надолго 200000", "oldim nodolg 5000"])
    def test_inside_word_no_category_not_resolved_as_debt(self, text: str) -> None:
        assert self._run(text).operation is None

    def test_debt_category_still_follows_verb(self) -> None:
        op = self._run(
            "qarz oldim 250000", extra_expense=[_expense("Qarz")]
        ).operation
        assert op is not None
        assert (op.type, op.category) == ("income", None)

    def test_debt_subcategory_follows_verb(self) -> None:
        parent = _expense("Qarz")
        sub = _expense("Rassrochka", parent_id=parent.id)
        op = self._run("qarzga rassrochka oldim 100000", extra_expense=[parent, sub]).operation
        assert op is not None
        assert (op.type, op.category) == ("income", None)

    def test_debt_variant_name_follows_verb(self) -> None:
        op = self._run(
            "взял долги 100000", extra_expense=[_expense("Долги")]
        ).operation
        assert op is not None
        assert (op.type, op.category) == ("income", None)
