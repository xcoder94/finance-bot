# Phase 1 — Quick Entry via Text Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Let a person write ordinary text to the Telegram bot and get expense/income records created immediately with PRD §7 cards (or a type question), without category questions.

**Architecture:** Aiogram text handler runs length/limit checks, builds a writer-scoped wallet list, calls a `MessageParser` interface (stub in tests; HTTP adapter inactive without env keys), resolves wallets/dates/categories on the bot side, creates transactions via existing service helpers (extended for parent-only and null category), and replies with cards or type-question blocks. Card callbacks handle delete and wallet change in-bot; «Изменить» is a WebApp button. Daily counters live on `family_budgets` and reset at Asia/Tashkent midnight. §8 transfer/exchange cards are never produced.

**Tech Stack:** Python, FastAPI (unchanged API surface except schema allowances), Aiogram 3, SQLAlchemy 2 async, Alembic, pytest, httpx (parser adapter only).

## Global Constraints

- Spec: `docs/tasks/phase-01-quick-entry-text.md` + PRD §7, §4 (counters/length/ops), §15.1–§15.3 (new-budget seed), §19.2 (chat refusals).
- Worker model: `composer-2.5` only.
- User-facing Russian: character-for-character from PRD / customer answers below. Banned words: ошибка, сессия, сервер, токен, запрос.
- No interim «разбираю…». No category questions. Only type question §7.6.
- §8 transfers/exchange: **do not implement**. If parser returns `transfer`/`exchange`, do not create §8 cards; drop those ops. If none remain, reply with §7.9 and spend unparsed.
- Parser: one interface. Tests use deterministic stub only — **no live model calls in pytest**. Real adapter reads `PARSER_PROVIDER`, `PARSER_API_KEY`, `PARSER_MODEL`; inactive when key missing. Stub must appear in phase report stubbed list. §20 prompt cache out of scope.
- §7.4 currency-missing copy (exact):
  - USD: `Кошелька в долларах у вас нет. Добавьте его в приложении, в настройках.`
  - UZS: `Кошелька в сумах у вас нет. Добавьте его в приложении, в настройках.`
- §7.5: `В одном сообщении можно записать не больше 5 операций. Разбейте на несколько сообщений.`
- §7.9: `Не нашёл сумму в сообщении.\nНапишите так: \`такси 25 тысяч\` или \`продукты 200 тыс с карты\``
- §7.11: `Не получилось записать — дело не в вашем сообщении. Попробуйте отправить его ещё раз через минуту или запишите операцию в приложении.`
- §19.2 length: `Сообщение слишком длинное — максимум 500 символов. Разбейте на несколько.`
- §19.2 model limit: `Сегодня записано 50 операций — это дневной предел на семью. Новые записи можно вносить с полуночи.` (number from config, not hard-coded 50 in the string builder — interpolate the configured limit).
- §19.2 unparsed limit: `Сегодня не удалось разобрать 20 сообщений — это дневной предел. Записи можно добавить в приложении.` (interpolate configured limit).
- Missing-record (acceptance 13; PRD English only): `Запись больше не существует.`
- Card buttons: `Кошелёк` · `Изменить` · `Удалить`. Type buttons: `Потратил` · `Получил`.
- Limits from config: `DAILY_MODEL_CALL_LIMIT` (default 50), `DAILY_UNPARSED_LIMIT` (default 20). Change applies same day.
- Model timeout 10s/attempt, up to 3 attempts on network/unavailable; never retry malformed request. Unparsed not spent on §7.11.
- New budgets only: §15.1 (7 parents / 23 subs) + §15.2 (5 income). No migration of existing families.
- Seed wallets order: Наличный сум, Карта сум, Наличный USD, Карта USD. Default wallet = Карта сум.
- Branch: `mvp2/phase-1-quick-entry-text`. Do not commit secrets. Report pytest before/after; list every stub/mock/disabled.
- Do not build mini-app edit forms, Settings default-wallet screen, personal-wallet UI, voice, receipts, or §8.

**Scope estimate:** 10 tasks · one feature branch off Phase 0.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/models/wallet.py` | `is_personal`, `owner_user_id` |
| `backend/app/models/user.py` | `default_wallet_id` |
| `backend/app/models/family_budget.py` | daily counter fields |
| `backend/alembic/versions/i9d0e1f2a3b4_phase1_quick_entry.py` | migration |
| `backend/app/config.py` | parser + limit env vars |
| `.env.example` | document new vars |
| `backend/bot/onboarding.py` | §15 seed + default wallet assignment |
| `backend/app/parsing/types.py` | parsed operation DTOs |
| `backend/app/parsing/base.py` | `MessageParser` protocol |
| `backend/app/parsing/stub.py` | deterministic stub for tests |
| `backend/app/parsing/http_adapter.py` | real provider adapter |
| `backend/app/parsing/factory.py` | `get_parser()` |
| `backend/app/services/quick_entry_dates.py` | relative date helpers |
| `backend/app/services/quick_entry_wallets.py` | visible wallets + resolve |
| `backend/app/services/quick_entry_counters.py` | Tashkent daily counters |
| `backend/app/services/quick_entry_balance.py` | per-wallet balance |
| `backend/app/services/transactions.py` | allow parent-only + null category for bot path |
| `backend/bot/quick_entry/texts.py` | all Russian refusal/card strings |
| `backend/bot/quick_entry/cards.py` | card format + keyboards |
| `backend/bot/quick_entry/pending.py` | store ambiguous ops for button tap |
| `backend/bot/quick_entry/handlers.py` | text + callback handlers |
| `backend/bot/main.py` | include quick-entry router |
| `backend/tests/test_quick_entry_*.py` | unit + integration with stub |

---

### Task 1: Schema — wallets personal, default wallet, daily counters

**Files:**
- Modify: `backend/app/models/wallet.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/family_budget.py`
- Create: `backend/alembic/versions/i9d0e1f2a3b4_phase1_quick_entry.py`
- Test: `backend/tests/test_quick_entry_schema.py`

**Interfaces:**
- Consumes: existing models / Alembic chain ending at `h8c9d0e1f2a3`
- Produces:
  - `Wallet.is_personal: bool` (default False), `Wallet.owner_user_id: uuid.UUID | None`
  - `User.default_wallet_id: uuid.UUID | None` (FK wallets, ON DELETE SET NULL)
  - `FamilyBudget.daily_model_calls: int` default 0, `daily_unparsed: int` default 0, `counters_day: date | None`

- [ ] **Step 1: Write failing model/migration smoke test**

```python
# backend/tests/test_quick_entry_schema.py
import pytest
from sqlalchemy import inspect
from app.db import engine

@pytest.mark.asyncio
async def test_phase1_columns_exist():
    async with engine.connect() as conn:
        def check(sync_conn):
            insp = inspect(sync_conn)
            w = {c["name"] for c in insp.get_columns("wallets")}
            u = {c["name"] for c in insp.get_columns("users")}
            f = {c["name"] for c in insp.get_columns("family_budgets")}
            assert {"is_personal", "owner_user_id"} <= w
            assert "default_wallet_id" in u
            assert {"daily_model_calls", "daily_unparsed", "counters_day"} <= f
        await conn.run_sync(check)
```

- [ ] **Step 2: Run test — expect FAIL (columns missing)**

Run: `cd backend && ./venv/bin/pytest tests/test_quick_entry_schema.py -v`
Expected: FAIL / columns missing.

- [ ] **Step 3: Update models + Alembic migration**

Add columns as in Interfaces. Migration `down_revision = "h8c9d0e1f2a3"`. For existing rows: `is_personal=false`, counters 0, `counters_day=null`, `default_wallet_id=null`.

- [ ] **Step 4: Upgrade DB and run test — PASS**

```bash
cd backend && ./venv/bin/alembic upgrade head && ./venv/bin/pytest tests/test_quick_entry_schema.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/wallet.py backend/app/models/user.py backend/app/models/family_budget.py backend/alembic/versions/i9d0e1f2a3b4_phase1_quick_entry.py backend/tests/test_quick_entry_schema.py
git commit -m "$(cat <<'EOF'
feat: add default wallet, personal flag, and daily counters columns

EOF
)"
```

---

### Task 2: Config — parser env + daily limits

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_quick_entry_config.py`

**Interfaces:**
- Consumes: existing `config.py` dotenv load
- Produces: exports
  - `PARSER_PROVIDER: str | None`
  - `PARSER_API_KEY: str | None`
  - `PARSER_MODEL: str | None`
  - `DAILY_MODEL_CALL_LIMIT: int` (default 50)
  - `DAILY_UNPARSED_LIMIT: int` (default 20)

- [ ] **Step 1: Failing test that imports limits**

```python
from app import config

def test_daily_limits_defaults():
    assert isinstance(config.DAILY_MODEL_CALL_LIMIT, int)
    assert config.DAILY_MODEL_CALL_LIMIT >= 1
    assert isinstance(config.DAILY_UNPARSED_LIMIT, int)
    assert config.DAILY_UNPARSED_LIMIT >= 1
```

- [ ] **Step 2: Run — FAIL (AttributeError)**

- [ ] **Step 3: Implement config loading**

```python
PARSER_PROVIDER = os.environ.get("PARSER_PROVIDER") or None
PARSER_API_KEY = os.environ.get("PARSER_API_KEY") or None
PARSER_MODEL = os.environ.get("PARSER_MODEL") or None
DAILY_MODEL_CALL_LIMIT = int(os.environ.get("DAILY_MODEL_CALL_LIMIT", "50"))
DAILY_UNPARSED_LIMIT = int(os.environ.get("DAILY_UNPARSED_LIMIT", "20"))
```

Document in `.env.example` (no real secrets).

- [ ] **Step 4: Run test — PASS; commit**

```bash
git commit -m "$(cat <<'EOF'
chore: add parser and daily-limit configuration

EOF
)"
```

---

### Task 3: §15 category seed + wallet order + default wallet on /start

**Files:**
- Modify: `backend/bot/onboarding.py`
- Modify: `backend/tests/test_onboarding.py`
- Test: `backend/tests/test_onboarding.py`

**Interfaces:**
- Consumes: Task 1 columns
- Produces: `copy_seed_data` seeds §15.1/§15.2 exactly; wallets in order Наличный сум, Карта сум, Наличный USD, Карта USD (`is_personal=False`); after owner/member user create, `user.default_wallet_id` = wallet named `Карта сум`

**Exact seed — income (`SEED_INCOME_CATEGORIES`):**
Зарплата, Подработка, Подарки, Переводы от родных, Прочее

**Exact seed — expense parents/subs (`SEED_EXPENSE_CATEGORIES`):**
- Еда → Продукты · Кафе и рестораны · Доставка
- Транспорт → Такси · Топливо · Общественный транспорт · Обслуживание авто
- Дом → Аренда · Коммунальные услуги · Связь и интернет · Ремонт и обустройство
- Дети → Садик и школа · Кружки и репетиторы · Детские товары
- Здоровье → Лекарства и аптека · Врачи и клиники · Стоматология
- События и тои → Тои и маърака · Подарки
- Покупки и досуг → Одежда · Развлечения · Подписки · Красота и уход

**SEED_WALLETS order:**
```python
[
    ("Наличный сум", "UZS", "cash_uzs"),
    ("Карта сум", "UZS", "card_uzs"),
    ("Наличный USD", "USD", "cash_usd"),
    ("Карта USD", "USD", "card_usd"),
]
```

- [ ] **Step 1: Update onboarding tests to expect 5 income, 7 parents, 23 subs, default Карта сум**

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Replace seed constants; set `default_wallet_id` after seed for owner; for member joining, set default to family's `Карта сум` shared wallet**

Helper:

```python
async def assign_default_card_uzs(session, user: User) -> None:
    stmt = select(Wallet).where(
        Wallet.family_budget_id == user.family_budget_id,
        Wallet.name == "Карта сум",
        Wallet.is_deleted.is_(False),
        Wallet.is_personal.is_(False),
    )
    wallet = await session.scalar(stmt)
    if wallet is not None:
        user.default_wallet_id = wallet.id
```

- [ ] **Step 4: Run onboarding tests — PASS; commit**

```bash
git commit -m "$(cat <<'EOF'
feat: seed MVP2 categories and assign default Карта сум

EOF
)"
```

---

### Task 4: Parser interface + stub + inactive HTTP adapter

**Files:**
- Create: `backend/app/parsing/__init__.py`
- Create: `backend/app/parsing/types.py`
- Create: `backend/app/parsing/base.py`
- Create: `backend/app/parsing/stub.py`
- Create: `backend/app/parsing/http_adapter.py`
- Create: `backend/app/parsing/factory.py`
- Test: `backend/tests/test_quick_entry_parser.py`

**Interfaces:**
- Consumes: Task 2 config
- Produces:

