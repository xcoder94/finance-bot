import uuid
from datetime import date

import pytest

from bot.quick_entry.cards import (
    format_exchange_card,
    format_transfer_card,
    transfer_card_keyboard,
)
from bot.quick_entry.texts import MSG_EXCHANGE_RATE_REQUIRED


class TestMsgExchangeRateRequired:
    def test_prd_section_8_3_refusal(self) -> None:
        assert MSG_EXCHANGE_RATE_REQUIRED == (
            "Перевод между кошельками в разных валютах — это обмен, для него нужен курс.\n"
            "Сделайте его в приложении."
        )


class TestFormatTransferCard:
    def test_prd_section_8_2_example(self) -> None:
        text = format_transfer_card(
            amount=500_000,
            currency="UZS",
            from_wallet_name="Карта сум",
            to_wallet_name="Наличный сум",
            op_date=date(2026, 8, 1),
            from_balance=1_200_000,
            to_balance=1_775_000,
        )
        assert text == (
            "↔️ **500 000 сум** · Перевод\n"
            "Карта сум → Наличный сум · 1 августа\n"
            "Карта сум: 1 200 000 · Наличный сум: 1 775 000"
        )


class TestFormatExchangeCard:
    def test_prd_section_8_3_example(self) -> None:
        text = format_exchange_card(
            amount=100,
            from_currency="USD",
            to_amount=1_280_000,
            to_currency="UZS",
            rate=12_800,
            op_date=date(2026, 8, 1),
            from_wallet_name="Карта USD",
            to_wallet_name="Карта сум",
            from_balance=400,
            to_balance=3_080_000,
        )
        assert text == (
            "🔄 **100 $ → 1 280 000 сум** · Обмен\n"
            "Курс 12 800 · 1 августа\n"
            "Карта USD: 400 $ · Карта сум: 3 080 000 сум"
        )


class TestTransferCardKeyboard:
    def test_transfer_card_keyboard_buttons(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "bot.quick_entry.cards.MINI_APP_URL",
            "https://example.com/app",
        )
        txn_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        kb = transfer_card_keyboard(txn_id)
        row = kb.inline_keyboard[0]
        assert [btn.text for btn in row] == ["Изменить", "Удалить"]
        assert row[0].web_app is not None
        assert row[0].web_app.url == f"https://example.com/app?tx={txn_id}"
        assert row[1].callback_data == f"qe:del:{txn_id}"
