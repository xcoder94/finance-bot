from app.services.entity_limits import LIMIT_MEMBERS, MEMBER_LIMIT
from app.services.member_texts import (
    departed_label,
    invite_already_member,
    invite_family_full_chat,
    invite_link_invalid,
    join_has_other_members,
    join_personal_wallet_cap,
    left_notice,
    removed_notice,
    welcome_invited,
)


def test_member_limit_constant_and_app_message():
    assert MEMBER_LIMIT == 4
    assert LIMIT_MEMBERS == "В семейном бюджете уже 4 участника — это предел."


def test_invite_and_join_texts_verbatim():
    assert "больше не действует" in invite_link_invalid()
    assert invite_family_full_chat() == (
        "В этом семейном бюджете уже 4 участника — это предел."
    )
    assert invite_already_member("Семья Юсуповых") == (
        "Вы уже участник бюджета «Семья Юсуповых»."
    )
    assert "пока в вашем бюджете есть участники" in join_has_other_members()
    assert "Сейчас у вас 12" in join_personal_wallet_cap(12)
    assert departed_label("Рустам") == "Рустам (бывший участник)"
    assert removed_notice("Семья Каримовых").startswith(
        "Вы больше не участник семейного бюджета «Семья Каримовых»."
    )
    assert left_notice("Семья Каримовых").startswith(
        "Вы вышли из бюджета «Семья Каримовых»."
    )
    assert "Вы присоединились к бюджету «Семья Юсуповых»." in welcome_invited(
        "Семья Юсуповых"
    )
