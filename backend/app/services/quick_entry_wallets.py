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


# Uzbek (Latin) words for the usual wallet kinds, folded to the Russian word: a wallet named in
# Russian is reachable by "kartadan"/"naqdga" and the other way round. A case ending may follow.
_KIND_ALIASES = {"karta": "карта", "naqd": "наличные", "naqt": "наличные", "naxt": "наличные"}

# A word is "a name + a case ending" only with an ending from these closed lists. Sharing a
# beginning with a name is not enough: "картошка", "картина", "наличники" are not "карта"/"наличка".
_RU_ENDINGS = sorted(
    {
        "ами", "ями", "ыми", "ими", "ого", "его", "ому", "ему", "ой", "ей", "ою", "ею", "ом",
        "ем", "ым", "им", "ую", "юю", "ых", "их", "ах", "ях", "ов", "ев", "ам", "ям", "ые",
        "ие", "ый", "ий", "ое", "ее", "ая", "яя", "ью", "а", "я", "у", "ю", "ы", "и", "е",
        "о", "ь", "й",
    },
    key=len,
    reverse=True,
)


def _build_uz_endings() -> list[str]:
    cases = ["", "ni", "ning", "ga", "ka", "qa", "ra", "da", "dan", "dagi", "gacha"]
    owners = ["", "im", "ing", "i", "si", "imiz", "ingiz"]
    plurals = ["", "lar"]
    out = {p + o + c for p in plurals for o in owners for c in cases}
    out.discard("")
    return sorted(out, key=len, reverse=True)


_UZ_ENDINGS = _build_uz_endings()
_MIN_STEM = 3

# Latin spellings of Russian letters (several for the ambiguous ones) so that "kopilkadan" reads
# as a form of "Копилка".
_TRANSLIT = {
    "а": ["a"], "б": ["b"], "в": ["v"], "г": ["g"], "д": ["d"], "е": ["e", "ye"], "ё": ["yo", "e"],
    "ж": ["j", "zh"], "з": ["z"], "и": ["i"], "й": ["y", "i"], "к": ["k"], "л": ["l"], "м": ["m"],
    "н": ["n"], "о": ["o"], "п": ["p"], "р": ["r"], "с": ["s"], "т": ["t"], "у": ["u"],
    "ф": ["f"], "х": ["x", "kh", "h"], "ц": ["ts", "s"], "ч": ["ch"], "ш": ["sh"], "щ": ["sh"],
    "ъ": [""], "ы": ["i", "y"], "ь": [""], "э": ["e"], "ю": ["yu", "u"], "я": ["ya", "a"],
}
_MIN_TRANSLIT_STEM = 4


def _is_cyrillic(word: str) -> bool:
    return any("\u0400" <= ch <= "\u04ff" for ch in word)


def _stems(word: str) -> set[str]:
    """The word and the word without one closed-list ending (stems of at least 3 letters)."""
    endings = _RU_ENDINGS if _is_cyrillic(word) else _UZ_ENDINGS
    out = {word}
    for e in endings:
        if word.endswith(e) and len(word) - len(e) >= _MIN_STEM:
            out.add(word[: -len(e)])
    return out


def _lat_variants(cyr: str) -> set[str]:
    variants = {""}
    for ch in cyr:
        options = _TRANSLIT.get(ch)
        if options is None:
            options = [ch]
        variants = {v + o for v in variants for o in options}
        if len(variants) > 64:
            variants = set(sorted(variants)[:64])
    return variants


def _canon(token: str) -> str:
    if token.startswith(_USD_PREFIXES) or token == "$":
        return "usd"
    if token in _UZS_WORDS:
        return "uzs"
    if not _is_cyrillic(token):
        stems = _stems(token)
        for stem, canon in _KIND_ALIASES.items():
            if stem in stems:
                return canon
    return token


def _tokens(text: str) -> list[str]:
    folded = text.translate(_APOSTROPHES).casefold()
    return [_canon(t.strip("'")) for t in _WORD_RE.findall(folded) if t.strip("'")]


def is_plain_name_word(word: str, wallet_names: list[str]) -> bool:
    """True when the word is a word of a wallet name as written (or its Latin spelling), with no
    case ending added: "Копилка" for the wallet Копилка; "kopilkaga" is not plain."""
    w = word.translate(_APOSTROPHES).casefold().strip("'")
    for name in wallet_names:
        for t in _WORD_RE.findall(name.translate(_APOSTROPHES).casefold()):
            t = t.strip("'")
            if w == t or (_is_cyrillic(t) and w in _lat_variants(t)):
                return True
    return False


def _same_word(a: str, b: str) -> bool:
    """Equal, or one is the other with a closed-list case ending (karta/kartadan,
    наличный/наличными), or a Latin spelling of a Russian word with such an ending."""
    if a == b:
        return True
    sa, sb = _stems(a), _stems(b)
    if any(len(x) >= _MIN_STEM for x in sa & sb):
        return True
    ca, cb = _is_cyrillic(a), _is_cyrillic(b)
    if ca != cb:
        cyr, lat = (a, b) if ca else (b, a)
        lat_stems = _stems(lat)
        for stem in _stems(cyr):
            if len(stem) >= _MIN_TRANSLIT_STEM and _lat_variants(stem) & lat_stems:
                return True
    return False


def _has_word(tokens: list[str], word: str) -> bool:
    return any(_same_word(t, word) for t in tokens)


def _narrow(candidates: list[Wallet], currency: str | None) -> list[Wallet]:
    """Several wallets fit equally (two cards named alike): the amount's currency decides."""
    if len(candidates) > 1 and currency is not None:
        in_currency = [w for w in candidates if w.currency == currency]
        if in_currency:
            return in_currency
    return candidates


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

    exact = _narrow([w for w, toks in allowed if toks and toks == hint_tokens], currency)
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
        top = _narrow([w for w, toks in whole if len(toks) == longest], currency)
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
    found = _narrow(found, currency)
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


def _word_key(word: str) -> str | None:
    found = _tokens(word)
    return found[0] if found else None


def _cut_phrase(words: list[str], phrase: str) -> list[str]:
    """Remove every run of whole words that reads as `phrase` (case/ending tolerant)."""
    wanted = [k for k in (_word_key(p) for p in phrase.split()) if k]
    if not wanted:
        return words
    keys = [_word_key(w) for w in words]
    out: list[str] = []
    i = 0
    while i < len(words):
        window = keys[i : i + len(wanted)]
        if len(window) == len(wanted) and all(
            k is not None and _same_word(k, w) for k, w in zip(window, wanted)
        ):
            i += len(wanted)
            continue
        out.append(words[i])
        i += 1
    return out


def strip_wallet_mention(
    comment: str | None, wallet_name: str, hint: str | None
) -> str | None:
    """Drop the wallet's name / the phrase that named it from a comment (whole words only)."""
    if not comment:
        return comment
    words = comment.split()
    phrases = sorted(filter(None, (wallet_name, hint)), key=lambda p: -len(p.split()))
    for phrase in phrases:
        words = _cut_phrase(words, phrase)
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
    if currency is None and wallet_hint:
        # No currency in the phrase: the amount is in the person's usual one (the default
        # wallet's), which decides between two equal-named cards ("Карта" UZS and USD).
        by_usual = pick_wallet_by_hint(visible, wallet_hint, currency=default_wallet.currency)
        if by_usual is not None:
            chosen = by_usual

    if currency is None or chosen.currency == currency:
        return chosen

    replacement = _find_wallet_in_currency(visible, currency)
    if replacement is None:
        return CurrencyMissing(currency=currency)
    return replacement
