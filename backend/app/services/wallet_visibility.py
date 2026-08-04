from fastapi import HTTPException
from sqlalchemy import and_, or_

from app.models.user import User
from app.models.wallet import Wallet


def wallet_is_visible(wallet: Wallet, user: User) -> bool:
    if not wallet.is_personal:
        return True
    return wallet.owner_user_id == user.id


def require_wallet_visible(wallet: Wallet | None, user: User) -> Wallet:
    if wallet is None or not wallet_is_visible(wallet, user):
        raise HTTPException(status_code=404)
    return wallet


def visible_wallets_clause(user: User):
    return or_(
        Wallet.is_personal.is_(False),
        and_(
            Wallet.is_personal.is_(True),
            Wallet.owner_user_id == user.id,
        ),
    )


def personal_ops_hidden_clause(viewer: User, from_wallet: Wallet, to_wallet: Wallet):
    return and_(
        or_(
            from_wallet.is_personal.is_(False),
            from_wallet.owner_user_id == viewer.id,
        ),
        or_(
            to_wallet.id.is_(None),
            to_wallet.is_personal.is_(False),
            to_wallet.owner_user_id == viewer.id,
        ),
    )
