"""Rule-based prefilter for text quick entry before LLM parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.parsing.cascade_keywords import CASCADE_KEYWORDS
from app.parsing.types import ParsedOperation
from app.services.budget_seed import SEED_EXPENSE_CATEGORIES, SEED_INCOME_CATEGORIES

PrefilterReason = Literal[
    "transfer_signal",
    "multi_operation",
    "amount_not_singular",
    "no_category_match",
    "category_ambiguous",
    "wallet_ambiguous",
    "prefilter_disabled",
]

# Wallet transfer / exchange signals — conservative; doubt → fall through.
_TRANSFER_SIGNALS: tuple[str, ...] = (
    "с карты",
    "на карту",
    "на наличные",
    "с наличных",
    "переложил",
    "перевел",
    "перевела",
    "перевели",
    "обмен",
    "exchange",
    "по курсу",
)

_MULTI_OP_CONNECTORS: tuple[str, ...] = (" и ", " а также ")

_THOUSAND_RE = re.compile(
    r"(?P<num>\d[\d\s_]*)\s*(?:тысяч(?:а|и)?|тыс\.?)",
    re.IGNORECASE,
)
_PLAIN_AMOUNT_RE = re.compile(
    r"(?<!\d)(?P<num>\d[\d\s_]*)\s*"
    r"(?P<currency>сум|uzs|\$|usd|доллар(?:ов)?|долл\.?)?(?!\d)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PrefilterResult:
    operation: ParsedOperation | None
    reason: PrefilterReason | None  # set iff operation is None; None on hit


@dataclass(frozen=True)
class PrefilterCategory:
    id: object
    name: str
    translation_key: str | None
    parent_id: object | None


@dataclass(frozen=True)
class _ParsedAmount:
    value: int
    currency: Literal["UZS", "USD"] | None
    span: tuple[int, int]


@dataclass(frozen=True)
class _CategoryMatch:
    category: PrefilterCategory
    op_type: Literal["expense", "income"]
    term: str
    span: tuple[int, int]


def build_seed_name_by_key() -> dict[str, str]:
    seed: dict[str, str] = {}
    for name, key in SEED_INCOME_CATEGORIES:
        seed[key] = name
    for parent_name, (parent_key, sub_entries) in SEED_EXPENSE_CATEGORIES.items():
        seed[parent_key] = parent_name
        for sub_name, sub_key in sub_entries:
            seed[sub_key] = sub_name
    return seed


def _normalize_number(raw: str) -> int:
    digits = re.sub(r"[\s_]", "", raw)
    return int(digits)


def _parse_currency(token: str | None) -> Literal["UZS", "USD"] | None:
    if token is None:
        return None
    lowered = token.casefold()
    if lowered in ("$", "usd", "доллар", "долларов", "долл", "долл."):
        return "USD"
    if lowered in ("сум", "uzs"):
        return "UZS"
    return None


def _find_amounts(text: str) -> list[_ParsedAmount]:
    covered = [False] * len(text)
    amounts: list[_ParsedAmount] = []

    for match in _THOUSAND_RE.finditer(text):
        start, end = match.span()
        if any(covered[start:end]):
            continue
        value = _normalize_number(match.group("num")) * 1000
        amounts.append(_ParsedAmount(value=value, currency=None, span=(start, end)))
        for i in range(start, end):
            covered[i] = True

    for match in _PLAIN_AMOUNT_RE.finditer(text):
        start, end = match.span()
        if any(covered[start:end]):
            continue
        num_raw = match.group("num")
        if not num_raw.strip():
            continue
        value = _normalize_number(num_raw)
        currency = _parse_currency(match.group("currency"))
        amounts.append(_ParsedAmount(value=value, currency=currency, span=(start, end)))
        for i in range(start, end):
            covered[i] = True

    return amounts


def _has_transfer_signal(text: str) -> bool:
    folded = text.casefold()
    return any(signal in folded for signal in _TRANSFER_SIGNALS)


def _has_multi_op_signal(text: str, amounts: list[_ParsedAmount]) -> bool:
    if len(amounts) > 1:
        return True
    folded = f" {text.casefold()} "
    return any(connector in folded for connector in _MULTI_OP_CONNECTORS)


def _single_word_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term.casefold())
    return re.compile(
        rf"(?<![\w\u0400-\u04ff]){escaped}(?![\w\u0400-\u04ff])",
        re.IGNORECASE,
    )


def _find_term_spans(text: str, term: str) -> list[tuple[int, int]]:
    if re.search(r"[\s']", term):
        folded_text = text.casefold()
        folded_term = term.casefold()
        spans: list[tuple[int, int]] = []
        start = 0
        while True:
            idx = folded_text.find(folded_term, start)
            if idx == -1:
                break
            spans.append((idx, idx + len(folded_term)))
            start = idx + 1
        return spans

    return [match.span() for match in _single_word_pattern(term).finditer(text)]


def _matchable_terms(
    category: PrefilterCategory,
    seed_name_by_key: dict[str, str],
) -> list[str]:
    terms = [category.name]
    if category.translation_key is None:
        return terms
    seed_name = seed_name_by_key.get(category.translation_key)
    if seed_name is not None and category.name.casefold() == seed_name.casefold():
        terms.extend(CASCADE_KEYWORDS.get(category.translation_key, []))
    return terms


def _find_category_matches(
    text: str,
    categories: list[PrefilterCategory],
    op_type: Literal["expense", "income"],
    seed_name_by_key: dict[str, str],
) -> list[_CategoryMatch]:
    matches: list[_CategoryMatch] = []
    for category in categories:
        best: _CategoryMatch | None = None
        for term in _matchable_terms(category, seed_name_by_key):
            for span in _find_term_spans(text, term):
                candidate = _CategoryMatch(
                    category=category,
                    op_type=op_type,
                    term=term,
                    span=span,
                )
                if best is None or len(term) > len(best.term):
                    best = candidate
        if best is not None:
            matches.append(best)
    return matches


def _apply_subcategory_first(matches: list[_CategoryMatch]) -> list[_CategoryMatch]:
    sub_matches = [m for m in matches if m.category.parent_id is not None]
    if not sub_matches:
        return matches
    parent_ids_with_sub = {m.category.parent_id for m in sub_matches}
    return [
        m
        for m in matches
        if m.category.parent_id is not None or m.category.id not in parent_ids_with_sub
    ]


def _unique_categories(matches: list[_CategoryMatch]) -> list[_CategoryMatch]:
    after_sub = _apply_subcategory_first(matches)
    seen: set[tuple[str, Literal["expense", "income"]]] = set()
    unique: list[_CategoryMatch] = []
    for match in after_sub:
        key = (match.category.name, match.op_type)
        if key in seen:
            continue
        seen.add(key)
        unique.append(match)
    return unique


def _match_wallets(text: str, wallet_names: list[str]) -> list[str]:
    folded = text.casefold()
    matched: list[str] = []
    for name in wallet_names:
        if name.casefold() in folded:
            matched.append(name)
    return matched


def _build_comment(
    text: str,
    amount_span: tuple[int, int],
    category_spans: list[tuple[int, int]],
) -> str | None:
    remove_ranges = sorted([amount_span, *category_spans], key=lambda s: s[0], reverse=True)
    comment = text
    for start, end in remove_ranges:
        comment = comment[:start] + " " + comment[end:]
    cleaned = re.sub(r"\s+", " ", comment).strip(" ,.-")
    return cleaned or None


def try_prefilter(
    text: str,
    *,
    wallet_names: list[str],
    expense_categories: list[PrefilterCategory],
    income_categories: list[PrefilterCategory],
    seed_name_by_key: dict[str, str] | None = None,
) -> PrefilterResult:
    """Return one fully resolved op, or None to fall through to the LLM parser."""
    if not text.strip():
        return PrefilterResult(operation=None, reason="amount_not_singular")

    if _has_transfer_signal(text):
        return PrefilterResult(operation=None, reason="transfer_signal")

    amounts = _find_amounts(text)
    if _has_multi_op_signal(text, amounts):
        return PrefilterResult(operation=None, reason="multi_operation")
    if len(amounts) != 1:
        return PrefilterResult(operation=None, reason="amount_not_singular")

    amount = amounts[0]
    seeds = seed_name_by_key if seed_name_by_key is not None else build_seed_name_by_key()

    expense_matches = _find_category_matches(
        text, expense_categories, "expense", seeds
    )
    income_matches = _find_category_matches(
        text, income_categories, "income", seeds
    )
    resolved = _unique_categories(expense_matches + income_matches)

    if len(resolved) != 1:
        reason: PrefilterReason = (
            "no_category_match" if len(resolved) == 0 else "category_ambiguous"
        )
        return PrefilterResult(operation=None, reason=reason)

    match = resolved[0]
    wallet_hits = _match_wallets(text, wallet_names)
    if len(wallet_hits) > 1:
        return PrefilterResult(operation=None, reason="wallet_ambiguous")

    comment = _build_comment(text, amount.span, [match.span])

    return PrefilterResult(
        operation=ParsedOperation(
            type=match.op_type,
            amount=amount.value,
            currency=amount.currency,
            wallet_hint=wallet_hits[0] if wallet_hits else None,
            category=match.category.name,
            comment=comment,
        ),
        reason=None,
    )
