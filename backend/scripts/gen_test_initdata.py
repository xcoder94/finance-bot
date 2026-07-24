"""
Генерирует валидную строку initData для ручного тестирования API через
Postman/curl. Использует ТОТ ЖЕ секрет (BOT_TOKEN из .env) и ту же функцию
подписи (sign_init_data), что и реальный auth-модуль app/auth/telegram.py.

ВАЖНО: этот скрипт НЕ создаёт пользователя в базе и НЕ управляет ролью
(owner/member). Роль хранится в таблице users и проверяется отдельно
(app/auth/user_deps.py). Чтобы запрос прошёл require_owner, в БД уже
должна существовать строка User с этим telegram_id и role="owner".

Запуск (из папки backend, с активным venv проекта):
    python scripts/gen_test_initdata.py --telegram-id 111111 --first-name Owner
    python scripts/gen_test_initdata.py --telegram-id 222222 --first-name Member
"""

import argparse
import json
import time

from app.auth.telegram import sign_init_data
from app.config import BOT_TOKEN


def build_init_data(
    telegram_id: int,
    first_name: str,
    last_name: str | None,
    username: str | None,
    language_code: str,
    auth_date: int | None,
) -> str:
    user_payload = {
        "id": telegram_id,
        "first_name": first_name,
        "language_code": language_code,
    }
    if last_name:
        user_payload["last_name"] = last_name
    if username:
        user_payload["username"] = username

    fields = {
        "query_id": "AAHtestQueryId",
        "user": json.dumps(user_payload, separators=(",", ":")),
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
    }
    return sign_init_data(fields, BOT_TOKEN)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telegram-id", type=int, required=True)
    parser.add_argument("--first-name", default="Test")
    parser.add_argument("--last-name", default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--language-code", default="ru")
    parser.add_argument(
        "--auth-date",
        type=int,
        default=None,
        help="Unix timestamp. По умолчанию — текущее время (свежий initData).",
    )
    args = parser.parse_args()

    init_data = build_init_data(
        telegram_id=args.telegram_id,
        first_name=args.first_name,
        last_name=args.last_name,
        username=args.username,
        language_code=args.language_code,
        auth_date=args.auth_date,
    )

    print("\nAuthorization header value:\n")
    print(f"tma {init_data}")
    print()


if __name__ == "__main__":
    main()