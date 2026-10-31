"""Bot texts for the purchase waiting for a sum (MVP 3, m3-4b).

Source: work/design/mvp3-strings.md, section "Бот". Language follows user.language.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app import config
from bot.quick_entry.cards import format_number

_HINT = {
    ("photo", "ru"): "Пришлите фото чека — запишу одной суммой.",
    ("photo", "uz"): "Chek rasmini yuboring — bitta summa qilib yozaman.",
    ("voice", "ru"): "Скажите сумму закупки голосом.",
    ("voice", "uz"): "Xarid summasini ovozli xabarda ayting.",
}
_RECORDED = {
    "ru": "Записал закупку: {amount} сум.",
    "uz": "Xarid yozildi: {amount} so'm.",
}
_NOT_RECOGNIZED = {
    "ru": "Не разобрал сумму. Введите её в приложении вручную.",
    "uz": "Summani tushunmadim. Uni ilovada qo‘lda kiriting.",
}
_BUTTON = {"ru": "Вернуться в приложение", "uz": "Ilovaga qaytish"}


def _lang(language: str | None) -> str:
    return language if language in ("ru", "uz") else "ru"


def pending_hint_text(language: str | None, method: str) -> str:
    return _HINT[(method, _lang(language))]


def recorded_text(language: str | None, amount: int) -> str:
    return _RECORDED[_lang(language)].format(amount=format_number(amount))


def not_recognized_text(language: str | None) -> str:
    return _NOT_RECOGNIZED[_lang(language)]


def purchase_launch_url(purchase_id: object) -> str | None:
    """Mini-app screen for a purchase: <MINI_APP_URL>/shopping/trip?purchase=<id>.

    The same link serves the result screen and the manual-sum screen: the app
    reads GET /shopping/purchases/pending/{id} to see which one to show.
    """
    base = config.MINI_APP_URL
    if not base:
        return None
    parts = urlsplit(base)
    path = parts.path.rstrip("/") + "/shopping/trip"
    return urlunsplit((parts.scheme, parts.netloc, path, f"purchase={purchase_id}", ""))


def launcher_keyboard(language: str | None, purchase_id: object) -> InlineKeyboardMarkup | None:
    url = purchase_launch_url(purchase_id)
    if url is None:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_BUTTON[_lang(language)], web_app=WebAppInfo(url=url))]
        ]
    )
