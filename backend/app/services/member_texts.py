"""Membership / welcome texts. Thin wrappers over the bot catalogue (app/services/bot_texts.py);
`language` is a code or a User, default RU."""

from typing import Any

from app.services.bot_texts import t


def invite_link_invalid(language: Any = "ru") -> str:
    return t(language, "member.invite_link_invalid")


def invite_family_full_chat(language: Any = "ru") -> str:
    return t(language, "member.family_full")


def invite_family_full(language: Any = "ru") -> str:
    return invite_family_full_chat(language)


def invite_already_member(budget_name: str, language: Any = "ru") -> str:
    return t(language, "member.already_member", budget_name=budget_name)


def join_has_other_members(language: Any = "ru") -> str:
    return t(language, "member.join_has_other_members")


def join_personal_wallet_cap(count: int, language: Any = "ru") -> str:
    return t(language, "member.join_personal_wallet_cap", count=count)


def join_confirm_prompt(budget_name: str, language: Any = "ru") -> str:
    return t(language, "member.join_confirm", budget_name=budget_name)


def welcome_solo(language: Any = "ru") -> str:
    return t(language, "welcome.solo")


def welcome_invited(budget_name: str, language: Any = "ru") -> str:
    return t(language, "welcome.invited", budget_name=budget_name)


def removed_notice(budget_name: str, language: Any = "ru") -> str:
    return t(language, "member.removed_notice", budget_name=budget_name)


def left_notice(budget_name: str, language: Any = "ru") -> str:
    return t(language, "member.left_notice", budget_name=budget_name)


def transfer_offer(budget_name: str, language: Any = "ru") -> str:
    return t(language, "member.transfer_offer", budget_name=budget_name)


def transfer_accepted_to_former(
    new_owner_name: str, budget_name: str, language: Any = "ru"
) -> str:
    return t(
        language, "member.transfer_accepted_to_former",
        name=new_owner_name, budget_name=budget_name,
    )


def transfer_refused_to_former(name: str, language: Any = "ru") -> str:
    return t(language, "member.transfer_refused_to_former", name=name)


def transfer_accepted_to_others(
    new_owner_name: str, budget_name: str, language: Any = "ru"
) -> str:
    return t(
        language, "member.transfer_accepted_to_others",
        name=new_owner_name, budget_name=budget_name,
    )


def departed_label(name: str, language: Any = "ru") -> str:
    return t(language, "member.departed_label", name=name)
