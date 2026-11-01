"""AI usage accounting (W2) and the daily cost alert (W3). Contract: work/db/admin-schema.md.

Every function opens its OWN short transaction, so the shared per-day row is never touched while a
family lock is held or while we wait for the model. Nothing here ever raises into the caller.

Row semantics in ai_usage_daily (PK day, model, kind, outcome):
- a model request is one CALL (retries are separate calls): outcome ok | error, calls += 1,
  tokens/cost from the provider's usage fields; calls_no_usage counts answered requests that
  carried no usage (their cost is unknown, shown as incomplete);
- a bot MESSAGE that went to parsing is counted once: outcome ok | unparsed | error, messages += 1.
  Prefilter hits (no model) are messages of model 'prefilter'.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy import BigInteger, Date, Integer, String

from app import config
from app.db import async_session_factory
from app.services.activity import tashkent_today

logger = logging.getLogger(__name__)

# Tests that run inside a rolled-back transaction switch this off (tests/conftest.py).
TRACKING_ENABLED = True

_alert_claimed: set[date] = set()


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    audio_input_tokens: int = 0


def utcnow() -> datetime:
    return datetime.now(UTC)


def reset_state() -> None:
    _alert_claimed.clear()


def _nonneg_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def extract_usage(provider: str, body: Any) -> Usage | None:
    """Token counts from the provider's answer, or None when it carried none."""
    if not isinstance(body, dict):
        return None
    if provider == "openai":
        u = body.get("usage")
        if isinstance(u, dict) and ("prompt_tokens" in u or "completion_tokens" in u):
            return Usage(_nonneg_int(u.get("prompt_tokens")), _nonneg_int(u.get("completion_tokens")))
    elif provider == "anthropic":
        u = body.get("usage")
        if isinstance(u, dict) and ("input_tokens" in u or "output_tokens" in u):
            return Usage(_nonneg_int(u.get("input_tokens")), _nonneg_int(u.get("output_tokens")))
    elif provider == "google":
        u = body.get("usageMetadata")
        if isinstance(u, dict) and ("promptTokenCount" in u or "candidatesTokenCount" in u):
            audio = 0
            details = u.get("promptTokensDetails")
            if isinstance(details, list):
                for item in details:
                    if isinstance(item, dict) and item.get("modality") == "AUDIO":
                        audio += _nonneg_int(item.get("tokenCount"))
            prompt = _nonneg_int(u.get("promptTokenCount"))
            # Thinking tokens are billed as output.
            out = _nonneg_int(u.get("candidatesTokenCount")) + _nonneg_int(u.get("thoughtsTokenCount"))
            return Usage(prompt, out, min(audio, prompt))
    return None


def cost_micro_usd(usage: Usage | None) -> int:
    """USD per 1M tokens == micro-USD per token."""
    if usage is None:
        return 0
    audio_price = config.AI_PRICE_AUDIO_INPUT_USD_PER_1M
    audio = usage.audio_input_tokens if audio_price > 0 else 0
    cost = (
        (usage.input_tokens - audio) * config.AI_PRICE_INPUT_USD_PER_1M
        + audio * audio_price
        + usage.output_tokens * config.AI_PRICE_OUTPUT_USD_PER_1M
    )
    return round(cost)


def current_model() -> str:
    return (config.PARSER_MODEL or "unknown")[:64]


_UPSERT = text(
    """
    INSERT INTO ai_usage_daily AS u (day, model, kind, outcome, calls, calls_no_usage, messages,
                                     input_tokens, output_tokens, cost_micro_usd)
    VALUES (:day, :model, :kind, :outcome, :calls, :no_usage, :messages, :tin, :tout, :cost)
    ON CONFLICT (day, model, kind, outcome) DO UPDATE SET
      calls = u.calls + excluded.calls, calls_no_usage = u.calls_no_usage + excluded.calls_no_usage,
      messages = u.messages + excluded.messages, input_tokens = u.input_tokens + excluded.input_tokens,
      output_tokens = u.output_tokens + excluded.output_tokens,
      cost_micro_usd = u.cost_micro_usd + excluded.cost_micro_usd
    """
).bindparams(
    bindparam("day", type_=Date()),
    bindparam("model", type_=String()),
    bindparam("kind", type_=String()),
    bindparam("outcome", type_=String()),
    bindparam("calls", type_=Integer()),
    bindparam("no_usage", type_=Integer()),
    bindparam("messages", type_=Integer()),
    bindparam("tin", type_=BigInteger()),
    bindparam("tout", type_=BigInteger()),
    bindparam("cost", type_=BigInteger()),
)

