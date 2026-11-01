"""dev-fix3: a spoken / short-hand sum ("50 ming", "пятьдесят тысяч", "50к") completes a waiting purchase."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.shopping import ShoppingItem
from app.models.transaction import Transaction
from app.parsing.http_adapter import _parse_response_payload
from app.parsing.prompt import IMMUTABLE_PARSER_INSTRUCTIONS
from app.parsing.types import ParseResponse
from bot.quick_entry.handlers import set_parser_override
from bot.quick_entry.shopping_pending import bare_text_amount, is_malformed_number
from tests.test_m3_4_bot_pending import (  # noqa: F401
    VOICE,
    FixedParser,
    _env,
    expense,
    feed,
    open_pending,
    setup_family,
    tx_count,
)
from tests.test_quick_entry_flow import pytestmark, rollback_session  # noqa: F401

SPOKEN = [
    ("50 ming", 50_000),
    ("50 ming so'm", 50_000),
    ("50 ming sum", 50_000),
    ("50 ming so’m", 50_000),
    ("50ming", 50_000),
    ("ellik ming", 50_000),
    ("ellik ming so'm", 50_000),
    ("yuz ellik ming", 150_000),
    ("50 тысяч", 50_000),
    ("50 тысяч сум", 50_000),
    ("50 тыс", 50_000),
    ("пятьдесят тысяч", 50_000),
    ("пятьдесят тысяч сум", 50_000),
    ("сто пятьдесят тысяч", 150_000),
    ("50к", 50_000),
    ("50 к", 50_000),
    ("50k", 50_000),
    ("50 K", 50_000),
    ("1,5 ming", 1_500),
    ("1.5 тысячи", 1_500),
    ("ming", 1_000),
    ("50 minga", None),
    ("50 ming bread", None),
    ("12 3 ming", None),
    ("хлеб 50 тысяч", None),
]


@pytest.mark.parametrize("text,expected", SPOKEN)
def test_bare_text_amount_spoken(text, expected) -> None:
    assert bare_text_amount(text) == expected


def test_malformed_still_malformed() -> None:
    assert is_malformed_number("12 3 ming") is False or bare_text_amount("12 3 ming") is None
    assert is_malformed_number("1.5")


def test_prompt_explains_thousand_words() -> None:
    assert "ming" in IMMUTABLE_PARSER_INSTRUCTIONS
    assert "transcript" in IMMUTABLE_PARSER_INSTRUCTIONS


def test_adapter_reads_transcript() -> None:
    resp = _parse_response_payload({"operations": [], "speech_status": "recognized", "transcript": "50 ming"})
    assert resp.transcript == "50 ming"
    assert _parse_response_payload({"operations": []}).transcript is None


class TestVoiceSpoken:
    @pytest.mark.parametrize(
        "response",
        [
            # model got it right
            ParseResponse(operations=[expense(50_000, type_="ambiguous")], speech_status="recognized"),
            # model heard the digits but did not scale "ming"
            ParseResponse(operations=[expense(50, type_="ambiguous")], speech_status="recognized", transcript="50 ming"),
            # no amount in the operation, only the heard words
            ParseResponse(operations=[expense(None, type_="ambiguous")], speech_status="recognized", transcript="50 ming so'm"),
            ParseResponse(operations=[], speech_status="recognized", transcript="ellik ming"),
            ParseResponse(operations=[], speech_status="recognized", transcript="пятьдесят тысяч"),
            ParseResponse(operations=[], speech_status="recognized", transcript="50к"),
            # model took the sum for a goods list
            ParseResponse(operations=[], speech_status="recognized", shopping_items=["50 ming"]),
            ParseResponse(operations=[], speech_status="recognized", shopping_items=["пятьдесят тысяч"]),
        ],
    )
    async def test_completes_with_50000(self, monkeypatch, response) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_360_001)
            purchase = await open_pending(session, user, ids, "voice")
            set_parser_override(FixedParser(response))
            bot = await feed(monkeypatch, session, user.telegram_id, **VOICE)
            tx = await session.scalar(select(Transaction))
            assert tx is not None and tx.amount == 50_000
            await session.refresh(purchase)
            assert purchase.status == "completed" and purchase.transaction_id == tx.id
            assert bot.sent[0].text == "Записал закупку: 50 000 сум."
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 0

    async def test_goods_in_pending_voice_still_unrecognized(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_360_002)
            purchase = await open_pending(session, user, ids, "voice")
            set_parser_override(
                FixedParser(ParseResponse(operations=[], speech_status="recognized", shopping_items=["сыр"], transcript="сыр"))
            )
            await feed(monkeypatch, session, user.telegram_id, **VOICE)
            await session.refresh(purchase)
            assert purchase.status == "unrecognized"
            assert await tx_count(session) == 0


class TestTextSpoken:
    @pytest.mark.parametrize("text", ["50 ming", "50 ming so'm", "ellik ming", "50к", "пятьдесят тысяч"])
    async def test_text_completes_without_model(self, monkeypatch, text) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_360_003)
            purchase = await open_pending(session, user, ids, "voice")
            parser = FixedParser(ParseResponse(operations=[]))
            set_parser_override(parser)
            bot = await feed(monkeypatch, session, user.telegram_id, text=text)
            tx = await session.scalar(select(Transaction))
            assert tx is not None and tx.amount == 50_000
            assert parser.calls == []
            await session.refresh(purchase)
            assert purchase.status == "completed"


async def test_app_view_after_bot_sum(monkeypatch) -> None:
    """What the app reads on return: purchase result, pending status, empty list, one expense."""
    from app.api.v1.shopping import _pending_status
    from app.services.shopping import get_own_purchase, get_purchase_result

    async with rollback_session() as session:
        user, budget, ids = await setup_family(session, 9_360_004)
        purchase = await open_pending(session, user, ids, "voice")
        set_parser_override(
            FixedParser(ParseResponse(operations=[], speech_status="recognized", transcript="50 ming"))
        )
        await feed(monkeypatch, session, user.telegram_id, **VOICE)
        status = _pending_status(await get_own_purchase(session, user, purchase.id))
        assert status.status == "completed" and status.amount == 50_000
        assert status.purchase_id == purchase.id
        result = await get_purchase_result(session, user, purchase.id)
        assert result.amount == 50_000 and result.items_recorded == 2 and result.items_left == 0 and result.transaction_id
        assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 0
        tx = await session.scalar(select(Transaction))
        assert tx.amount == 50_000 and tx.type == "expense" and tx.channel == "voice"