```python
# types.py
from dataclasses import dataclass
from typing import Literal

OpType = Literal["expense", "income", "ambiguous", "transfer", "exchange"]

@dataclass(frozen=True)
class ParsedOperation:
    type: OpType
    amount: int | None  # minor units same as DB (whole сум / dollars as int)
    currency: Literal["UZS", "USD"] | None
    wallet_hint: str | None
    category: str | None  # may be "Parent: Sub" or bare name
    comment: str | None

@dataclass(frozen=True)
class ParseRequest:
    text: str
    wallet_names: list[str]  # writer-visible only
    expense_category_names: list[str]
    income_category_names: list[str]

@dataclass(frozen=True)
class ParseResponse:
    operations: list[ParsedOperation]

class ParserUnavailable(Exception): ...
class ParserMalformed(Exception): ...  # do not retry

# base.py
class MessageParser(Protocol):
    async def parse(self, request: ParseRequest) -> ParseResponse: ...

# factory.py
def get_parser() -> MessageParser:
    # If PARSER_API_KEY missing → StubParser only used when explicitly injected in tests;
    # production get_parser returns HttpParser if key set else a NoOp that raises ParserUnavailable
```

**Stub behaviour (tests inject this):** map fixture texts deterministically, e.g. `такси 25 тысяч` → one expense amount 25000 UZS category Такси; configurable via constructor `responses: dict[str, ParseResponse]`.

**HttpParser:** POST/chat per `PARSER_PROVIDER` (`openai` or `anthropic` minimal). Timeout 10s. Retries: up to 3 total on network / 5xx / 429; **never** retry 4xx malformed. If no API key: `get_parser()` raises `ParserUnavailable` on `parse` (inactive).

- [ ] **Step 1: Write tests for stub mapping + factory inactive without key**

- [ ] **Step 2: RED then implement — GREEN**

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: add message parser interface with stub and HTTP adapter

EOF
)"
```

---

### Task 5: Date helpers + category strip + comment cleanup

**Files:**
- Create: `backend/app/services/quick_entry_dates.py`
- Create: `backend/app/services/quick_entry_categories.py`
- Test: `backend/tests/test_quick_entry_dates.py`

**Interfaces:**
- Produces:

```python
def tashkent_today() -> date: ...
def resolve_operation_date(text: str, now: datetime | None = None) -> date:
    """Relative markers and weekdays; lookback max 31 days; future → today.
    Markers: вчера, позавчера, N дня/дней назад, в понедельник, в прошлую пятницу.
    Weekday without 'прошл' = most recent past occurrence.
    """

def strip_date_words(comment: str | None, original_text: str) -> str | None:
    """Remove date marker words from comment; truncate to 200 chars."""

def strip_parent_category(raw: str | None) -> str | None:
    """If 'Parent: Sub' / 'Parent：Sub', return Sub stripped; else raw."""
```

- [ ] **Step 1: TDD cases** — `вчера` → yesterday; weekday; 40 days ignored (today); future → today; `Транспорт: Такси` → `Такси`

- [ ] **Step 2: Implement — PASS; commit**

```bash
git commit -m "$(cat <<'EOF'
feat: add quick-entry date and category string helpers

EOF
)"
```

---

### Task 6: Wallet visibility, resolve, per-wallet balance, counters

**Files:**
- Create: `backend/app/services/quick_entry_wallets.py`
- Create: `backend/app/services/quick_entry_balance.py`
- Create: `backend/app/services/quick_entry_counters.py`
- Test: `backend/tests/test_quick_entry_wallets.py`, `backend/tests/test_quick_entry_counters.py`

**Interfaces:**

```python
async def list_wallets_for_parse(session, family_budget_id, writer: User) -> list[Wallet]:
    """Up to 10 shared + all personal of writer only. Never other members' personal."""

async def resolve_wallet(
    *,
    session,
    family_budget_id,
    writer: User,
    wallet_hint: str | None,
    currency: Literal["UZS","USD"] | None,
    default_wallet: Wallet,
) -> Wallet | CurrencyMissing:
    """Match hint by meaning (casefold / contains). Miss → default.
    If currency set and chosen wallet differs → switch to any wallet in that currency
    (shared or writer's personal). If none → CurrencyMissing(currency).
    """

class CurrencyMissing:
    currency: Literal["UZS", "USD"]

async def wallet_balance(session, wallet_id: uuid.UUID) -> int:
    """Sum income - expense - transfers out + transfers in for this wallet (active only)."""

async def ensure_counters_day(budget: FamilyBudget, today: date) -> None: ...
async def can_model_call(budget, limit: int) -> bool: ...
async def can_unparsed(budget, limit: int) -> bool: ...
async def spend_model_call(budget) -> None: ...
async def spend_unparsed(budget) -> None: ...
```

Acceptance 14 test: member B's `list_wallets_for_parse` names must not include member A's personal wallet name.

Counter tests: reset at Tashkent midnight boundary; spend rules; §7.11 path does not call `spend_unparsed`.

- [ ] **Step 1–4: TDD each module; commit**

```bash
git commit -m "$(cat <<'EOF'
feat: add wallet visibility, balances, and daily counters

