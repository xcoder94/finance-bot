"""a-2 backend-b: AI usage accounting (W2), cost alert (W3), usage.ai block.

Only the network answer of the model (httpx.MockTransport) and the Telegram network are replaced.
The aggregate is written by the real code into real Postgres.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

import httpx
import pytest
from sqlalchemy import delete, func, select

from app.models.admin_tracking import AiCostAlert, AiUsageDaily
from app.parsing.http_adapter import HttpParser
from app.parsing.types import ParseRequest, ParseResponse, ParserMalformed, ParserUnavailable
from app.services import ai_usage
from bot.quick_entry.handlers import set_parser_override
from tests.admin_helpers import FORBIDDEN_KEY_PARTS, make_admin, make_user, utc, walk_keys
from tests.test_a1_admin_overview import pytestmark  # noqa: F401
from tests.test_telegram_auth import _AsyncSessionFactoryOverride
from tests.test_wallets_categories import api_client, auth_headers  # noqa: F401

NOW = utc(2026, 6, 15, 7)  # 12:00 Tashkent 15 June
TODAY = date(2026, 6, 15)
OP = {"type": "expense", "amount": 25000, "currency": "UZS", "wallet_hint": None,
      "category": None, "comment": None, "from_wallet_hint": None, "to_wallet_hint": None,
      "rate": None}
GOOD_TEXT = json.dumps({"operations": [OP], "speech_status": "recognized", "receipt_status": "ok"})
REQ = ParseRequest(text="такси 25000", wallet_names=[], expense_category_names=[],
                   income_category_names=[])
AUDIO_REQ = ParseRequest(text="", wallet_names=[], expense_category_names=[],
                         income_category_names=[], audio_base64="QQ==", audio_mime_type="audio/ogg")
IMAGE_REQ = ParseRequest(text="", wallet_names=[], expense_category_names=[],
                         income_category_names=[], image_base64="QQ==", image_mime_type="image/jpeg")


def google_body(text: str = GOOD_TEXT, usage: dict | None = None) -> dict:
    body: dict = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    if usage is not None:
        body["usageMetadata"] = usage
    return body


@pytest.fixture
def prices(monkeypatch):
    from app import config

    monkeypatch.setattr(config, "AI_PRICE_INPUT_USD_PER_1M", 0.30)
    monkeypatch.setattr(config, "AI_PRICE_OUTPUT_USD_PER_1M", 2.50)
    monkeypatch.setattr(config, "AI_PRICE_AUDIO_INPUT_USD_PER_1M", 1.00)
    monkeypatch.setattr(config, "ADMIN_AI_DAILY_COST_ALERT_USD", 0.0)
    monkeypatch.setattr(config, "PARSER_MODEL", "gemini-test")


def usage_on(monkeypatch, session) -> None:
    monkeypatch.setattr(ai_usage, "TRACKING_ENABLED", True)
    monkeypatch.setattr(ai_usage, "async_session_factory", _AsyncSessionFactoryOverride(session))
    monkeypatch.setattr(ai_usage, "utcnow", lambda: NOW)
    ai_usage.reset_state()


async def run_parser(handler, request=REQ, provider="google", model="gemini-test"):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await HttpParser(provider, "key", model, client=client).parse(request)


async def rows(session) -> dict[tuple[str, str, str], AiUsageDaily]:
    await session.flush()
    found = (await session.scalars(select(AiUsageDaily).where(AiUsageDaily.day == TODAY))).all()
    return {(r.model, r.kind, r.outcome): r for r in found}


# ---- W2: every model request is one call ------------------------------------------------------


async def test_ok_call_with_usage_records_tokens_and_cost(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    usage_on(monkeypatch, session)
    await run_parser(lambda r: httpx.Response(200, json=google_body(
        usage={"promptTokenCount": 1000, "candidatesTokenCount": 200})))
    row = (await rows(session))[("gemini-test", "text", "ok")]
    assert (row.calls, row.calls_no_usage, row.input_tokens, row.output_tokens) == (1, 0, 1000, 200)
    assert row.cost_micro_usd == 800  # 1000 * 0.30 + 200 * 2.50 micro-USD


async def test_call_without_usage_is_counted_but_flagged(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    usage_on(monkeypatch, session)
    await run_parser(lambda r: httpx.Response(200, json=google_body()))
    row = (await rows(session))[("gemini-test", "text", "ok")]
    assert (row.calls, row.calls_no_usage, row.input_tokens, row.output_tokens, row.cost_micro_usd) == (
        1, 1, 0, 0, 0)


async def test_google_thinking_tokens_are_output_and_audio_has_its_own_price(
    api_client, monkeypatch, prices
) -> None:
    _, session = api_client
    usage_on(monkeypatch, session)
    meta = {"promptTokenCount": 1000, "candidatesTokenCount": 100, "thoughtsTokenCount": 100,
            "promptTokensDetails": [{"modality": "AUDIO", "tokenCount": 600},
                                    {"modality": "TEXT", "tokenCount": 400}]}
    await run_parser(lambda r: httpx.Response(200, json=google_body(usage=meta)), AUDIO_REQ)
    row = (await rows(session))[("gemini-test", "voice", "ok")]
    assert (row.input_tokens, row.output_tokens) == (1000, 200)
    assert row.cost_micro_usd == 600 * 1.0 + 400 * 0.30 + 200 * 2.50  # 1220


async def test_image_request_is_kind_photo(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    usage_on(monkeypatch, session)
    await run_parser(lambda r: httpx.Response(200, json=google_body(
        usage={"promptTokenCount": 10, "candidatesTokenCount": 1})), IMAGE_REQ)
    assert ("gemini-test", "photo", "ok") in await rows(session)


@pytest.mark.parametrize(
    "provider,body",
    [
        ("openai", {"choices": [{"message": {"content": GOOD_TEXT}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 10}}),
        ("anthropic", {"content": [{"text": GOOD_TEXT}],
                       "usage": {"input_tokens": 100, "output_tokens": 10}}),
    ],
)
async def test_usage_fields_of_other_providers(api_client, monkeypatch, prices, provider, body) -> None:
    _, session = api_client
    usage_on(monkeypatch, session)
    await run_parser(lambda r: httpx.Response(200, json=body), provider=provider, model="m1")
    row = (await rows(session))[("m1", "text", "ok")]
    assert (row.input_tokens, row.output_tokens, row.cost_micro_usd) == (100, 10, 55)


async def test_retry_is_two_calls_one_error_one_ok(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    usage_on(monkeypatch, session)
    answers = iter([httpx.Response(503), httpx.Response(200, json=google_body(
        usage={"promptTokenCount": 10, "candidatesTokenCount": 1}))])
    await run_parser(lambda r: next(answers))
    got = await rows(session)
    assert got[("gemini-test", "text", "error")].calls == 1
    assert got[("gemini-test", "text", "error")].calls_no_usage == 0  # transport failure is not "no usage"
    assert got[("gemini-test", "text", "ok")].calls == 1


async def test_timeouts_are_error_calls_and_still_raise(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    usage_on(monkeypatch, session)

    def boom(request):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ParserUnavailable):
        await run_parser(boom)
    row = (await rows(session))[("gemini-test", "text", "error")]
    assert (row.calls, row.cost_micro_usd) == (3, 0)
    assert ("gemini-test", "text", "ok") not in await rows(session)


async def test_garbage_answer_is_error_but_tokens_are_billed(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    usage_on(monkeypatch, session)
    with pytest.raises(ParserMalformed):
        await run_parser(lambda r: httpx.Response(200, json=google_body(
            text="not json", usage={"promptTokenCount": 1000, "candidatesTokenCount": 0})))
    row = (await rows(session))[("gemini-test", "text", "error")]
    assert (row.calls, row.input_tokens, row.cost_micro_usd) == (1, 1000, 300)


@pytest.mark.parametrize("provider,body", [
    ("google", {"candidates": ["x"]}),
    ("google", {"candidates": [{"content": ["x"]}]}),
    ("google", ["top", "level", "array"]),
    ("google", "just a string"),
    ("openai", {"choices": ["x"]}),
    ("openai", [1, 2]),
    ("anthropic", {"content": ["x"]}),
    ("anthropic", [1]),
])
async def test_valid_json_of_unexpected_shape_is_a_counted_error_not_a_crash(
    api_client, monkeypatch, prices, provider, body
) -> None:
    _, session = api_client
    usage_on(monkeypatch, session)
    with pytest.raises(ParserMalformed):
        await run_parser(lambda r: httpx.Response(200, json=body), provider=provider)
    row = (await rows(session))[("gemini-test", "text", "error")]
    assert row.calls == 1


async def test_unexpected_shape_gives_the_user_the_usual_reply(monkeypatch, prices) -> None:
    from tests.test_m3_4_bot_pending import feed, setup_family
    from tests.test_quick_entry_flow import rollback_session

    async with rollback_session() as session:
        usage_on(monkeypatch, session)
        user, _, _ = await setup_family(session, 9_530_010)

        async def handler(request):
            return httpx.Response(200, json={"candidates": ["x"]})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        set_parser_override(HttpParser("google", "key", "gemini-test", client=client))
        bot = await feed(monkeypatch, session, user.telegram_id, text="такси 30000")
        got = await rows(session)
        set_parser_override(None)
        await client.aclose()
    assert got[("gemini-test", "text", "error")].calls == 1
    assert got[("gemini-test", "text", "error")].messages == 1
    assert bot.sent, "the user must get a reply"


async def test_accounting_failure_never_breaks_parsing(monkeypatch, prices) -> None:
    class Broken:
        def __call__(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(ai_usage, "TRACKING_ENABLED", True)
    monkeypatch.setattr(ai_usage, "async_session_factory", Broken())
    ai_usage.reset_state()
    parsed = await run_parser(lambda r: httpx.Response(200, json=google_body()))
    assert parsed.operations[0].amount == 25000


# ---- messages / unparsed ----------------------------------------------------------------------


async def test_bot_messages_are_counted_by_outcome(monkeypatch, prices) -> None:
    from tests.test_m3_4_bot_pending import FixedParser, expense, feed, setup_family  # noqa: F401
    from tests.test_quick_entry_flow import rollback_session

    async with rollback_session() as session:
        usage_on(monkeypatch, session)
        user, _, _ = await setup_family(session, 9_530_001)
        set_parser_override(FixedParser(ParseResponse(operations=[expense(25_000)])))
        await feed(monkeypatch, session, user.telegram_id, text="такси 25000")
        set_parser_override(FixedParser(ParseResponse(operations=[])))
        await feed(monkeypatch, session, user.telegram_id, text="привет как дела")

        class Failing:
            async def parse(self, request):
                raise ParserUnavailable("down")

        set_parser_override(Failing())
        await feed(monkeypatch, session, user.telegram_id, text="такси 30000")
        got = await rows(session)
        set_parser_override(None)
    assert got[("gemini-test", "text", "ok")].messages == 1
    assert got[("gemini-test", "text", "unparsed")].messages == 1
    assert got[("gemini-test", "text", "error")].messages == 1
    assert all(r.calls == 0 for r in got.values())  # FixedParser makes no HTTP call


async def test_message_with_only_shopping_items_is_ok_not_unparsed(monkeypatch, prices) -> None:
    from tests.test_m3_4_bot_pending import FixedParser, feed, setup_family
    from tests.test_quick_entry_flow import rollback_session

    async with rollback_session() as session:
        usage_on(monkeypatch, session)
        user, _, _ = await setup_family(session, 9_530_011)
        set_parser_override(FixedParser(ParseResponse(operations=[], shopping_items=["молоко", "хлеб"])))
        await feed(monkeypatch, session, user.telegram_id, text="купить молоко и хлеб")
        got = await rows(session)
        set_parser_override(None)
    assert got[("gemini-test", "text", "ok")].messages == 1
    assert ("gemini-test", "text", "unparsed") not in got


def test_message_outcome_shopping_items_only_is_ok() -> None:
    assert ai_usage.message_outcome(ParseResponse(operations=[], shopping_items=["x"]), "text") == "ok"
    assert ai_usage.message_outcome(ParseResponse(operations=[]), "text") == "unparsed"


async def test_prefilter_hit_is_a_message_without_a_call(monkeypatch, prices) -> None:
    from tests.test_m3_4_bot_pending import FixedParser, feed, setup_family
    from tests.test_quick_entry_flow import rollback_session

    async with rollback_session() as session:
        usage_on(monkeypatch, session)
        user, _, _ = await setup_family(session, 9_530_002)
        fixed = FixedParser(ParseResponse(operations=[]))
        set_parser_override(fixed)  # a prefilter miss must never reach a network
        await feed(monkeypatch, session, user.telegram_id, text="продукты 25000")
        got = await rows(session)
        set_parser_override(None)
    assert fixed.calls == []
    row = got[("prefilter", "text", "ok")]
    assert (row.messages, row.calls) == (1, 0)


async def test_voice_and_photo_messages_are_counted(monkeypatch, prices) -> None:
    from tests.test_m3_4_bot_pending import PHOTO, VOICE, FixedParser, expense, feed, setup_family
    from tests.test_quick_entry_flow import rollback_session

    async with rollback_session() as session:
        usage_on(monkeypatch, session)
        user, _, _ = await setup_family(session, 9_530_003)
        set_parser_override(FixedParser(ParseResponse(operations=[], speech_status="not_recognized")))
        await feed(monkeypatch, session, user.telegram_id, **VOICE)
        set_parser_override(FixedParser(ParseResponse(operations=[expense(5000)], speech_status="recognized")))
        await feed(monkeypatch, session, user.telegram_id, **VOICE)
        from bot.quick_entry.receipt_photo import set_receipt_parser_override

        set_receipt_parser_override(FixedParser(ParseResponse(operations=[], receipt_status="unreadable")))
        await feed(monkeypatch, session, user.telegram_id, **PHOTO)
        got = await rows(session)
        set_parser_override(None)
        set_receipt_parser_override(None)
    assert got[("gemini-test", "voice", "unparsed")].messages == 1
    assert got[("gemini-test", "voice", "ok")].messages == 1
    assert got[("gemini-test", "photo", "unparsed")].messages == 1


# ---- W3: alert --------------------------------------------------------------------------------


class AlertBot:
    def __init__(self, fail_for: set[int] | None = None) -> None:
        self.sent: list[tuple[int, str]] = []
        self.fail_for = fail_for or set()

    async def send_message(self, chat_id, text, **kw):
        if chat_id in self.fail_for:
            raise RuntimeError("blocked")
        self.sent.append((chat_id, text))

    class session:  # noqa: N801
        @staticmethod
        async def close() -> None:
            return None


def alert_on(monkeypatch, session, *, threshold_usd=0.001, admins=(111, 222), bot=None):
    from app import config

    usage_on(monkeypatch, session)
    bot = bot or AlertBot()
    monkeypatch.setattr(config, "ADMIN_AI_DAILY_COST_ALERT_USD", threshold_usd)
    monkeypatch.setattr(config, "ADMIN_TELEGRAM_IDS", frozenset(admins))
    monkeypatch.setattr(ai_usage, "_get_bot", lambda: bot)
    return bot


async def one_call(tokens_in=1000, tokens_out=200):
    await run_parser(lambda r: httpx.Response(200, json=google_body(
        usage={"promptTokenCount": tokens_in, "candidatesTokenCount": tokens_out})))


async def test_alert_once_per_admin_when_threshold_crossed(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    bot = alert_on(monkeypatch, session, threshold_usd=0.001)  # 1000 micro
    await one_call()  # 800 micro: below
    assert bot.sent == []
    await one_call()  # 1600 micro: crossed
    assert sorted(chat for chat, _ in bot.sent) == [111, 222]
    text = bot.sent[0][1]
    assert text == "Расход на ИИ сегодня: $0.00 — выше порога $0.00."
    await one_call()  # same day again: no new message
    assert len(bot.sent) == 2
    stored = (await session.scalars(select(AiCostAlert).where(AiCostAlert.day == TODAY))).all()
    assert [(a.threshold_micro_usd, a.cost_micro_usd) for a in stored] == [(1000, 1600)]


async def test_alert_fires_when_cost_equals_the_threshold_exactly(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    bot = alert_on(monkeypatch, session, threshold_usd=0.0008)  # 800 micro
    await one_call()  # 1000*0.30 + 200*2.50 = 800 micro: exactly the threshold
    assert sorted(chat for chat, _ in bot.sent) == [111, 222]


async def test_alert_text_shows_dollars(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    bot = alert_on(monkeypatch, session, threshold_usd=5.0, admins=(111,))
    await one_call(tokens_in=20_000_000, tokens_out=0)  # $6.00
    assert bot.sent == [(111, "Расход на ИИ сегодня: $6.00 — выше порога $5.00.")]


async def test_alert_threshold_zero_or_unset_sends_nothing(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    bot = alert_on(monkeypatch, session, threshold_usd=0.0)
    await one_call(tokens_in=20_000_000, tokens_out=0)
    assert bot.sent == []
    assert (await session.scalar(select(func.count()).select_from(AiCostAlert))) == 0


async def test_alert_new_day_can_fire_again(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    bot = alert_on(monkeypatch, session, threshold_usd=0.0005, admins=(111,))
    await one_call()
    assert len(bot.sent) == 1
    monkeypatch.setattr(ai_usage, "utcnow", lambda: utc(2026, 6, 16, 7))
    await one_call()
    assert len(bot.sent) == 2


async def test_alert_delivery_failure_is_logged_not_raised(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    bot = alert_on(monkeypatch, session, threshold_usd=0.0005, bot=AlertBot(fail_for={111}))
    await one_call()  # must not raise
    assert [chat for chat, _ in bot.sent] == [222]  # the second admin still gets it


async def test_alert_cost_is_summed_across_models_and_kinds(api_client, monkeypatch, prices) -> None:
    _, session = api_client
    bot = alert_on(monkeypatch, session, threshold_usd=0.0012, admins=(111,))
    await one_call()  # 800 text
    await run_parser(lambda r: httpx.Response(200, json=google_body(
        usage={"promptTokenCount": 1000, "candidatesTokenCount": 200})), AUDIO_REQ, model="other")
    assert len(bot.sent) == 1


async def test_two_parallel_crossings_send_one_message_per_admin(monkeypatch, prices) -> None:
    """Real, separately committed sessions: the unique mark decides who sends."""
    from app.db import async_session_factory
    from tests.test_wallets_categories import _reset_engine

    await _reset_engine()
    day_now = utc(2020, 1, 2, 7)
    bot = AlertBot()
    from app import config

    monkeypatch.setattr(config, "ADMIN_AI_DAILY_COST_ALERT_USD", 0.0005)
    monkeypatch.setattr(config, "ADMIN_TELEGRAM_IDS", frozenset({111}))
    monkeypatch.setattr(ai_usage, "TRACKING_ENABLED", True)
    monkeypatch.setattr(ai_usage, "_get_bot", lambda: bot)
    ai_usage.reset_state()
    try:
        await asyncio.gather(
            *[ai_usage.record_call("gemini-test", "text", "ok", ai_usage.Usage(1000, 200), now=day_now)
              for _ in range(4)]
        )
        assert len(bot.sent) == 1
    finally:
        async with async_session_factory() as s:
            await s.execute(delete(AiCostAlert).where(AiCostAlert.day == date(2020, 1, 2)))
            await s.execute(delete(AiUsageDaily).where(AiUsageDaily.day == date(2020, 1, 2)))
            await s.commit()
        await _reset_engine()


# ---- /api/v1/admin/usage -> ai ----------------------------------------------------------------


async def put(session, outcome, *, kind="text", model="m", day=TODAY, calls=0, no_usage=0, messages=0,
              tin=0, tout=0, cost=0) -> None:
    session.add(AiUsageDaily(day=day, model=model, kind=kind, outcome=outcome, calls=calls,
                             calls_no_usage=no_usage, messages=messages, input_tokens=tin,
                             output_tokens=tout, cost_micro_usd=cost))
    await session.flush()


async def usage_client(api_client, monkeypatch):
    client, session = api_client
    admin = await make_user(session, created_at=utc(2026, 1, 1))
    make_admin(monkeypatch, admin.telegram_id)
    monkeypatch.setattr("app.api.v1.admin.utcnow", lambda: NOW)
    headers = auth_headers(admin.telegram_id)

    async def get(period="day"):
        resp = await client.get("/api/v1/admin/usage", params={"period": period}, headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    return client, session, headers, get


async def test_usage_ai_block_matches_fixture(api_client, monkeypatch) -> None:
    from app import config

    monkeypatch.setattr(config, "ADMIN_AI_DAILY_COST_ALERT_USD", 2.0)
    _, session, _, get = await usage_client(api_client, monkeypatch)
    # today: 10 ok messages (11 calls: one retry error), 2 unparsed, 1 error message
    await put(session, "ok", calls=10, no_usage=1, messages=10, tin=9000, tout=900, cost=3_000_000)
    await put(session, "error", calls=4, messages=1)  # 4 failed calls, 1 failed message
    await put(session, "unparsed", messages=2)
    await put(session, "ok", day=date(2026, 6, 10), calls=5, messages=5, tin=1000, tout=100, cost=500_000)
    await put(session, "ok", day=date(2026, 5, 1), calls=99, messages=99, cost=9_000_000)  # outside month
    day = (await get("day"))["ai"]
    assert day == {
        "calls": 14, "error_calls": 4, "calls_without_usage": 1, "cost_incomplete": True,
        "cost_today_incomplete": True,
        "input_tokens": 9000, "output_tokens": 900, "cost_usd": 3.0,
        "messages": 13, "unparsed": 2, "errors": 1,
        "threshold_usd": 2.0, "cost_today_usd": 3.0,
    }
    week = (await get("week"))["ai"]
    assert (week["calls"], week["cost_usd"], week["messages"], week["cost_today_usd"]) == (19, 3.5, 18, 3.0)
    month = (await get("month"))["ai"]
    assert month["calls"] == 19  # 1 May is 45 days back


async def test_cost_today_incomplete_looks_at_today_only(api_client, monkeypatch) -> None:
    _, session, _, get = await usage_client(api_client, monkeypatch)
    await put(session, "ok", calls=3, no_usage=0, messages=3, cost=1_000)  # today: all with tokens
    await put(session, "ok", day=date(2026, 6, 14), calls=2, no_usage=2, messages=2)  # yesterday: gap
    day = (await get("day"))["ai"]
    week = (await get("week"))["ai"]
    assert (day["cost_incomplete"], day["cost_today_incomplete"]) == (False, False)
    assert (week["cost_incomplete"], week["cost_today_incomplete"]) == (True, False)
    await put(session, "error", calls=1, no_usage=1)  # today now has a gap
    for period in ("day", "week", "month"):
        ai = (await get(period))["ai"]
        assert (ai["cost_incomplete"], ai["cost_today_incomplete"]) == (True, True)


@pytest.mark.parametrize("period,days", [("day", 1), ("week", 7), ("month", 30)])
async def test_ai_window_is_exactly_n_tashkent_days_including_today(
    api_client, monkeypatch, period, days
) -> None:
    from datetime import timedelta

    _, session, _, get = await usage_client(api_client, monkeypatch)
    await put(session, "ok", day=TODAY - timedelta(days=days - 1), calls=1, messages=1)  # oldest inside
    await put(session, "ok", day=TODAY - timedelta(days=days), calls=100, messages=100)  # one day outside
    ai = (await get(period))["ai"]
    assert (ai["calls"], ai["messages"]) == (1, 1)


async def test_usage_ai_empty_and_no_threshold(api_client, monkeypatch) -> None:
    from app import config

    monkeypatch.setattr(config, "ADMIN_AI_DAILY_COST_ALERT_USD", 0.0)
    _, _, _, get = await usage_client(api_client, monkeypatch)
    ai = (await get("day"))["ai"]
    assert ai["calls"] == 0 and ai["cost_usd"] == 0 and ai["threshold_usd"] is None
    assert ai["cost_incomplete"] is False and ai["cost_today_usd"] == 0
    assert ai["cost_today_incomplete"] is False


async def test_usage_ai_is_private_and_still_guarded(api_client, monkeypatch) -> None:
    client, session, headers, get = await usage_client(api_client, monkeypatch)
    await put(session, "ok", model="secret-model-name", calls=1, messages=1, cost=10)
    body = await get("day")
    for key in walk_keys(body):
        assert not any(part in key for part in FORBIDDEN_KEY_PARTS), key
    assert "secret-model-name" not in json.dumps(body)  # no model names / keys
    assert (await client.get("/api/v1/admin/usage")).status_code == 401
    stranger = await make_user(session, created_at=utc(2026, 1, 1))
    resp = await client.get("/api/v1/admin/usage", headers=auth_headers(stranger.telegram_id))
    assert resp.status_code == 404
