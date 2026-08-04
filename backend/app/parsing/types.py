from dataclasses import dataclass
from typing import Literal

OpType = Literal["expense", "income", "ambiguous", "transfer", "exchange"]


@dataclass(frozen=True)
class ParsedOperation:
    type: OpType
    amount: int | None
    currency: Literal["UZS", "USD"] | None
    wallet_hint: str | None
    category: str | None
    comment: str | None
    from_wallet_hint: str | None = None
    to_wallet_hint: str | None = None
    rate: int | None = None


@dataclass(frozen=True)
class ParseRequest:
    text: str
    wallet_names: list[str]
    expense_category_names: list[str]
    income_category_names: list[str]
    audio_base64: str | None = None
    audio_mime_type: str | None = None


@dataclass(frozen=True)
class ParseResponse:
    operations: list[ParsedOperation]
    speech_status: Literal["recognized", "not_recognized"] | None = None
    date_hint: str | None = None


class ParserUnavailable(Exception):
    """Parser could not complete after retries or is inactive."""


class ParserMalformed(Exception):
    """Request or response malformed; do not retry."""