EOF
)"
```

---

### Task 7: Bot transaction create path (parent-only + Без категории)

**Files:**
- Modify: `backend/app/services/transactions.py`
- Create: `backend/app/services/quick_entry_create.py`
- Test: `backend/tests/test_quick_entry_create.py`

**Interfaces:**

```python
async def create_quick_entry_expense(
    session, user: User, *,
    amount: int, wallet_id: uuid.UUID,
    expense_category_id: uuid.UUID | None,  # parent or sub or None (= Без категории)
    comment: str | None,
    transaction_date: datetime,  # Tashkent calendar date at noon UTC+5 ok
) -> Transaction: ...

async def create_quick_entry_income(...) -> Transaction: ...

async def resolve_category_id(
    session, family_budget_id, *,
    op_type: Literal["expense","income"],
    category_name: str | None,
    button_choice: Literal["expense","income"] | None = None,
) -> uuid.UUID | None:
    """Match by subcategory name first, then parent, then income name.
    Подарки collision: if button_choice income → income Подарки; if expense → sub under События и тои.
    None / empty → None (Без категории).
    """
```

Change `validate_expense_refs` used by **API** to still require subcategory for mini-app manual entry OR add a flag. Preferred: keep API validation unchanged; bot path uses `quick_entry_create` that allows parent or null without calling the subcategory-only check.

- [ ] **Step 1: TDD parent-only expense + null category; commit**

```bash
git commit -m "$(cat <<'EOF'
feat: create quick-entry transactions with parent or no category

EOF
)"
```

---

### Task 8: Card texts, formatters, keyboards

**Files:**
- Create: `backend/bot/quick_entry/__init__.py`
- Create: `backend/bot/quick_entry/texts.py`
- Create: `backend/bot/quick_entry/cards.py`
- Test: `backend/tests/test_quick_entry_cards.py`

**Interfaces:**

```python
# texts.py — all PRD strings as constants / formatters
def currency_missing_text(currency: Literal["UZS","USD"]) -> str: ...
def model_limit_text(limit: int) -> str: ...
def unparsed_limit_text(limit: int) -> str: ...
MSG_TOO_LONG = "Сообщение слишком длинное — максимум 500 символов. Разбейте на несколько."
MSG_TOO_MANY_OPS = "В одном сообщении можно записать не больше 5 операций. Разбейте на несколько сообщений."
MSG_NO_AMOUNT = "Не нашёл сумму в сообщении.\nНапишите так: `такси 25 тысяч` или `продукты 200 тыс с карты`"
MSG_MODEL_FAIL = "Не получилось записать — дело не в вашем сообщении. Попробуйте отправить его ещё раз через минуту или запишите операцию в приложении."
MSG_GONE = "Запись больше не существует."
MSG_TYPE_QUESTION = "Не понял, это трата или доход?"

def format_amount(amount: int, currency: str) -> str:  # "25 000 сум" / "10 $"
def format_card(*, sign: str, amount: int, currency: str, category_label: str,
                comment: str | None, wallet_name: str, op_date: date, balance: int) -> str:
    """§7.1 layout, no field labels."""

def card_keyboard(transaction_id: uuid.UUID) -> InlineKeyboardMarkup:
    """Кошелёк (callback), Изменить (WebApp MINI_APP_URL?tx=<id>), Удалить (callback)."""

def type_question_keyboard(pending_id: str) -> InlineKeyboardMarkup:
    """Потратил / Получил callbacks."""

def wallet_picker_keyboard(transaction_id, wallets: list[Wallet]) -> InlineKeyboardMarkup: ...
```

Sign: expense `➖`, income `➕`. Category label `Без категории` when ids null.

- [ ] **Step 1: TDD format_card matches §7.1 shape; commit**

```bash
git commit -m "$(cat <<'EOF'
feat: add quick-entry card formatting and keyboards

