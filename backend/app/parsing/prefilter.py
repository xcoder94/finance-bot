"""Rule-based prefilter for text quick entry before LLM parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.parsing.cascade_keywords import CASCADE_KEYWORDS
from app.parsing.types import ParsedOperation
from app.services.display_name import build_seed_name_by_key, is_default_name

PrefilterReason = Literal[
    "transfer_signal",
    "multi_operation",
    "amount_not_singular",
    "no_category_match",
    "category_ambiguous",
    "wallet_ambiguous",
    "type_conflict",
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

# Direction verbs: the verb decides the operation type, not the category list.
_EXPENSE_VERBS: tuple[str, ...] = (
    "to'ladim",
    "toladim",
    "tuladim",
    "berdim",
    "qaytardim",
    "chiqim",
    "вернул",
    "вернула",
    "отдал",
    "отдала",
    "дал в долг",
    "дала в долг",
    "заплатил",
    "заплатила",
    "потратил",
    "потратила",
    "расход",
)
_INCOME_VERBS: tuple[str, ...] = (
    "kirim",
    "приход",
    "доход",
)
# Generic verbs ("bought/took/came/received") say nothing about direction on their
# own: "taksi oldim" is a purchase. They count as income only in a debt context.
_DEBT_INCOME_VERBS: tuple[str, ...] = (
    "oldim",
    "keldi",
    "взял",
    "взяла",
    "получил",
    "получила",
)
# Debt word only at the start of a word ("qarz*", "долг" + case ending): "надолго",
# "задолго", "долговечный" are not debt context.
_DEBT_RE = re.compile(
    r"(?<!\w)(?:qarz\w*|долг(?:а|у|ом|е|и|ов|ам|ами|ах)?(?!\w))",
    re.IGNORECASE,
)

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u02bc": "'", "\u02bb": "'", "\u2018": "'", "`": "'"})

_MULTI_OP_CONNECTORS: tuple[str, ...] = (" и ", " а также ")

# One number: either digit groups of exactly 3 after a first group of 1-3 digits
# ("20 000", "1 215 000", "20_000"; separator: space, nbsp, thin/narrow nbsp, "_"; never tab
# or newline) or plain digits. Separate numbers ("20000 2", "12 15000") are never glued.
# Whitelist of neighbours: an amount is well-formed only when the char before it is the text
# start, whitespace or one of ( [ « " ' , ; : and the char after the whole token (suffix
# included) is the text end, whitespace or one of . , ; : ! ? ) ] » " '. Anything else glued
# to the digits (letter, digit, "_", sign, multiplier look-alike) means "not an amount".
_NUM = r"\d{1,3}(?:[ \u00a0\u202f\u2009_]\d{3})+(?!\d)|\d+"
# Extra neighbours, nothing more: a dash/hyphen glued to a LETTER on its left is a separator
# ("такси-20000", "бензин-200 тыс"; a dash after a space or digit stays a sign); an emoji glued
# to the number counts as a space. Multiplication-like symbols (U+2715..2718, U+274C) are NOT emoji here.
_EMOJI = (
    "\u2600-\u2714\u2705\u2728\u2764\u2b50\u2b55\U0001f300-\U0001faff"
)
_BEFORE = (
    r"(?:(?<![^\s(\[\u00ab\"',;:])"
    r"|(?<=[^\W\d_][-\u2010\u2011\u2013\u2014])"
    r"|(?<=[" + _EMOJI + r"\ufe0f]))"
)
_AFTER = r"(?![^\s.,;:!?)\]\u00bb\"'" + _EMOJI + r"])"

_THOUSAND_RE = re.compile(
    _BEFORE + r"(?P<num>" + _NUM + r")\s*(?:тысяч(?:а|и)?|тыс\.?)" + _AFTER,
    re.IGNORECASE,
)
# Uzbek / short magnitude words after a number: "25 ming", "25 минг", "25k", "3 mln".
_THOUSAND_WORD_RE = re.compile(
    _BEFORE + r"(?P<num>" + _NUM + r")\s*(?:ming[^\W\d_]*|минг[^\W\d_]*|k|к)" + _AFTER,
    re.IGNORECASE,
)
_MILLION_WORD_RE = re.compile(
    _BEFORE + r"(?P<num>" + _NUM + r")\s*(?:million|mln|миллион(?:а|ов)?|млн)\.?" + _AFTER,
    re.IGNORECASE,
)
# "$20" / "кофе $20": currency sign glued before the number (not together with a suffix).
_PLAIN_AMOUNT_RE = re.compile(
    _BEFORE + r"(?P<cur_pre>\$)?(?P<num>" + _NUM + r")"
    r"(?:\s*(?P<currency>сум|uzs|\$|usd|доллар(?:ов|ы|а|ах)?|dollar(?:lar|ga|da|dan|ni)?(?![a-z])|долл\.?))?"
    + _AFTER,
    re.IGNORECASE,
)
_MAGNITUDE_TAIL_RE = re.compile(
    r"\s*(?:тыс|ming|минг|mln|million|млн|миллион|[kк](?![^\W\d_]))", re.IGNORECASE
)

# A bare number must never be accepted when a magnitude word or currency mark is attached to it
# (space or glued), whether or not that mark itself passed the neighbour check ("20 тыс-",
# "20 млн$", "20 k/день"): the mark then is not part of the amount and the sum would be wrong.
# Stems that may continue with letters ("тысячи", "dollarlar") vs. marks that may not ("сумма").
_ATTACHED_MARK_RE = re.compile(
    r"\s*(?:\$|(?:тыс|ming|минг|million|миллион|доллар|dollar|долл)"
    r"|(?:сум|uzs|usd|mln|млн|[kк])(?![^\W\d_]))",
    re.IGNORECASE,
)
# Same on the left: "$ 20" (currency sign before the number, space between).
_MARK_BEFORE_RE = re.compile(r"\$\s*$")


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


def _normalize_number(raw: str) -> int:
    digits = re.sub(r"[\s_]", "", raw)
    return int(digits)


def _parse_currency(token: str | None) -> Literal["UZS", "USD"] | None:
    if token is None:
        return None
    lowered = token.casefold()
    if lowered in ("$", "usd", "долл", "долл.") or lowered.startswith(("доллар", "dollar")):
        return "USD"
    if lowered in ("сум", "uzs"):
        return "UZS"
    return None


def _find_amounts(text: str, *, magnitude_words: bool = True) -> list[_ParsedAmount]:
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

    for pattern, factor in (
        ((_MILLION_WORD_RE, 1_000_000), (_THOUSAND_WORD_RE, 1000))
        if magnitude_words
        else ()
    ):
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(covered[start:end]):
                continue
            value = _normalize_number(match.group("num")) * factor
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
        if (not match.group("currency") and _ATTACHED_MARK_RE.match(text, end)) or (
            not match.group("cur_pre") and _MARK_BEFORE_RE.search(text, 0, start)
        ):
            continue
        value = _normalize_number(num_raw)
        currency = _parse_currency(match.group("currency"))
        if match.group("cur_pre"):
            # "$20 usd" is two currency marks, "$20 тыс" is a magnitude: not for the fast path.
            if match.group("currency") or _MAGNITUDE_TAIL_RE.match(text, end):
                continue
            currency = "USD"
        amounts.append(_ParsedAmount(value=value, currency=currency, span=(start, end)))
        for i in range(start, end):
            covered[i] = True

    return amounts


_DIGIT_RE = re.compile(r"\d")


def _all_digits_covered(text: str, amounts: list[_ParsedAmount]) -> bool:
    """Whitelist check: exactly one amount and every digit char of the text lies inside it.

    Any other digit (a second number, a count, "x2", "express24", "2по20000") means the
    phrase is not understood by the fast path and goes to the model.
    """
    if len(amounts) != 1:
        return False
    start, end = amounts[0].span
    return all(start <= m.start() < end for m in _DIGIT_RE.finditer(text))


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
    # Uzbek users type o'/g' with typographic marks or a backtick: compare with the plain apostrophe
    # (one char for one char, so spans still point into the original text).
    text = text.translate(_APOSTROPHES)
    term = term.translate(_APOSTROPHES)
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
    if is_default_name(category.name, category.translation_key, seed_name_by_key):
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


def _has_debt_context(text: str) -> bool:
    return _DEBT_RE.search(text.casefold()) is not None


def _is_debt_category(
    category: PrefilterCategory,
    by_id: dict[object, PrefilterCategory],
) -> bool:
    """The debt category itself (Qarz/Долг and variants) or any of its subcategories."""
    current: PrefilterCategory | None = category
    for _ in range(8):
        if current is None:
            return False
        if _has_debt_context(current.name):
            return True
        current = by_id.get(current.parent_id) if current.parent_id is not None else None
    return False


def _verb_type(
    text: str, *, include_generic: bool = True
) -> Literal["expense", "income", "conflict"] | None:
    """Direction implied by the verb; None if no verb; "conflict" if both kinds.

    include_generic=False ignores oldim/keldi/взял...: only explicit direction verbs.
    """
    normalized = text.translate(_APOSTROPHES)
    has_expense = any(_find_term_spans(normalized, v) for v in _EXPENSE_VERBS)
    has_income = any(_find_term_spans(normalized, v) for v in _INCOME_VERBS)
    if include_generic and not has_income and _has_debt_context(normalized):
        has_income = any(_find_term_spans(normalized, v) for v in _DEBT_INCOME_VERBS)
    if has_expense and has_income:
        return "conflict"
    if has_expense:
        return "expense"
    if has_income:
        return "income"
    return None


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
    cleaned = re.sub(r"\s+", " ", comment).strip(" ,.-\u2010\u2011\u2013\u2014")
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
    if not _all_digits_covered(text, amounts):
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

    verb_type = _verb_type(text)
    if verb_type == "conflict":
        return PrefilterResult(operation=None, reason="type_conflict")
    if verb_type is not None and len(resolved) == 2:
        # Same category name in both lists: the verb picks the list.
        by_type = [m for m in resolved if m.op_type == verb_type]
        if len(by_type) == 1 and resolved[0].category.name == resolved[1].category.name:
            resolved = by_type

    if not resolved and verb_type in ("expense", "income") and _has_debt_context(text):
        # Debt phrase ("qarzga oldim", "qarzni qaytardim"): verb decides, no category.
        debt_wallets = _match_wallets(text, wallet_names)
        if len(debt_wallets) > 1:
            return PrefilterResult(operation=None, reason="wallet_ambiguous")
        return PrefilterResult(
            operation=ParsedOperation(
                type=verb_type,
                amount=amount.value,
                currency=amount.currency,
                wallet_hint=debt_wallets[0] if debt_wallets else None,
                category=None,
                comment=_build_comment(text, amount.span, []),
            ),
            reason=None,
        )

    if len(resolved) != 1:
        reason: PrefilterReason = (
            "no_category_match" if len(resolved) == 0 else "category_ambiguous"
        )
        return PrefilterResult(operation=None, reason=reason)

    match = resolved[0]
    wallet_hits = _match_wallets(text, wallet_names)
    if len(wallet_hits) > 1:
        return PrefilterResult(operation=None, reason="wallet_ambiguous")

    generic_only = verb_type is not None and _verb_type(text, include_generic=False) != verb_type
    all_categories = {c.id: c for c in (*expense_categories, *income_categories)}
    if (
        verb_type is not None
        and verb_type != match.op_type
        and generic_only
        and not _is_debt_category(match.category, all_categories)
    ):
        # Credit purchase ("qarzga taksi oldim"): the generic verb does not override
        # an ordinary category, same as without the debt word.
        op_type = match.op_type
        category_name = match.category.name
        comment = _build_comment(text, amount.span, [match.span])
    elif verb_type is not None and verb_type != match.op_type:
        # Verb contradicts the category's type: the verb wins, category dropped
        # (it stays in the comment text).
        op_type: Literal["expense", "income"] = verb_type
        category_name: str | None = None
        comment = _build_comment(text, amount.span, [])
    else:
        op_type = match.op_type
        category_name = match.category.name
        comment = _build_comment(text, amount.span, [match.span])

    return PrefilterResult(
        operation=ParsedOperation(
            type=op_type,
            amount=amount.value,
            currency=amount.currency,
            wallet_hint=wallet_hits[0] if wallet_hits else None,
            category=category_name,
            comment=comment,
        ),
        reason=None,
    )
