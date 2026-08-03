import pytest
from app.parsing.stub import StubParser
from app.parsing.types import ParseRequest


def _req(text: str) -> ParseRequest:
    return ParseRequest(text=text, wallet_names=[], expense_category_names=[], income_category_names=[])


@pytest.mark.anyio
async def test_stub_same_currency_transfer():
    op = (await StubParser().parse(_req("переложил 500 тысяч с карты на наличные"))).operations[0]
    assert op.type == "transfer"
    assert op.amount == 500_000
    assert op.currency == "UZS"
    assert op.from_wallet_hint is not None
    assert op.to_wallet_hint is not None
    assert op.rate is None


@pytest.mark.anyio
async def test_stub_exchange_with_rate_marker():
    op = (await StubParser().parse(_req("поменял 100 долларов на сумы по 12800"))).operations[0]
    assert op.type == "exchange"
    assert op.amount == 100
    assert op.currency == "USD"
    assert op.rate == 12_800


@pytest.mark.anyio
async def test_stub_cross_currency_without_rate_russian():
    op = (await StubParser().parse(_req("перевел с карты доллара на карту сум 50$"))).operations[0]
    assert op.type in ("transfer", "exchange")
    assert op.amount == 50
    assert op.rate is None


@pytest.mark.anyio
async def test_stub_cross_currency_without_rate_uzbek():
    op = (await StubParser().parse(_req("dollar kartasidan so'm kartasiga 50$ o'tkazdim"))).operations[0]
    assert op.type in ("transfer", "exchange")
    assert op.amount == 50
    assert op.rate is None


@pytest.mark.anyio
async def test_stub_exchange_number_without_po_marker_has_null_rate():
    op = (await StubParser().parse(_req("поменял 100 долларов на сумы 12800"))).operations[0]
    assert op.type == "exchange"
    assert op.rate is None
