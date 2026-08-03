from __future__ import annotations

import re
from dataclasses import dataclass

from app.parsing.types import ParsedOperation

RATE_MARKER_RE = re.compile(
    r"(?:по\s+курсу)|(?:\bпо\b)",
    re.IGNORECASE | re.UNICODE,
)


@dataclass(frozen=True, slots=True)
class ExchangeRateRequired:
    """§8.3 refusal — cross-currency transfer/exchange without rate."""


def text_has_rate_marker(text: str) -> bool:
    return bool(RATE_MARKER_RE.search(text))


def effective_rate(op: ParsedOperation, source_text: str) -> int | None:
    rate = op.rate
    if rate is not None and rate > 0 and text_has_rate_marker(source_text):
        return rate
    return None


def needs_exchange_refusal(
    *,
    from_currency: str,
    to_currency: str,
    rate: int | None,
) -> bool:
    return from_currency != to_currency and rate is None