EOF
)"
```

---

### Task 9: Quick-entry text handler + type-question persistence

**Files:**
- Create: `backend/bot/quick_entry/pending.py`
- Create: `backend/bot/quick_entry/handlers.py`
- Modify: `backend/bot/main.py`
- Test: `backend/tests/test_quick_entry_flow.py`

**Interfaces:**
- Consumes: Tasks 4–8
- Produces: router handling plain text (not commands) for registered users

**Handler algorithm (`handle_quick_entry_text`):**
1. If not registered → existing onboarding `not_registered` (or ignore if onboarding owns it).
2. If `len(text) > 500` → §19.2 length; **no** counter spend; return.
3. `ensure_counters_day`; if not `can_model_call` → §19.2 model limit text; return.
4. Build wallet names via `list_wallets_for_parse` + category name lists; call parser.
5. On `ParserUnavailable` after retries → §7.11; **do not** spend unparsed; return. On success path spend **one** model call (even for multi-op).
6. Bot recounts `len(operations)` after dropping transfer/exchange. If >5 → §7.5; spend unparsed; no writes.
7. Split ops: clear (expense/income with amount) vs ambiguous (type ambiguous or amount present but type ambiguous) vs no-amount.
8. If no clear and no ambiguous (e.g. no amount) → §7.9; spend unparsed.
9. For each clear op in order: resolve date from **original message text** (same date for all unless per-op hints exist — use message-level date from full text); resolve wallet; on CurrencyMissing → that op refused with §7.4 text, spend unparsed once per such refusal (if multiple currency-missing in one message, each spends); create txn; send card with running balance.
10. Then send ambiguous questions as a block (`format` amount + category + MSG_TYPE_QUESTION + buttons). Persist pending row (DB table or JSON in callback_data + short-lived table).

**Pending storage:** create table `quick_entry_pending` (`id`, `user_id`, `family_budget_id`, `amount`, `currency`, `wallet_id`, `category_raw`, `comment`, `operation_date`, `created_at`) so buttons live indefinitely.

**Order:** all cards first, then questions. No rewrite of earlier cards on later tap.

Inject `MessageParser` via module-level setter for tests (`set_parser_override`).

- [ ] **Step 1: Integration tests with StubParser fixtures:**
  - single expense card fields
  - three ops → three cards
  - ambiguous → question, no row
  - currency missing → §7.4
  - length → no model call (spy)
  - >5 ops → refusal
  - §7.11 does not increment unparsed
  - member B wallet leak check on ParseRequest.wallet_names

- [ ] **Step 2: Implement handler + wire router in `main.py` after onboarding**

- [ ] **Step 3: PASS; commit**

```bash
git commit -m "$(cat <<'EOF'
feat: handle quick-entry text messages with stubbed parser

EOF
)"
```

---

### Task 10: Card callbacks + type buttons + gone checks

**Files:**
- Modify: `backend/bot/quick_entry/handlers.py`
- Modify: `backend/bot/quick_entry/pending.py` (if needed)
- Test: `backend/tests/test_quick_entry_callbacks.py`

**Interfaces:**
- Callback prefixes: `qe:del:<txn_id>`, `qe:wal:<txn_id>`, `qe:walset:<txn_id>:<wallet_id>`, `qe:type:<pending_id>:expense`, `qe:type:<pending_id>:income`
- «Изменить»: WebApp button only (no callback) — URL `f"{MINI_APP_URL}?tx={transaction_id}"`

**Behaviour:**
1. Any of delete / wallet-list / wallet-set: if transaction missing or soft-deleted → answer `MSG_GONE`, do not recreate.
2. Delete: soft-delete, edit message to show gone or remove buttons; no confirmation.
3. Кошелёк: show inline wallet list (shared + writer's personal, same visibility rules).
4. Wallet set: update `transaction.wallet_id`, recalculate balance, re-render card text + restore three buttons.
5. Type button: spend **one model-call quota** at tap (PRD §7.6); create record with original pending `operation_date`; resolve Подарки by button; if no category → Без категории; replace question message with card; if pending already consumed / txn path fails → `MSG_GONE` or ignore double-tap.

- [ ] **Step 1: TDD delete / gone / wallet change / type tap; commit**

```bash
git commit -m "$(cat <<'EOF'
feat: handle quick-entry card and type-question buttons

EOF
)"
```

---

## Self-review checklist (orchestrator)

1. Spec coverage: §7.1–7.11, §4 counters/length, §15 seed, §19.2, acceptance 14 wallet filter, card buttons — mapped to tasks 1–10.
2. No §8 cards; transfer/exchange dropped.
3. No placeholders left for §7.4 copy.
4. Stub-only pytest; live adapter inactive without key.
5. Types consistent across tasks (`ParsedOperation`, `CurrencyMissing`, pending table).

## Execution

Customer chose **Subagent-Driven Development** with `composer-2.5`. Execute continuously; stop only on BLOCKED / true UX ambiguity / out-of-spec.
