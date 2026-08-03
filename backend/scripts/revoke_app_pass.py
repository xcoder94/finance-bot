"""
Revoke an application pass by JWT jti.

Decodes the token (including expired passes), inserts a row into
revoked_app_passes, and prints the revoked jti.

Run from backend/:
    python scripts/revoke_app_pass.py --token '<jwt>'
"""

import argparse
import asyncio
import sys

import jwt

from app.config import APP_PASS_SECRET
from app.db import async_session_factory, dispose_engine
from app.models.revoked_app_pass import RevokedAppPass


def extract_jti(token: str) -> str:
    try:
        claims = jwt.decode(
            token,
            APP_PASS_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": False, "require": ["jti"]},
        )
    except jwt.PyJWTError as exc:
        raise SystemExit(f"invalid application pass token: {exc}") from exc
    jti = claims.get("jti")
    if not jti:
        raise SystemExit("application pass token has no jti claim")
    return str(jti)


async def revoke_pass(token: str) -> str:
    jti = extract_jti(token)
    async with async_session_factory() as session:
        session.add(RevokedAppPass(jti=jti))
        await session.commit()
    return jti


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token",
        required=True,
        help="Application pass JWT to revoke.",
    )
    args = parser.parse_args()
    token = args.token.strip()
    if not token:
        raise SystemExit("--token must not be empty")

    jti = asyncio.run(revoke_pass(token))
    print(f"revoked jti={jti}")


if __name__ == "__main__":
    main()
