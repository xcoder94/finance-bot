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
        + "Hamyonlar, toifalar va tahlil — ilovada.",
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
    # --- /start of a registered user, help, command menu (ux-fix B16, B20) ---
    "start.already_registered": {
        "ru": "Вы уже в семейном бюджете «{budget_name}».",
        "uz": "Siz allaqachon «{budget_name}» oilaviy byudjetidasiz.",
    },
    "help.hint": {
        "ru": "Напишите трату или доход обычным текстом, например: такси 25 тысяч. "
        "Или откройте приложение.",
        "uz": "Xarajat yoki daromadni oddiy matn bilan yozing, masalan: taksi 25 ming. "
        "Yoki ilovani oching.",
    },
    "command.start": {"ru": "Начать", "uz": "Boshlash"},
    "command.help": {"ru": "Подсказка", "uz": "Yordam"},
    # --- quick entry ---
    "quick.amount_too_large": {
        "ru": "Слишком большая сумма — больше {max} {cur} записать нельзя. Проверьте число.",
        "uz": "Summa juda katta — {max} {cur} dan ortiq yozib bo'lmaydi. Raqamni tekshiring.",
    },
    "quick.amount_too_large_partial": {
        "ru": "Не записал «{what}» — сумма {amount} {cur} больше допустимых {max} {cur}. Проверьте число.",
        "uz": "«{what}» yozilmadi — {amount} {cur} summa ruxsat etilgan {max} {cur} chegarasidan katta. Raqamni tekshiring.",
    },
    # --- quick entry: errors and limits (ux-p5-backend-b) ---
    "quick.too_long": {
        "ru": "Сообщение слишком длинное — максимум 500 символов. Разбейте на несколько.",
        "uz": "Xabar juda uzun — ko'pi bilan 500 belgi. Bir nechta xabarga bo'ling.",
    },
    "quick.too_many_ops": {
        "ru": "В одном сообщении можно записать не больше 5 операций. "
        "Разбейте на несколько сообщений.",
        "uz": "Bitta xabarda 5 tadan ko'p amal yozib bo'lmaydi. Bir nechta xabarga bo'ling.",
    },
    "quick.no_amount": {
        "ru": "Не нашёл сумму в сообщении.\n"
        "Напишите так: `такси 25 тысяч` или `продукты 200 тыс с карты`",
        "uz": "Xabarda summani topa olmadim.\n"
        "Mana bunday yozing: `taksi 25 ming` yoki `oziq-ovqat 200 ming kartadan`",
    },
    "quick.model_fail": {
        "ru": "Не получилось записать — дело не в вашем сообщении. "
        "Попробуйте отправить его ещё раз через минуту или "
        "запишите операцию в приложении.",
        "uz": "Yozib bo'lmadi — gap xabaringizda emas. Bir daqiqadan so'ng yana yuboring "
        "yoki amalni ilovada yozing.",
    },
    "quick.gone": {"ru": "Запись больше не существует.", "uz": "Yozuv endi mavjud emas."},
    "quick.type_question": {
        "ru": "Не понял, это трата или доход?",
        "uz": "Tushunmadim, bu xarajatmi yoki daromadmi?",
    },
    "quick.exchange_rate_required": {
        "ru": "Перевод между кошельками в разных валютах — это обмен, для него нужен курс.\n"
        "Сделайте его в приложении.",
        "uz": "Turli valyutadagi hamyonlar o'rtasidagi o'tkazma — bu ayirboshlash, buning "
        "uchun kurs kerak.\nUni ilovada bajaring.",
    },
    "quick.voice_not_recognized": {
        "ru": "Не разобрал голосовое. Попробуйте записать ещё раз или напишите текстом.",
        "uz": "Ovozli xabarni tushunmadim. Qayta yozib yuboring yoki matn bilan yozing.",
    },
    "quick.receipt_unreadable": {
        "ru": "Не разобрал чек. Сфотографируйте его целиком при хорошем свете или запишите\n"
        "сумму текстом.",
        "uz": "Chekni o'qiy olmadim. Uni to'liq va yorug'da suratga oling yoki\n"
        "summani matn bilan yozing.",
    },
    "quick.currency_missing_usd": {
        "ru": "Кошелька в долларах у вас нет. Добавьте его в приложении, в настройках.",
        "uz": "Sizda dollar hamyoni yo'q. Uni ilovada, sozlamalarda qo'shing.",
    },
    "quick.currency_missing_uzs": {
        "ru": "Кошелька в сумах у вас нет. Добавьте его в приложении, в настройках.",
        "uz": "Sizda so'm hamyoni yo'q. Uni ilovada, sozlamalarda qo'shing.",
    },
    "quick.model_limit": {
        "ru": "Сегодня записано {limit} операций — это дневной предел на семью. "
        "Новые записи можно вносить с полуночи.",
        "uz": "Bugun {limit} ta amal yozildi — bu oila uchun kunlik chegara. "
        "Yangi yozuvlarni yarim tundan keyin kiritish mumkin.",
    },
    "quick.unparsed_limit": {
        "ru": "Сегодня не удалось разобрать {limit} сообщений — это дневной предел. "
        "Записи можно добавить в приложении.",
        "uz": "Bugun {limit} ta xabarni tushunib bo'lmadi — bu kunlik chegara. "
        "Yozuvlarni ilovada qo'shish mumkin.",
    },
    # --- quick-entry cards and their buttons ---
    "card.remaining": {"ru": "Осталось: {amount}", "uz": "Qoldiq: {amount}"},
    "card.transfer": {"ru": "Перевод", "uz": "O'tkazma"},
    "card.exchange": {"ru": "Обмен", "uz": "Ayirboshlash"},
    "card.rate": {"ru": "Курс {rate}", "uz": "Kurs {rate}"},
    "card.no_category": {"ru": "Без категории", "uz": "Toifasiz"},
    "card.unit_sum": {"ru": "сум", "uz": "so'm"},
    "button.wallet": {"ru": "Кошелёк", "uz": "Hamyon"},
    "button.edit": {"ru": "Изменить", "uz": "Tahrirlash"},
    "button.delete": {"ru": "Удалить", "uz": "O'chirish"},
    "button.expense": {"ru": "Потратил", "uz": "Xarajat"},
    "button.income": {"ru": "Получил", "uz": "Daromad"},
    "month.1": {"ru": "января", "uz": "yanvar"},
    "month.2": {"ru": "февраля", "uz": "fevral"},
    "month.3": {"ru": "марта", "uz": "mart"},
    "month.4": {"ru": "апреля", "uz": "aprel"},
    "month.5": {"ru": "мая", "uz": "may"},
    "month.6": {"ru": "июня", "uz": "iyun"},
    "month.7": {"ru": "июля", "uz": "iyul"},
    "month.8": {"ru": "августа", "uz": "avgust"},
    "month.9": {"ru": "сентября", "uz": "sentyabr"},
    "month.10": {"ru": "октября", "uz": "oktyabr"},
    "month.11": {"ru": "ноября", "uz": "noyabr"},
    "month.12": {"ru": "декабря", "uz": "dekabr"},
    # --- reminder, weekly digest, goal notice, release announcement ---
    "reminder.evening": {
        "ru": "Сегодня не было ни одной записи.\n"
        "Напишите трату одной строкой — например, `продукты 150 тысяч`",
        "uz": "Bugun bironta ham yozuv bo'lmadi.\n"
        "Xarajatni bir qatorda yozing — masalan, `bozorlik 150 ming`",
    },
    "digest.title": {"ru": "Итоги недели", "uz": "Hafta yakunlari"},
    "digest.expenses": {"ru": "Расходы: {amount}", "uz": "Xarajatlar: {amount}"},
    "digest.more": {
        "ru": "На {amount} больше, чем на прошлой неделе",
        "uz": "O'tgan haftadan {amount} ko'p",
    },
    "digest.less": {
        "ru": "На {amount} меньше, чем на прошлой неделе",
        "uz": "O'tgan haftadan {amount} kam",
    },
    "digest.leader": {
        "ru": "Больше всего — {name}, {amount}",
        "uz": "Eng ko'pi — {name}, {amount}",
    },
    "digest.goal": {
        "ru": "Цель «{name}»: отложили {set_aside}, накоплено {balance} из {target}",
        "uz": "«{name}» maqsadi: {set_aside} ajratildi, jami {balance} / {target}",
    },
    "digest.goal_done": {
        "ru": "Цель «{name}» достигнута — можно закрыть в разделе «Цели»",
        "uz": "«{name}» maqsadiga erishildi — uni «Maqsadlar» bo'limida yopish mumkin",
    },
    "goal.achieved": {
        "ru": "🎯 Цель «{name}» достигнута\nНакоплено {balance} из {target}",
        "uz": "🎯 «{name}» maqsadiga erishildi\nYig'ildi: {balance} / {target}",
    },
    "goal.close": {"ru": "Закрыть цель", "uz": "Maqsadni yopish"},
    "release.announcement": {
        "ru": "Теперь трату можно записать прямо здесь, сообщением.\n"
        "Напишите, например: `такси 25 тысяч`\n"
        "\n"
        "В приложении появились личные кошельки, цели и управление участниками.",
        "uz": "Endi xarajatni shu yerning o'zida xabar bilan yozish mumkin.\n"
        "Masalan, yozing: `taksi 25 ming`\n"
        "\n"
        "Ilovada shaxsiy hamyonlar, maqsadlar va a'zolarni boshqarish paydo bo'ldi.",
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
        "Egasi umumiy hamyonlar, toifalar va a'zolarni boshqaradi.\n"
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
