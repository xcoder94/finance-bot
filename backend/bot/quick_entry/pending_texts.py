"""Bot texts for the purchase waiting for a sum (MVP 3, m3-4b).

Source: work/design/mvp3-strings.md, section "Бот". Language follows user.language.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app import config
from app.config import receipt_photo_enabled
from bot.quick_entry.cards import format_number

# The chosen method does not matter any more: any way of giving the sum works.
_HINT = {
    ("all", "ru"): "Пришлите сумму закупки: голосом, фото чека или текстом.",
    ("all", "uz"): "Xarid summasini yuboring: ovozli xabar, chek rasmi yoki matn bilan.",
    ("no_photo", "ru"): "Пришлите сумму закупки: голосом или текстом.",
    ("no_photo", "uz"): "Xarid summasini yuboring: ovozli xabar yoki matn bilan.",
}
_CANCEL_BUTTON = {"ru": "Отменить закупку", "uz": "Xaridni bekor qilish"}
CANCEL_PREFIX = "shp:cancel:"
_CANCELLED = {
    "ru": "Закупка отменена. Товары остались в списке.",
    "uz": "Xarid bekor qilindi. Mahsulotlar ro'yxatda qoldi.",
}
_ALREADY_RECORDED = {
    "ru": "Закупка уже записана.",
    "uz": "Xarid allaqachon yozilgan.",
}
_RECORDED = {
    "ru": "Записал закупку: {amount} сум.",
    "uz": "Xarid yozildi: {amount} so'm.",
}
_NOT_RECOGNIZED = {
    "ru": "Не разобрал сумму. Введите её в приложении вручную.",
    "uz": "Summani tushunmadim. Uni ilovada qo'lda kiriting.",
}
_BUTTON = {"ru": "Вернуться в приложение", "uz": "Ilovaga qaytish"}


def _lang(language: str | None) -> str:
    return language if language in ("ru", "uz") else "ru"


def pending_hint_text(language: str | None, method: str | None = None) -> str:
    key = "all" if receipt_photo_enabled() else "no_photo"
    return _HINT[(key, _lang(language))]


def cancelled_text(language: str | None) -> str:
    return _CANCELLED[_lang(language)]


def already_recorded_text(language: str | None) -> str:
    return _ALREADY_RECORDED[_lang(language)]


def cancel_keyboard(language: str | None, purchase_id: object) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_CANCEL_BUTTON[_lang(language)],
                    callback_data=f"{CANCEL_PREFIX}{purchase_id}",
                )
            ]
        ]
    )


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


def waiting_keyboard(
    language: str | None, purchase_id: object, *, launcher: bool = False
) -> InlineKeyboardMarkup:
    """Cancel button (+ the app launcher row when asked and MINI_APP_URL is set)."""
    rows = []
    if launcher:
        launch = launcher_keyboard(language, purchase_id)
        if launch is not None:
            rows.extend(launch.inline_keyboard)
    rows.extend(cancel_keyboard(language, purchase_id).inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows)
