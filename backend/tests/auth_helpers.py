import uuid

from app.auth.pass_tokens import issue_app_pass

TEST_APP_PASS_SECRET = "test-app-pass-secret-not-for-production"


def bearer_header_for_telegram_id(
    telegram_id: int,
    user_id: uuid.UUID | None = None,
) -> dict[str, str]:
    token, _, _ = issue_app_pass(
        telegram_id=telegram_id,
        user_id=user_id,
        secret=TEST_APP_PASS_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}