_TODAY_COST = text("SELECT coalesce(sum(cost_micro_usd), 0) FROM ai_usage_daily WHERE day = :day").bindparams(
    bindparam("day", type_=Date())
)

_CLAIM = text(
    """
    INSERT INTO ai_cost_alerts (day, threshold_micro_usd, cost_micro_usd) VALUES (:day, :thr, :cost)
    ON CONFLICT (day) DO NOTHING RETURNING day
    """
).bindparams(
    bindparam("day", type_=Date()),
    bindparam("thr", type_=BigInteger()),
    bindparam("cost", type_=BigInteger()),
)


async def _upsert(
    day: date, model: str, kind: str, outcome: str, *, calls=0, no_usage=0, messages=0, tin=0, tout=0, cost=0
) -> None:
    async with async_session_factory() as session:
        await session.execute(
            _UPSERT,
            {"day": day, "model": model, "kind": kind, "outcome": outcome, "calls": calls,
             "no_usage": no_usage, "messages": messages, "tin": tin, "tout": tout, "cost": cost},
        )
        await session.commit()


async def record_call(
    model: str, kind: str, outcome: str, usage: Usage | None, *, answered: bool = False,
    now: datetime | None = None,
) -> None:
    """One request to the model. `answered`: an HTTP answer arrived (so missing usage is a gap in
    the cost, not a transport failure)."""
    if not TRACKING_ENABLED:
        return
    try:
        moment = now or utcnow()
        day = tashkent_today(moment)
        await _upsert(
            day, model[:64], kind, outcome, calls=1,
            no_usage=1 if usage is None and answered else 0,
            tin=usage.input_tokens if usage else 0, tout=usage.output_tokens if usage else 0,
            cost=cost_micro_usd(usage),
        )
    except Exception as exc:
        logger.warning("ai usage accounting failed: %s", type(exc).__name__)
        return
    await maybe_alert(day)


async def record_message(model: str | None, kind: str, outcome: str, *, now: datetime | None = None) -> None:
    """One bot message that went to parsing (ok | unparsed | error)."""
    if not TRACKING_ENABLED:
        return
    try:
        await _upsert(tashkent_today(now or utcnow()), (model or current_model())[:64], kind, outcome,
                      messages=1)
    except Exception as exc:
        logger.warning("ai usage accounting failed: %s", type(exc).__name__)


def alert_text(cost_micro: int, threshold_micro: int) -> str:
    return f"Расход на ИИ сегодня: ${cost_micro / 1_000_000:.2f} — выше порога ${threshold_micro / 1_000_000:.2f}."


def _get_bot():
    from aiogram import Bot

    return Bot(token=config.BOT_TOKEN)


async def maybe_alert(day: date) -> None:
    """W3. Own transaction; the unique mark per day decides who sends. Never raises."""
    try:
        threshold = round(config.ADMIN_AI_DAILY_COST_ALERT_USD * 1_000_000)
        if threshold <= 0 or day in _alert_claimed:
            return
        async with async_session_factory() as session:
            cost = int(await session.scalar(_TODAY_COST, {"day": day}) or 0)
            if cost < threshold:
                return
            claimed = await session.scalar(_CLAIM, {"day": day, "thr": threshold, "cost": cost})
            await session.commit()
        _alert_claimed.add(day)
        if claimed is None:
            return  # somebody else already alerted for this day
        await _notify_admins(alert_text(cost, threshold))
    except Exception as exc:
        logger.warning("ai cost alert failed: %s", type(exc).__name__)


async def _notify_admins(message: str) -> None:
    admins = sorted(config.ADMIN_TELEGRAM_IDS)
    if not admins:
        return
    bot = _get_bot()
    try:
        for chat_id in admins:
            try:
                await bot.send_message(chat_id, message)
            except Exception as exc:
                logger.warning("ai cost alert not delivered to an admin: %s", type(exc).__name__)
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass


def message_outcome(response: Any, kind: str) -> str:
    """Outcome of one parsed message: 'unparsed' = nothing usable (no amount anywhere, no shopping
    items, unrecognised speech, unreadable receipt); 'error' = the model's status field is missing
    (the user gets the model-failure reply)."""
    if kind == "voice":
        if response.speech_status is None:
            return "error"
        if response.speech_status == "not_recognized":
            return "unparsed"
    if kind == "photo":
        if response.receipt_status is None:
            return "error"
        if response.receipt_status == "unreadable":
            return "unparsed"
    has_amount = any(op.amount is not None for op in response.operations)
    return "ok" if has_amount or response.shopping_items else "unparsed"
