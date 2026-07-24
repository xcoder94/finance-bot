"""
Автоматизированная ручная проверка пунктов 6-9 из раздела Verification
в docs/tasks/04-api-wallets-categories.md.

Требования перед запуском:
  1. Сервер должен быть запущен: uvicorn app.main:app --reload
     (в отдельном терминале, порт по умолчанию 8000)
  2. В БД уже должен существовать Owner-пользователь с telegram_id=111111
     (создан ранее вручную в рамках этой же проверки).

Запуск (из папки backend, с активным venv):
    python -m scripts.manual_verify_categories

Скрипт:
  - создаёт top-level и под-категорию расходов через API (пункт 6)
  - проверяет отклонение вложенности "подкатегория под подкатегорией" (пункт 9)
  - напрямую вставляет income-категорию + кошелёк + транзакцию в БД,
    затем удаляет категорию через API и проверяет
    affected_transactions_count и то, что сама транзакция не тронута (пункт 7)
  - удаляет top-level категорию через API и проверяет, что её подкатегория
    тоже стала is_deleted в БД (пункт 8)

Ничего не удаляет и не трогает из ранее созданных вами тестовых
пользователей/кошельков (telegram_id=111111 Owner, 222222 Member) — только
добавляет новые тестовые строки с уникальными именами.
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.db import async_session_factory
from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from scripts.gen_test_initdata import build_init_data
from app.config import BOT_TOKEN

BASE_URL = "http://127.0.0.1:8000"
OWNER_TELEGRAM_ID = 111111

passed = 0
failed = 0


def check(label: str, condition: bool, extra: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed += 1
        print(f"  [FAIL] {label}  {extra}")


async def main() -> None:
    print("Подключаюсь к БД, ищу Owner-пользователя (telegram_id=111111)...")
    async with async_session_factory() as session:
        owner = await session.scalar(
            select(User).where(User.telegram_id == OWNER_TELEGRAM_ID, User.is_deleted.is_(False))
        )
        if owner is None:
            print(
                "ОШИБКА: Owner с telegram_id=111111 не найден в БД. "
                "Сначала выполните шаги из чата (INSERT в family_budgets/users)."
            )
            sys.exit(1)
        family_budget_id = owner.family_budget_id
        print(f"Найден Owner, family_budget_id={family_budget_id}")

    owner_header = "tma " + build_init_data(
        telegram_id=OWNER_TELEGRAM_ID,
        first_name="Owner",
        last_name=None,
        username=None,
        language_code="ru",
        auth_date=None,
    )
    headers = {"Authorization": owner_header, "Content-Type": "application/json"}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        # ---------- Пункт 6: создать top-level категорию и подкатегорию ----------
        print("\n=== Пункт 6: создание top-level категории и подкатегории ===")
        suffix = uuid.uuid4().hex[:6]
        top_resp = await client.post(
            "/api/v1/categories/expense",
            headers=headers,
            json={"name": f"Еда-{suffix}"},
        )
        check("POST top-level category -> 201", top_resp.status_code == 201, str(top_resp.text))
        top_json = top_resp.json() if top_resp.status_code == 201 else {}
        check("top-level category parent_id is null", top_json.get("parent_id") is None)
        top_id = top_json.get("id")

        sub_resp = await client.post(
            "/api/v1/categories/expense",
            headers=headers,
            json={"name": f"Продукты-{suffix}", "parent_id": top_id},
        )
        check("POST subcategory -> 201", sub_resp.status_code == 201, str(sub_resp.text))
        sub_json = sub_resp.json() if sub_resp.status_code == 201 else {}
        check("subcategory parent_id matches top_id", sub_json.get("parent_id") == top_id)
        sub_id = sub_json.get("id")

        # ---------- Пункт 9: запрет вложенности "подкатегория под подкатегорией" ----------
        print("\n=== Пункт 9: запрет создания подкатегории под подкатегорией ===")
        nested_resp = await client.post(
            "/api/v1/categories/expense",
            headers=headers,
            json={"name": "Too deep", "parent_id": sub_id},
        )
        check("POST под подкатегорией -> 400", nested_resp.status_code == 400, str(nested_resp.text))

        # ---------- Пункт 7: transaction_count / affected_transactions_count ----------
        print("\n=== Пункт 7: удаление income-категории с привязанной транзакцией ===")
        income_cat_id = uuid.uuid4()
        wallet_id = uuid.uuid4()
        txn_id = uuid.uuid4()
        async with async_session_factory() as session:
            income_cat = IncomeCategory(
                id=income_cat_id,
                family_budget_id=family_budget_id,
                name=f"Зарплата-{suffix}",
            )
            wallet = Wallet(
                id=wallet_id,
                family_budget_id=family_budget_id,
                name=f"ScriptWallet-{suffix}",
                currency="UZS",
            )
            session.add_all([income_cat, wallet])
            await session.flush()
            txn = Transaction(
                id=txn_id,
                family_budget_id=family_budget_id,
                type="income",
                wallet_id=wallet_id,
                amount=500,
                income_category_id=income_cat_id,
                created_by_user_id=owner.id,
                transaction_date=datetime.now(UTC),
            )
            session.add(txn)
            await session.commit()
        print(f"  Вставлены напрямую в БД: income_category={income_cat_id}, "
              f"wallet={wallet_id}, transaction={txn_id}")

        del_income_resp = await client.delete(
            f"/api/v1/categories/income/{income_cat_id}", headers=headers
        )
        check("DELETE income category -> 200", del_income_resp.status_code == 200, str(del_income_resp.text))
        del_income_json = del_income_resp.json() if del_income_resp.status_code == 200 else {}
        check(
            "affected_transactions_count == 1",
            del_income_json.get("affected_transactions_count") == 1,
            str(del_income_json),
        )

        async with async_session_factory() as session:
            txn_check = await session.get(Transaction, txn_id)
            check("транзакция не тронута (is_deleted == False)", txn_check is not None and txn_check.is_deleted is False)
            check("транзакция всё ещё ссылается на удалённую категорию", txn_check is not None and txn_check.income_category_id == income_cat_id)

        # ---------- Пункт 8: каскад soft-delete на подкатегории ----------
        print("\n=== Пункт 8: удаление top-level категории каскадно удаляет подкатегорию ===")
        del_top_resp = await client.delete(f"/api/v1/categories/expense/{top_id}", headers=headers)
        check("DELETE top-level category -> 200", del_top_resp.status_code == 200, str(del_top_resp.text))

        async with async_session_factory() as session:
            top_row = await session.get(ExpenseCategory, uuid.UUID(top_id))
            sub_row = await session.get(ExpenseCategory, uuid.UUID(sub_id))
            check("top-level категория is_deleted == True", top_row is not None and top_row.is_deleted is True)
            check("подкатегория is_deleted == True (каскад)", sub_row is not None and sub_row.is_deleted is True)

    print(f"\n===== ИТОГО: {passed} passed, {failed} failed =====")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
