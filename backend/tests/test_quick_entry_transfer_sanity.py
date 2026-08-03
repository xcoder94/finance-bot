from app.parsing.types import ParsedOperation
from app.services.quick_entry_transfer import (
    effective_rate,
    needs_exchange_refusal,
    text_has_rate_marker,
)


def test_rate_marker_po_and_po_kursu():
    assert text_has_rate_marker("поменял 100 долларов на сумы по 12800")
    assert text_has_rate_marker("обмен по курсу 12800")
    assert not text_has_rate_marker("поменял 100 долларов на сумы 12800")
    assert not text_has_rate_marker("перевел с карты доллара на карту сум 50$")


def test_effective_rate_requires_marker():
    op = ParsedOperation(
        type="exchange", amount=100, currency="USD",
        wallet_hint=None, category=None, comment=None,
        from_wallet_hint="карта", to_wallet_hint="карта", rate=12_800,
    )
    assert effective_rate(op, "поменял 100 долларов на сумы по 12800") == 12_800
    assert effective_rate(op, "поменял 100 долларов на сумы 12800") is None


def test_needs_exchange_refusal_cross_currency_without_rate():
    assert needs_exchange_refusal(from_currency="USD", to_currency="UZS", rate=None) is True
    assert needs_exchange_refusal(from_currency="USD", to_currency="UZS", rate=12_800) is False
    assert needs_exchange_refusal(from_currency="UZS", to_currency="UZS", rate=None) is False
