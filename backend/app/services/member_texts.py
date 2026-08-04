def invite_link_invalid() -> str:
    return (
        "Эта ссылка-приглашение больше не действует. Попросите новую у того, кто вас "
        "пригласил."
    )


def invite_family_full_chat() -> str:
    return "В этом семейном бюджете уже 4 участника — это предел."


def invite_family_full() -> str:
    return invite_family_full_chat()


def invite_already_member(budget_name: str) -> str:
    return f"Вы уже участник бюджета «{budget_name}»."


def join_has_other_members() -> str:
    return (
        "Нельзя присоединиться к другой семье, пока в вашем бюджете есть участники.\n"
        "Передайте права владения одному из них или удалите участников, затем "
        "попробуйте снова."
    )


def join_personal_wallet_cap(count: int) -> str:
    return (
        "В новой семье ваши кошельки станут личными, а личных можно иметь не больше 5.\n"
        f"Сейчас у вас {count} — удалите лишние и попробуйте снова."
    )


def join_confirm_prompt(budget_name: str) -> str:
    return (
        f"Вы присоединяетесь к бюджету «{budget_name}». Ваши кошельки и операции по "
        "ним станут вашими личными в этой семье, ваш бюджет закроется."
    )


def welcome_invited(budget_name: str) -> str:
    return (
        f"Вы присоединились к бюджету «{budget_name}».\n"
        "Всё, что вы запишете, увидят остальные участники.\n"
        "\n"
        "Записывайте траты прямо здесь, сообщением:\n"
        "`такси 25 тысяч`\n"
        "\n"
        "Кошельки, цели и аналитика — в приложении."
    )


def removed_notice(budget_name: str) -> str:
    return (
        f"Вы больше не участник семейного бюджета «{budget_name}».\n"
        "\n"
        "Ваши личные кошельки и операции по ним перешли в ваш собственный бюджет — "
        "вы теперь его владелец."
    )


def left_notice(budget_name: str) -> str:
    return (
        f"Вы вышли из бюджета «{budget_name}».\n"
        "\n"
        "Ваши личные кошельки и операции по ним перешли в ваш собственный бюджет — "
        "вы теперь его владелец."
    )


def transfer_offer(budget_name: str) -> str:
    return (
        f"Вас предлагают сделать владельцем бюджета «{budget_name}».\n"
        "\n"
        "Владелец распоряжается общими кошельками, категориями и участниками.\n"
        "Прежний владелец останется обычным участником."
    )


def transfer_accepted_to_former(new_owner_name: str, budget_name: str) -> str:
    return (
        f"{new_owner_name} теперь владелец бюджета «{budget_name}». "
        "Вы остались участником."
    )


def transfer_refused_to_former(name: str) -> str:
    return f"{name} отказался стать владельцем."


def transfer_accepted_to_others(new_owner_name: str, budget_name: str) -> str:
    return f"{new_owner_name} теперь владелец бюджета «{budget_name}»."


def departed_label(name: str) -> str:
    return f"{name} (бывший участник)"
