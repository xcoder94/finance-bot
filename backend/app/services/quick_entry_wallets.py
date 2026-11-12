from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.wallet import Wallet

SHARED_WALLET_LIMIT = 10


@dataclass(frozen=True, slots=True)
class CurrencyMissing:
    currency: Literal["UZS", "USD"]


_APOSTROPHES = str.maketrans(
    {"\u2019": "'", "\u02bb": "'", "\u02bc": "'", "\u2018": "'", "`": "'", "\u00b4": "'"}
)
_WORD_RE = re.compile(r"[\w']+", re.UNICODE)
_USD_PREFIXES = ("доллар", "dollar", "usd")
_UZS_WORDS = {"сум", "сумы", "сумов", "сумм", "сума", "сўм", "сум.", "so'm", "som", "sum", "uzs"}
# Currency words and nothing else: they are shared by most wallets, so they never pick one.
_CURRENCY_TOKENS = {"usd", "uzs"}
_CONNECTORS = {"с", "со", "из", "на", "в", "по", "от", "за"}


def _canon(token: str) -> str:
    if token.startswith(_USD_PREFIXES) or token == "$":
        return "usd"
    if token in _UZS_WORDS:
        return "uzs"
    return token


def _tokens(text: str) -> list[str]:
    folded = text.translate(_APOSTROPHES).casefold()
    return [_canon(t.strip("'")) for t in _WORD_RE.findall(folded) if t.strip("'")]


def _same_word(a: str, b: str) -> bool:
    """Equal, or one is the other with a case/suffix ending (karta/kartadan, наличный/наличные)."""
    if a == b:
        return True
    shortest = min(len(a), len(b))
    if shortest < 4:
        return False
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    return common >= max(4, shortest - 2)


def _has_word(tokens: list[str], word: str) -> bool:
    return any(_same_word(t, word) for t in tokens)


def pick_wallet_by_hint(
    wallets: list[Wallet],
    hint: str | None,
    *,
    exclude: Wallet | None = None,
    currency: str | None = None,
) -> Wallet | None:
    """The wallet the phrase names, or None (not named, or not unambiguous).

    Order: the whole name; then every word of a name present in the phrase (longest name
    wins); then a word that only this wallet has. Currency words and words shared by several
    wallets (a name part like "Карта" when there are two cards) never select by themselves.
    """
    if not hint:
        return None
    hint_tokens = _tokens(hint)
    if not hint_tokens:
        return None
    named = [(w, _tokens(w.name)) for w in wallets]
    allowed = [(w, toks) for w, toks in named if exclude is None or w.id != exclude.id]

    exact = [w for w, toks in allowed if toks and toks == hint_tokens]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None

    whole = [
        (w, toks)
        for w, toks in allowed
        if toks
        and any(t not in _CURRENCY_TOKENS for t in toks)
        and all(_has_word(hint_tokens, t) for t in toks)
    ]
    if whole:
        longest = max(len(toks) for _, toks in whole)
        top = [w for w, toks in whole if len(toks) == longest]
        return top[0] if len(top) == 1 else None

    found: list[Wallet] = []
    shared: list[Wallet] = []
    for w, toks in allowed:
        others = [t for o, ot in named if o.id != w.id for t in ot]
        own = [
            t
            for t in toks
            if t not in _CURRENCY_TOKENS and not _has_word(others, t)
        ]
        if any(_has_word(hint_tokens, t) for t in own):
            found.append(w)
        if any(t not in _CURRENCY_TOKENS and _has_word(hint_tokens, t) for t in toks):
            shared.append(w)
    if len(found) == 1:
        return found[0]
    if not found and currency is not None:
        # "карта" with a card per currency: the operation's currency decides, if it leaves one
        in_currency = [w for w in shared if w.currency == currency]
        if len(in_currency) == 1:
            return in_currency[0]
    return None


def wallet_matches_hint(hint: str, wallet_name: str) -> bool:
    """Kept for callers that compare one name: whole-name match only."""
    name_tokens = _tokens(wallet_name)
    hint_tokens = _tokens(hint)
    return bool(name_tokens) and all(_has_word(hint_tokens, t) for t in name_tokens)


def strip_wallet_mention(
    comment: str | None, wallet_name: str, hint: str | None
) -> str | None:
    """Drop the wallet's name / the phrase that named it from a comment."""
    if not comment:
        return comment
    result = comment
    for phrase in filter(None, (wallet_name, hint)):
        pattern = r"\s*".join(re.escape(p) for p in phrase.split())
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    words = result.split()
    while words and words[0].casefold() in _CONNECTORS:
        words.pop(0)
    while words and words[-1].casefold() in _CONNECTORS:
        words.pop()
    cleaned = " ".join(words).strip(" ,.-")
    return cleaned or None


async def list_wallets_for_parse(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    writer: User,
) -> list[Wallet]:
    shared_stmt = (
        select(Wallet)
        .where(
            Wallet.family_budget_id == family_budget_id,
            Wallet.is_deleted.is_(False),
            Wallet.is_personal.is_(False),
        )
        .order_by(Wallet.created_at)
        .limit(SHARED_WALLET_LIMIT)
    )
    personal_stmt = select(Wallet).where(
        Wallet.family_budget_id == family_budget_id,
        Wallet.is_deleted.is_(False),
        Wallet.is_personal.is_(True),
        Wallet.owner_user_id == writer.id,
    ).order_by(Wallet.created_at)
    shared = list((await session.scalars(shared_stmt)).all())
    personal = list((await session.scalars(personal_stmt)).all())
    return shared + personal


def _pick_wallet_by_hint(
    wallets: list[Wallet],
    wallet_hint: str | None,
    default_wallet: Wallet,
    currency: str | None = None,
) -> Wallet:
    return pick_wallet_by_hint(wallets, wallet_hint, currency=currency) or default_wallet


def _find_wallet_in_currency(
    wallets: list[Wallet],
    currency: Literal["UZS", "USD"],
) -> Wallet | None:
    for wallet in wallets:
        if wallet.currency == currency:
            return wallet
    return None


async def resolve_wallet(
    *,
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    writer: User,
    wallet_hint: str | None,
    currency: Literal["UZS", "USD"] | None,
    default_wallet: Wallet,
) -> Wallet | CurrencyMissing:
    visible = await list_wallets_for_parse(session, family_budget_id, writer)
    chosen = _pick_wallet_by_hint(visible, wallet_hint, default_wallet, currency)

    if currency is None or chosen.currency == currency:
        return chosen

    replacement = _find_wallet_in_currency(visible, currency)
    if replacement is None:
        return CurrencyMissing(currency=currency)
    return replacement
