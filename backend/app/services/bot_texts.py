"""One text catalogue for the Telegram bot: every key has `ru` and `uz`.

`t(user, key, **params)` picks the person's language (a `User`, or a bare language
code); only an unknown / missing language falls back to RU. UZ strings use the ASCII
apostrophe `'` only (checked by tests/test_ux_p5_bot_texts.py).
"""

from __future__ import annotations

from typing import Any

SUPPORTED = ("ru", "uz")

_WELCOME_TAIL_RU = "Записывайте траты прямо здесь, сообщением:\n`такси 25 тысяч`\n\n"
_WELCOME_TAIL_UZ = "Xarajatlarni shu yerning o'zida xabar bilan yozing:\n`taksi 25 ming`\n\n"

CATALOGUE: dict[str, dict[str, str]] = {
    # --- /start (PRD §18.1, §18.2) ---
    "welcome.solo": {
        "ru": "Chontak — семейный бюджет.\n\n" + _WELCOME_TAIL_RU
        + "Кошельки, категории и аналитика — в приложении.",
        "uz": "Chontak — oilaviy byudjet.\n\n" + _WELCOME_TAIL_UZ
        + "Hamyonlar, kategoriyalar va tahlil — ilovada.",
    },
    "welcome.invited": {
        "ru": "Вы присоединились к бюджету «{budget_name}».\n"
        "Всё, что вы запишете, увидят остальные участники.\n\n" + _WELCOME_TAIL_RU
        + "Кошельки, цели и аналитика — в приложении.",
        "uz": "Siz «{budget_name}» byudjetiga qo'shildingiz.\n"
        "Siz yozgan hamma narsani boshqa a'zolar ko'radi.\n\n" + _WELCOME_TAIL_UZ
        + "Hamyonlar, maqsadlar va tahlil — ilovada.",
    },
    "onboarding.choose_language": {"ru": "Выберите язык:", "uz": "Tilni tanlang:"},
    "onboarding.already_member": {
        "ru": "Вы уже состоите в Chontak.",
        "uz": "Siz allaqachon Chontak a'zosisiz.",
    },
    "onboarding.invalid_invite": {
        "ru": "Ссылка-приглашение недействительна или просрочена.",
        "uz": "Taklif havolasi yaroqsiz yoki muddati tugagan.",
    },
    "onboarding.invite_only_owner": {
        "ru": "Только владелец может приглашать участников.",
        "uz": "Faqat egasi a'zolarni taklif qila oladi.",
    },
    "onboarding.not_registered": {
        "ru": "Сначала пройдите регистрацию через /start.",
        "uz": "Avval /start orqali ro'yxatdan o'ting.",
    },
    # --- buttons ---
    "button.open_app": {"ru": "Открыть приложение", "uz": "Ilovani ochish"},
    "button.join": {"ru": "Присоединиться", "uz": "Qo'shilish"},
    "button.cancel": {"ru": "Отмена", "uz": "Bekor qilish"},
    "button.transfer_accept": {"ru": "Принять", "uz": "Qabul qilish"},
    "button.transfer_refuse": {"ru": "Отказаться", "uz": "Rad etish"},
    # --- phone request ---
    "phone.prompt": {
        "ru": "Если хотите, поделитесь номером телефона — так нам проще связаться с вами, "
        "если что-то пойдёт не так. Можно пропустить.",
        "uz": "Xohlasangiz, telefon raqamingizni yuboring — biror muammo bo'lsa, "
        "siz bilan bog'lanish osonroq bo'ladi. O'tkazib yuborish mumkin.",
    },
    "phone.share": {"ru": "Поделиться номером", "uz": "Raqamni yuborish"},
    "phone.skip": {"ru": "Пропустить", "uz": "O'tkazib yuborish"},
    "phone.saved": {"ru": "Спасибо, номер сохранён.", "uz": "Rahmat, raqam saqlandi."},
    "phone.skipped": {
        "ru": "Хорошо. Записывайте траты сообщением.",
        "uz": "Mayli. Xarajatlarni xabar bilan yozing.",
    },
    "phone.restored": {"ru": "Хорошо.", "uz": "Mayli."},
    "phone.foreign": {
        "ru": "Нужен ваш номер — кнопка ниже.",
        "uz": "Sizning raqamingiz kerak — pastdagi tugma.",
    },
    # --- membership ---
    "member.invite_link_invalid": {
        "ru": "Эта ссылка-приглашение больше не действует. Попросите новую у того, кто вас "
        "пригласил.",
        "uz": "Bu taklif havolasi endi ishlamaydi. Sizni taklif qilgan odamdan yangisini so'rang.",
    },
    "member.family_full": {
        "ru": "В этом семейном бюджете уже 4 участника — это предел.",
        "uz": "Bu oilaviy byudjetda allaqachon 4 a'zo bor — bu chegara.",
    },
    "member.already_member": {
        "ru": "Вы уже участник бюджета «{budget_name}».",
        "uz": "Siz allaqachon «{budget_name}» byudjeti a'zosisiz.",
    },
    "member.join_has_other_members": {
        "ru": "Нельзя присоединиться к другой семье, пока в вашем бюджете есть участники.\n"
        "Передайте права владения одному из них или удалите участников, затем "
        "попробуйте снова.",
        "uz": "Byudjetingizda a'zolar bor ekan, boshqa oilaga qo'shilib bo'lmaydi.\n"
        "Egalik huquqini ulardan biriga topshiring yoki a'zolarni o'chiring, "
        "so'ng qayta urinib ko'ring.",
    },
    "member.join_personal_wallet_cap": {
        "ru": "В новой семье ваши кошельки станут личными, а личных можно иметь не больше 5.\n"
        "Сейчас у вас {count} — удалите лишние и попробуйте снова.",
        "uz": "Yangi oilada hamyonlaringiz shaxsiy bo'ladi, shaxsiy hamyon esa 5 tadan "
        "ko'p bo'lmasligi kerak.\n"
        "Hozir sizda {count} ta — ortiqchasini o'chirib, qayta urinib ko'ring.",
    },
    "member.join_confirm": {
        "ru": "Вы присоединяетесь к бюджету «{budget_name}». Ваши кошельки и операции по "
        "ним станут вашими личными в этой семье, ваш бюджет закроется.",
        "uz": "Siz «{budget_name}» byudjetiga qo'shilyapsiz. Hamyonlaringiz va ulardagi "
        "operatsiyalar bu oilada shaxsiy bo'lib qoladi, sizning byudjetingiz yopiladi.",
    },
    "member.removed_notice": {
        "ru": "Вы больше не участник семейного бюджета «{budget_name}».\n\n"
        "Ваши личные кошельки и операции по ним перешли в ваш собственный бюджет — "
        "вы теперь его владелец.",
        "uz": "Siz endi «{budget_name}» oilaviy byudjetining a'zosi emassiz.\n\n"
        "Shaxsiy hamyonlaringiz va ulardagi operatsiyalar o'zingizning byudjetingizga "
        "o'tdi — endi uning egasi siz.",
    },
    "member.left_notice": {
        "ru": "Вы вышли из бюджета «{budget_name}».\n\n"
        "Ваши личные кошельки и операции по ним перешли в ваш собственный бюджет — "
        "вы теперь его владелец.",
        "uz": "Siz «{budget_name}» byudjetidan chiqdingiz.\n\n"
        "Shaxsiy hamyonlaringiz va ulardagi operatsiyalar o'zingizning byudjetingizga "
        "o'tdi — endi uning egasi siz.",
    },
    "member.transfer_offer": {
        "ru": "Вас предлагают сделать владельцем бюджета «{budget_name}».\n\n"
        "Владелец распоряжается общими кошельками, категориями и участниками.\n"
        "Прежний владелец останется обычным участником.",
        "uz": "Sizni «{budget_name}» byudjetining egasi qilishni taklif qilishyapti.\n\n"
        "Egasi umumiy hamyonlar, kategoriyalar va a'zolarni boshqaradi.\n"
        "Avvalgi egasi oddiy a'zo bo'lib qoladi.",
    },
    "member.transfer_accepted_to_former": {
        "ru": "{name} теперь владелец бюджета «{budget_name}». Вы остались участником.",
        "uz": "{name} endi «{budget_name}» byudjetining egasi. Siz a'zo bo'lib qoldingiz.",
    },
    "member.transfer_refused_to_former": {
        "ru": "{name} отказался стать владельцем.",
        "uz": "{name} egasi bo'lishdan bosh tortdi.",
    },
    "member.transfer_accepted_to_others": {
        "ru": "{name} теперь владелец бюджета «{budget_name}».",
        "uz": "{name} endi «{budget_name}» byudjetining egasi.",
    },
    "member.transfer_stale": {
        "ru": "Предложение больше не действует.",
        "uz": "Taklif endi kuchda emas.",
    },
    "member.departed_label": {
        "ru": "{name} (бывший участник)",
        "uz": "{name} (sobiq a'zo)",
    },
}


def resolve_language(who: Any) -> str:
    """`who` is a User-like object (has `.language`), a language code, or None."""
    code = getattr(who, "language", who)
    return code if code in SUPPORTED else "ru"


def t(who: Any, key: str, **params: Any) -> str:
    template = CATALOGUE[key][resolve_language(who)]
    return template.format(**params) if params else template
