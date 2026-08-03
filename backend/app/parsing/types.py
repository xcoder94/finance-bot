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


@dataclass(frozen=True)
class ParseResponse:
    operations: list[ParsedOperation]


class ParserUnavailable(Exception):
    """Parser could not complete after retries or is inactive."""


class ParserMalformed(Exception):
    """Request or response malformed; do not retry."""
