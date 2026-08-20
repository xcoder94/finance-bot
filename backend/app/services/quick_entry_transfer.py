from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.types import ParsedOperation
from app.services.quick_entry_wallets import (
    CurrencyMissing,
    list_wallets_for_parse,
    wallet_matches_hint,
)
from app.services.transactions import validate_transfer_refs

RATE_MARKER_RE = re.compile(
    r"(?:по\s+курсу)|(?:\bпо\b)",
    re.IGNORECASE | re.UNICODE,
)

MAX_RATE = 2_000_000_000


@dataclass(frozen=True, slots=True)
class ExchangeRateRequired:
    """§8.3 refusal — cross-currency transfer/exchange without rate."""


@dataclass(frozen=True, slots=True)
class ResolvedTransferWallets:
    from_wallet: Wallet
    to_wallet: Wallet


def text_has_rate_marker(text: str) -> bool:
    return bool(RATE_MARKER_RE.search(text))


def effective_rate(op: ParsedOperation, source_text: str) -> int | None:
    rate = op.rate
    if (
        rate is not None
        and 0 < rate <= MAX_RATE
        and text_has_rate_marker(source_text)
    ):
        return rate
    return None


def needs_exchange_refusal(
    *,
    from_currency: str,
    to_currency: str,
    rate: int | None,
) -> bool:
    return from_currency != to_currency and rate is None


def _pick_by_hint(
    wallets: list[Wallet],
    hint: str,
    *,
    exclude: Wallet | None = None,
) -> Wallet | None:
    for wallet in wallets:
        if exclude is not None and wallet.id == exclude.id:
            continue
        if wallet_matches_hint(hint, wallet.name):
            return wallet
    return None


def _find_wallet_in_currency(
    wallets: list[Wallet],
    currency: Literal["UZS", "USD"],
    *,
    exclude: Wallet | None = None,
    prefer_shared: bool = False,
) -> Wallet | None:
    if prefer_shared:
        for wallet in wallets:
            if (
                wallet.currency == currency
                and not wallet.is_personal
                and (exclude is None or wallet.id != exclude.id)
            ):
                return wallet
    for wallet in wallets:
        if wallet.currency == currency and (
            exclude is None or wallet.id != exclude.id
        ):
            return wallet
    return None


def _resolve_from_wallet(
    wallets: list[Wallet],
    *,
    from_hint: str | None,
    amount_currency: Literal["UZS", "USD"],
    default_wallet: Wallet,
) -> Wallet | CurrencyMissing:
    if from_hint:
        matched = _pick_by_hint(wallets, from_hint)
        if matched is not None:
            if matched.currency == amount_currency:
                return matched
            replacement = _find_wallet_in_currency(wallets, amount_currency)
            if replacement is None:
                return CurrencyMissing(currency=amount_currency)
            return replacement

    if default_wallet.currency == amount_currency:
        return default_wallet

    replacement = _find_wallet_in_currency(wallets, amount_currency)
    if replacement is None:
        return CurrencyMissing(currency=amount_currency)
    return replacement


def _resolve_to_wallet(
    wallets: list[Wallet],
    *,
    to_hint: str | None,
    from_wallet: Wallet,
    default_wallet: Wallet,
) -> Wallet | CurrencyMissing:
    if to_hint:
        matched = _pick_by_hint(wallets, to_hint, exclude=from_wallet)
        if matched is not None:
            return matched

    same_currency = _find_wallet_in_currency(
        wallets,
        from_wallet.currency,  # type: ignore[arg-type]
        exclude=from_wallet,
        prefer_shared=True,
    )
    if same_currency is not None:
        return same_currency

    if (
        default_wallet.id != from_wallet.id
        and default_wallet.currency == from_wallet.currency
    ):
        return default_wallet

    return CurrencyMissing(currency=from_wallet.currency)  # type: ignore[arg-type]


async def resolve_transfer_wallets(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    writer: User,
    *,
    from_hint: str | None,
    to_hint: str | None,
    amount_currency: Literal["UZS", "USD"],
    default_wallet: Wallet,
) -> ResolvedTransferWallets | CurrencyMissing:
    visible = await list_wallets_for_parse(session, family_budget_id, writer)

    from_result = _resolve_from_wallet(
        visible,
        from_hint=from_hint,
        amount_currency=amount_currency,
        default_wallet=default_wallet,
    )
    if isinstance(from_result, CurrencyMissing):
        return from_result

    to_result = _resolve_to_wallet(
        visible,
        to_hint=to_hint,
        from_wallet=from_result,
        default_wallet=default_wallet,
    )
    if isinstance(to_result, CurrencyMissing):
        return to_result

    return ResolvedTransferWallets(from_wallet=from_result, to_wallet=to_result)


async def create_quick_entry_transfer(
    session: AsyncSession,
    user: User,
    *,
    from_wallet_id: uuid.UUID,
    to_wallet_id: uuid.UUID,
    amount: int,
    rate: Decimal | None,
    comment: str | None,
    transaction_date: datetime,
) -> Transaction:
    _, _, to_amount, stored_rate = await validate_transfer_refs(
        session,
        user.family_budget_id,
        from_wallet_id,
        to_wallet_id,
        amount,
        rate,
        user,
    )
    transaction = Transaction(
        family_budget_id=user.family_budget_id,
        type="transfer",
        wallet_id=from_wallet_id,
        to_wallet_id=to_wallet_id,
        amount=amount,
        to_amount=to_amount,
        rate=stored_rate,
        comment=comment,
        created_by_user_id=user.id,
        transaction_date=transaction_date,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction
