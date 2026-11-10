from __future__ import annotations

from typing import Literal

from app.services.bot_texts import CATALOGUE, t

# RU defaults (kept as constants for callers/tests that pin the Russian text); the handlers use
# the `*_text(language)` helpers / `t(user, key)` so the person's language wins.
MSG_TOO_LONG = CATALOGUE["quick.too_long"]["ru"]
MSG_TOO_MANY_OPS = CATALOGUE["quick.too_many_ops"]["ru"]
MSG_NO_AMOUNT = CATALOGUE["quick.no_amount"]["ru"]
MSG_MODEL_FAIL = CATALOGUE["quick.model_fail"]["ru"]
MSG_GONE = CATALOGUE["quick.gone"]["ru"]
MSG_TYPE_QUESTION = CATALOGUE["quick.type_question"]["ru"]
MSG_EXCHANGE_RATE_REQUIRED = CATALOGUE["quick.exchange_rate_required"]["ru"]
MSG_VOICE_NOT_RECOGNIZED = CATALOGUE["quick.voice_not_recognized"]["ru"]
MSG_RECEIPT_UNREADABLE = CATALOGUE["quick.receipt_unreadable"]["ru"]


def currency_missing_text(
    currency: Literal["UZS", "USD"], language: str | None = None
) -> str:
    key = "quick.currency_missing_usd" if currency == "USD" else "quick.currency_missing_uzs"
    return t(language, key)


def model_limit_text(limit: int, language: str | None = None) -> str:
    return t(language, "quick.model_limit", limit=limit)


def unparsed_limit_text(limit: int, language: str | None = None) -> str:
    return t(language, "quick.unparsed_limit", limit=limit)


# --- Shopping list replies (MVP 3). Source: work/design/mvp3-strings.md, "Бот". ---
SHOPPING_ITEMS_PER_MESSAGE = 20

_SHOPPING_ADDED = {
    "ru": "Добавил в список покупок: {names}.",
    "uz": "Xarid ro'yxatiga qo'shdim: {names}.",
}
_SHOPPING_EXISTING = {
    "ru": "Уже были в списке: {names}.",
    "uz": "Ro'yxatda bor edi: {names}.",
}
_SHOPPING_FULL = {
    "ru": "В списке уже 100 позиций — остальное не добавил.",
    "uz": "Ro'yxatda allaqachon 100 ta pozitsiya — qolganini qo'shmadim.",
}


def _lang(language: str | None) -> str:
    return language if language in ("ru", "uz") else "ru"


def shopping_reply_text(
    language: str | None,
    *,
    added: list[str],
    existing: list[str],
    over_limit: bool,
) -> str:
    """Names must already be Markdown-escaped by the caller."""
    lang = _lang(language)
    lines: list[str] = []
    if added:
        lines.append(_SHOPPING_ADDED[lang].format(names=", ".join(added)))
    if existing:
        lines.append(_SHOPPING_EXISTING[lang].format(names=", ".join(existing)))
    if over_limit:
        lines.append(_SHOPPING_FULL[lang])
    return "\n".join(lines)
