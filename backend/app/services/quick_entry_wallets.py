from __future__ import annotations

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


def _wallet_matches_hint(hint: str, wallet_name: str) -> bool:
    hint_cf = hint.casefold()
    name_cf = wallet_name.casefold()
    if hint_cf in name_cf or name_cf in hint_cf:
        return True
    return any(len(word) >= 3 and word in hint_cf for word in name_cf.split())


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
) -> Wallet:
    if wallet_hint:
        for wallet in wallets:
            if _wallet_matches_hint(wallet_hint, wallet.name):
                return wallet
    return default_wallet


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
    chosen = _pick_wallet_by_hint(visible, wallet_hint, default_wallet)

    if currency is None or chosen.currency == currency:
        return chosen

    replacement = _find_wallet_in_currency(visible, currency)
    if replacement is None:
        return CurrencyMissing(currency=currency)
    return replacement
