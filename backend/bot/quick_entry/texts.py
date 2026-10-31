from __future__ import annotations

from typing import Literal

MSG_TOO_LONG = (
    "Сообщение слишком длинное — максимум 500 символов. Разбейте на несколько."
)
MSG_TOO_MANY_OPS = (
    "В одном сообщении можно записать не больше 5 операций. "
    "Разбейте на несколько сообщений."
)
MSG_NO_AMOUNT = (
    "Не нашёл сумму в сообщении.\n"
    "Напишите так: `такси 25 тысяч` или `продукты 200 тыс с карты`"
)
MSG_MODEL_FAIL = (
    "Не получилось записать — дело не в вашем сообщении. "
    "Попробуйте отправить его ещё раз через минуту или "
    "запишите операцию в приложении."
)
MSG_GONE = "Запись больше не существует."
MSG_TYPE_QUESTION = "Не понял, это трата или доход?"
MSG_EXCHANGE_RATE_REQUIRED = (
    "Перевод между кошельками в разных валютах — это обмен, для него нужен курс.\n"
    "Сделайте его в приложении."
)
MSG_VOICE_NOT_RECOGNIZED = (
    "Не разобрал голосовое. Попробуйте записать ещё раз или напишите текстом."
)
MSG_RECEIPT_UNREADABLE = (
    "Не разобрал чек. Сфотографируйте его целиком при хорошем свете или запишите\n"
    "сумму текстом."
)


def currency_missing_text(currency: Literal["UZS", "USD"]) -> str:
    if currency == "USD":
        return (
            "Кошелька в долларах у вас нет. "
            "Добавьте его в приложении, в настройках."
        )
    return "Кошелька в сумах у вас нет. Добавьте его в приложении, в настройках."


def model_limit_text(limit: int) -> str:
    return (
        f"Сегодня записано {limit} операций — это дневной предел на семью. "
        "Новые записи можно вносить с полуночи."
    )


def unparsed_limit_text(limit: int) -> str:
    return (
        f"Сегодня не удалось разобрать {limit} сообщений — это дневной предел. "
        "Записи можно добавить в приложении."
    )


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
