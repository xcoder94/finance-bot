import uuid
from datetime import date

import pytest

from app.models.wallet import Wallet
from bot.quick_entry.cards import (
    card_keyboard,
    format_amount,
    format_card,
    type_question_keyboard,
    wallet_picker_keyboard,
)
from bot.quick_entry.texts import (
    MSG_GONE,
    MSG_MODEL_FAIL,
    MSG_NO_AMOUNT,
    MSG_TOO_LONG,
    MSG_TOO_MANY_OPS,
    MSG_TYPE_QUESTION,
    currency_missing_text,
    model_limit_text,
    unparsed_limit_text,
)


class TestFormatAmount:
    def test_uzs(self) -> None:
        assert format_amount(25_000, "UZS") == "25 000 сум"

    def test_usd(self) -> None:
        assert format_amount(10, "USD") == "10 $"

    def test_large_uzs(self) -> None:
        assert format_amount(1_275_000, "UZS") == "1 275 000 сум"


class TestFormatCard:
    def test_prd_section_7_1_example(self) -> None:
        text = format_card(
            sign="➖",
            amount=25_000,
            currency="UZS",
            category_label="Такси",
            comment="такси до работы",
            wallet_name="Наличный сум",
            op_date=date(2026, 8, 1),
            balance=1_275_000,
        )
        assert text == (
            "➖ **25 000 сум** · Такси\n"
            "такси до работы\n"
            "Наличный сум · 1 августа\n"
            "Осталось: 1 275 000 сум"
        )

    def test_without_comment(self) -> None:
        text = format_card(
            sign="➕",
            amount=300_000,
            currency="UZS",
            category_label="Без категории",
            comment=None,
            wallet_name="Карта сум",
            op_date=date(2026, 8, 1),
            balance=975_000,
        )
        assert text == (
            "➕ **300 000 сум** · Без категории\n"
            "Карта сум · 1 августа\n"
            "Осталось: 975 000 сум"
        )

    def test_usd_balance(self) -> None:
        text = format_card(
            sign="➖",
            amount=10,
            currency="USD",
            category_label="Продукты",
            comment=None,
            wallet_name="Карта USD",
            op_date=date(2026, 3, 15),
            balance=400,
        )
        assert "10 $" in text
        assert "15 марта" in text
        assert "Осталось: 400 $" in text


class TestTextConstants:
    def test_msg_constants(self) -> None:
        assert MSG_TOO_LONG == (
            "Сообщение слишком длинное — максимум 500 символов. Разбейте на несколько."
        )
        assert MSG_TOO_MANY_OPS == (
            "В одном сообщении можно записать не больше 5 операций. "
            "Разбейте на несколько сообщений."
        )
        assert MSG_NO_AMOUNT == (
            "Не нашёл сумму в сообщении.\n"
            "Напишите так: `такси 25 тысяч` или `продукты 200 тыс с карты`"
        )
        assert MSG_MODEL_FAIL == (
            "Не получилось записать — дело не в вашем сообщении. "
            "Попробуйте отправить его ещё раз через минуту или запишите операцию в приложении."
        )
        assert MSG_GONE == "Запись больше не существует."
        assert MSG_TYPE_QUESTION == "Не понял, это трата или доход?"

    def test_currency_missing_uzs(self) -> None:
        assert currency_missing_text("UZS") == (
            "Кошелька в сумах у вас нет. Добавьте его в приложении, в настройках."
        )

    def test_currency_missing_usd(self) -> None:
        assert currency_missing_text("USD") == (
            "Кошелька в долларах у вас нет. Добавьте его в приложении, в настройках."
        )

    def test_model_limit_text(self) -> None:
        assert model_limit_text(50) == (
            "Сегодня записано 50 операций — это дневной предел на семью. "
            "Новые записи можно вносить с полуночи."
        )

    def test_unparsed_limit_text(self) -> None:
        assert unparsed_limit_text(20) == (
            "Сегодня не удалось разобрать 20 сообщений — это дневной предел. "
            "Записи можно добавить в приложении."
        )


class TestCardKeyboard:
    def test_card_keyboard_buttons(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "bot.quick_entry.cards.MINI_APP_URL",
            "https://example.com/app",
        )
        txn_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        kb = card_keyboard(txn_id)
        row = kb.inline_keyboard[0]
        assert [btn.text for btn in row] == ["Кошелёк", "Изменить", "Удалить"]
        assert row[0].callback_data == f"qe:wal:{txn_id}"
        assert row[1].web_app is not None
        assert row[1].web_app.url == f"https://example.com/app?tx={txn_id}"
        assert row[2].callback_data == f"qe:del:{txn_id}"


class TestTypeQuestionKeyboard:
    def test_type_question_keyboard(self) -> None:
        pending_id = "pending-123"
        kb = type_question_keyboard(pending_id)
        row = kb.inline_keyboard[0]
        assert [btn.text for btn in row] == ["Потратил", "Получил"]
        assert row[0].callback_data == f"qe:type:{pending_id}:expense"
        assert row[1].callback_data == f"qe:type:{pending_id}:income"


class TestWalletPickerKeyboard:
    def test_wallet_picker_keyboard(self) -> None:
        txn_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
        wallets = [
            Wallet(name="Карта сум", currency="UZS"),
            Wallet(name="Наличный сум", currency="UZS"),
        ]
        wallets[0].id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        wallets[1].id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        kb = wallet_picker_keyboard(txn_id, wallets)
        assert len(kb.inline_keyboard) == 2
        assert kb.inline_keyboard[0][0].text == "Карта сум"
        assert (
            kb.inline_keyboard[0][0].callback_data
            == f"qe:walset:{txn_id}:{wallets[0].id}"
        )
        assert kb.inline_keyboard[1][0].text == "Наличный сум"
        assert (
            kb.inline_keyboard[1][0].callback_data
            == f"qe:walset:{txn_id}:{wallets[1].id}"
        )
