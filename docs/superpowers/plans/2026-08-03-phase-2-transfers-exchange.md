# Phase 2 — Transfers and Exchange via Quick Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Let a person write about moving money between wallets; the bot creates a same-currency transfer or a rate-marked exchange correctly, or refuses with the exact §8.3 text when a rate is missing — money never silently moves at the wrong scale (§8.4).

**Architecture:** Extend `ParsedOperation` with from/to wallet hints and optional rate. Keep parser prompt as **immutable instructions first, mutable per-request payload second** (Phase 13 only turns on cache measurement). Bot-side pure helpers detect rate-marker words and enforce §8.4 before any write. Reuse existing `create_transfer_transaction` (DB type stays `transfer` for both transfer and exchange). Cards use §8.2 / §8.3 layouts with only `Изменить` · `Удалить`. Expense/income path from Phase 1 stays intact.

**Tech Stack:** Python, FastAPI (unchanged API), Aiogram 3, SQLAlchemy 2 async, pytest, httpx (parser adapter only; live calls inactive without keys).

## Global Constraints

- Spec: `docs/tasks/phase-02-transfers-exchange.md` + PRD §8 (and Phase 1 counters/length still apply).
- Worker model: `composer-2.5` only.
- User-facing Russian: character-for-character from PRD. Banned words: ошибка, сессия, сервер, токен, запрос.
- §8.3 refusal (exact):
  ```
  Перевод между кошельками в разных валютах — это обмен, для него нужен курс.
  Сделайте его в приложении.
  ```
- Rate recognised **only** with explicit marker words `по` / `по курсу` (bot-side check of user text; never assume a bare second number is a rate).
- §8.4: before any write, if op is transfer/exchange, source and destination currencies differ, and no rate → discard parse, send §8.3 refusal, spend unparsed. Independent of the model.
- Transfer card buttons: exactly `Изменить` · `Удалить`. **No `Кошелёк`.**
- Neutral colour / no minus sign on amounts for transfer and exchange (§5 / §8.2).
- Counters: one model call per message when model is called; refusal paths that called the model spend unparsed per §8.3.
- Parser: `PARSER_*` env only; model name never hard-coded. Tests use stub only — **no live model calls in pytest**.
- Prompt assembly from this phase on: **immutable part first, mutable part second**. Do not rearrange later for Phase 13.
- No dead controls: do not render buttons/tabs that do nothing. Transfer/exchange cards show only the two working buttons from §8.
- Do not build voice, receipt photo, personal-wallet UI, goals, members, change log, mini-app redesign, notifications, prompt caching enablement, `/start` rewrite, or mini-app transfer form (§17.7).
- Branch: `mvp2/phase-2-transfers-exchange` off current `main`. Do not commit secrets. Report pytest before/after; list every stub/mock/disabled.
- Do not edit `docs/PRD.md`.

**Scope estimate:** 7 tasks · one feature branch off Phase 1 main.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/parsing/types.py` | Add `from_wallet_hint`, `to_wallet_hint`, `rate` on `ParsedOperation` |
| `backend/app/parsing/prompt.py` | Immutable system prompt + mutable user payload builders (cache-ready order) |
| `backend/app/parsing/http_adapter.py` | Use prompt builders; parse new fields |
| `backend/app/parsing/stub.py` | Fixtures for transfer / exchange / no-rate cases |
| `backend/app/services/quick_entry_transfer.py` | Rate-marker check, §8.4 gate, resolve from/to wallets, create transfer |
| `backend/bot/quick_entry/texts.py` | §8.3 refusal constant |
| `backend/bot/quick_entry/cards.py` | `format_transfer_card`, `format_exchange_card`, `transfer_card_keyboard` |
| `backend/bot/quick_entry/handlers.py` | Process transfer/exchange; stop dropping them; wire refusal |
| `backend/tests/test_quick_entry_transfer_*.py` | Unit + flow tests |

---

### Task 1: Extend ParsedOperation + cache-ready prompt builders

**Files:**
- Modify: `backend/app/parsing/types.py`
- Create: `backend/app/parsing/prompt.py`
- Modify: `backend/app/parsing/http_adapter.py`
- Modify: `backend/tests/test_quick_entry_parser.py`

**Interfaces:**
- Consumes: existing `ParsedOperation`, `ParseRequest`, `HttpParser`
- Produces:
  - `ParsedOperation` fields (new, default `None`): `from_wallet_hint: str | None`, `to_wallet_hint: str | None`, `rate: int | None`
  - `IMMUTABLE_PARSER_INSTRUCTIONS: str` — fixed system text (includes transfer/exchange + rate marker rules)
  - `build_mutable_parser_payload(request: ParseRequest) -> str` — JSON with text + wallet/category lists
  - `build_parser_messages(request) -> list[dict]` with order `[immutable system, mutable user]`
  - HTTP adapter parses the three new fields; ignores unknown keys still forbidden only for type

- [ ] **Step 1: Write failing tests for new fields and prompt order**

```python
# append to backend/tests/test_quick_entry_parser.py
from app.parsing.prompt import (
    IMMUTABLE_PARSER_INSTRUCTIONS,
    build_mutable_parser_payload,
    build_parser_messages,
)

def test_parsed_operation_accepts_transfer_fields():
    op = ParsedOperation(
        type="transfer",
        amount=500_000,
        currency="UZS",
        wallet_hint=None,
        category=None,
        comment=None,
        from_wallet_hint="карта",
        to_wallet_hint="наличные",
        rate=None,
    )
    assert op.from_wallet_hint == "карта"
    assert op.to_wallet_hint == "наличные"
    assert op.rate is None


def test_prompt_immutable_then_mutable_order():
    req = ParseRequest(
        text="переложил 500 тысяч с карты на наличные",
        wallet_names=["Карта сум", "Наличный сум"],
        expense_category_names=["Такси"],
        income_category_names=["Зарплата"],
    )
    messages = build_parser_messages(req)
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == IMMUTABLE_PARSER_INSTRUCTIONS
    assert "по курсу" in IMMUTABLE_PARSER_INSTRUCTIONS
    assert "transfer" in IMMUTABLE_PARSER_INSTRUCTIONS
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == build_mutable_parser_payload(req)
    assert "переложил 500 тысяч" in messages[1]["content"]
```

- [ ] **Step 2: Run tests — expect FAIL (fields / prompt module missing)**

Run: `cd backend && ./venv/bin/pytest tests/test_quick_entry_parser.py::test_parsed_operation_accepts_transfer_fields tests/test_quick_entry_parser.py::test_prompt_immutable_then_mutable_order -v`
Expected: FAIL (import or attribute error).

- [ ] **Step 3: Implement types + prompt + adapter**

Update `ParsedOperation`:

```python
@dataclass(frozen=True)
class ParsedOperation:
    type: OpType
    amount: int | None
    currency: Literal["UZS", "USD"] | None
    wallet_hint: str | None
    category: str | None
    comment: str | None
    from_wallet_hint: str | None = None
    to_wallet_hint: str | None = None
    rate: int | None = None
```

Create `backend/app/parsing/prompt.py`:

```python
import json

from app.parsing.types import ParseRequest

IMMUTABLE_PARSER_INSTRUCTIONS = (
    "Parse family budget chat messages. Reply with JSON only, no markdown:\n"
    '{"operations":[{"type":"expense|income|ambiguous|transfer|exchange",'
    '"amount":integer_or_null,"currency":"UZS|USD"|null,'
    '"wallet_hint":string_or_null,'
    '"from_wallet_hint":string_or_null,"to_wallet_hint":string_or_null,'
    '"rate":integer_or_null,'
    '"category":string_or_null,"comment":string_or_null}]}\n'
    "Rules:\n"
    "- Same-currency move between two wallets → type transfer; set from_wallet_hint and to_wallet_hint; rate null.\n"
    "- Different-currency move → type exchange; set from_wallet_hint, to_wallet_hint, and rate only when the text "
    "contains an explicit rate marker word («по» or «по курсу»). If no marker, rate must be null.\n"
    "- Never invent a rate from a bare second number without «по» / «по курсу».\n"
    "- expense/income/ambiguous: from_wallet_hint, to_wallet_hint, rate are null; use wallet_hint."
)


def build_mutable_parser_payload(request: ParseRequest) -> str:
    return json.dumps(
        {
            "text": request.text,
            "wallet_names": request.wallet_names,
            "expense_category_names": request.expense_category_names,
            "income_category_names": request.income_category_names,
        },
        ensure_ascii=False,
    )


def build_parser_messages(request: ParseRequest) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": IMMUTABLE_PARSER_INSTRUCTIONS},
        {"role": "user", "content": build_mutable_parser_payload(request)},
    ]
```

In `http_adapter.py`: remove local `_SYSTEM_PROMPT` / `_build_user_content`; use `build_parser_messages`. In `_parse_operations_payload`, read optional `from_wallet_hint`, `to_wallet_hint`, `rate` (int or null only). Pass them into `ParsedOperation`.

In `_post`, for openai use `messages=build_parser_messages(request)`; for anthropic use `system=IMMUTABLE_PARSER_INSTRUCTIONS` and user content from `build_mutable_parser_payload(request)`.

- [ ] **Step 4: Run focused tests — PASS; full suite green**

Run: `cd backend && ./venv/bin/pytest tests/test_quick_entry_parser.py -v && ./venv/bin/pytest -q`
Expected: all PASS (186+ new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/types.py backend/app/parsing/prompt.py backend/app/parsing/http_adapter.py backend/tests/test_quick_entry_parser.py
git commit -m "$(cat <<'EOF'
feat: extend parser ops with transfer fields and cache-ready prompt

EOF
)"
```

---

### Task 2: Stub fixtures for §8 acceptance sentences

**Files:**
- Modify: `backend/app/parsing/stub.py`
- Create: `backend/tests/test_quick_entry_transfer_stub.py`

**Interfaces:**
- Consumes: `StubParser`, extended `ParsedOperation`
- Produces: default stub map entries for the Phase 2 acceptance texts (Russian + Uzbek cross-currency)

- [ ] **Step 1: Write failing stub tests**

```python
# backend/tests/test_quick_entry_transfer_stub.py
import pytest
from app.parsing.stub import StubParser
from app.parsing.types import ParseRequest

def _req(text: str) -> ParseRequest:
    return ParseRequest(text=text, wallet_names=[], expense_category_names=[], income_category_names=[])

@pytest.mark.anyio
async def test_stub_same_currency_transfer():
    op = (await StubParser().parse(_req("переложил 500 тысяч с карты на наличные"))).operations[0]
    assert op.type == "transfer"
    assert op.amount == 500_000
    assert op.currency == "UZS"
    assert op.from_wallet_hint is not None
    assert op.to_wallet_hint is not None
    assert op.rate is None

@pytest.mark.anyio
async def test_stub_exchange_with_rate_marker():
    op = (await StubParser().parse(_req("поменял 100 долларов на сумы по 12800"))).operations[0]
    assert op.type == "exchange"
    assert op.amount == 100
    assert op.currency == "USD"
    assert op.rate == 12_800

@pytest.mark.anyio
async def test_stub_cross_currency_without_rate_russian():
    op = (await StubParser().parse(_req("перевел с карты доллара на карту сум 50$"))).operations[0]
    assert op.type in ("transfer", "exchange")
    assert op.amount == 50
    assert op.rate is None

@pytest.mark.anyio
async def test_stub_cross_currency_without_rate_uzbek():
    op = (await StubParser().parse(_req("dollar kartasidan so'm kartasiga 50$ o'tkazdim"))).operations[0]
    assert op.type in ("transfer", "exchange")
    assert op.amount == 50
    assert op.rate is None

@pytest.mark.anyio
async def test_stub_exchange_number_without_po_marker_has_null_rate():
    op = (await StubParser().parse(_req("поменял 100 долларов на сумы 12800"))).operations[0]
    assert op.type == "exchange"
    assert op.rate is None
```

- [ ] **Step 2: Run — expect FAIL (empty stub responses)**

Run: `cd backend && ./venv/bin/pytest tests/test_quick_entry_transfer_stub.py -v`
Expected: FAIL (index/empty operations).

- [ ] **Step 3: Add stub defaults**

In `stub.py` `_DEFAULT_RESPONSES`, add the five texts above with realistic hints (`карта`/`наличные`/`карта доллара`/`карта сум`/`Карта USD` etc. matching seed wallet names where helpful). Keep existing `такси 25 тысяч`.

- [ ] **Step 4: Run stub tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/stub.py backend/tests/test_quick_entry_transfer_stub.py
git commit -m "$(cat <<'EOF'
feat: add stub parser fixtures for transfer and exchange

EOF
)"
```

---

### Task 3: Rate markers + §8.4 sanity gate (pure)

**Files:**
- Create: `backend/app/services/quick_entry_transfer.py` (helpers only in this task)
- Create: `backend/tests/test_quick_entry_transfer_sanity.py`

**Interfaces:**
- Consumes: `ParsedOperation`, wallet currency strings
- Produces:
  - `RATE_MARKER_RE` / `text_has_rate_marker(text: str) -> bool` — True iff `по курсу` or standalone `по` as a word (Cyrillic), case-insensitive
  - `effective_rate(op: ParsedOperation, source_text: str) -> int | None` — returns `op.rate` only if rate is positive int **and** `text_has_rate_marker(source_text)`; else `None`
  - `needs_exchange_refusal(*, from_currency: str, to_currency: str, rate: int | None) -> bool` — True when currencies differ and rate is None
  - Dataclass or constant for refusal decision (no I/O)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_quick_entry_transfer_sanity.py
from app.parsing.types import ParsedOperation
from app.services.quick_entry_transfer import (
    effective_rate,
    needs_exchange_refusal,
    text_has_rate_marker,
)

def test_rate_marker_po_and_po_kursu():
    assert text_has_rate_marker("поменял 100 долларов на сумы по 12800")
    assert text_has_rate_marker("обмен по курсу 12800")
    assert not text_has_rate_marker("поменял 100 долларов на сумы 12800")
    assert not text_has_rate_marker("перевел с карты доллара на карту сум 50$")

def test_effective_rate_requires_marker():
    op = ParsedOperation(
        type="exchange", amount=100, currency="USD",
        wallet_hint=None, category=None, comment=None,
        from_wallet_hint="карта", to_wallet_hint="карта", rate=12_800,
    )
    assert effective_rate(op, "поменял 100 долларов на сумы по 12800") == 12_800
    assert effective_rate(op, "поменял 100 долларов на сумы 12800") is None

def test_needs_exchange_refusal_cross_currency_without_rate():
    assert needs_exchange_refusal(from_currency="USD", to_currency="UZS", rate=None) is True
    assert needs_exchange_refusal(from_currency="USD", to_currency="UZS", rate=12_800) is False
    assert needs_exchange_refusal(from_currency="UZS", to_currency="UZS", rate=None) is False
```

- [ ] **Step 2: Run — FAIL (module missing)**

- [ ] **Step 3: Implement helpers in `quick_entry_transfer.py`**

Use `re` with Unicode word boundaries for `по` / `по курсу`. Do not call the DB.

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quick_entry_transfer.py backend/tests/test_quick_entry_transfer_sanity.py
git commit -m "$(cat <<'EOF'
feat: add rate-marker and §8.4 exchange refusal helpers

EOF
)"
```

---

### Task 4: Resolve from/to wallets + create quick-entry transfer

**Files:**
- Modify: `backend/app/services/quick_entry_transfer.py`
- Modify: `backend/app/services/quick_entry_wallets.py` (optional small helper export if needed)
- Create: `backend/tests/test_quick_entry_transfer_create.py`

**Interfaces:**
- Consumes: `list_wallets_for_parse`, `_wallet_matches_hint` (export a public `wallet_matches_hint` if currently private), `create_transfer_transaction`, `TransferCreate`, `compute_transfer_amounts` / validate
- Produces:
  - `@dataclass TransferWalletsMissing` / reuse patterns — result type:
    - `ResolvedTransferWallets(from_wallet: Wallet, to_wallet: Wallet)`
    - or a refusal/missing reason
  - `async def resolve_transfer_wallets(session, family_budget_id, writer, *, from_hint, to_hint, amount_currency, default_wallet) -> ResolvedTransferWallets | CurrencyMissing`
    - Match from/to by hints among visible wallets; if hint missing, prefer currency-compatible shared wallet; never pick the same wallet for both; if a required currency has no wallet → `CurrencyMissing`
  - `async def create_quick_entry_transfer(session, user, *, from_wallet_id, to_wallet_id, amount, rate: Decimal | None, comment, transaction_date) -> Transaction` — wraps `create_transfer_transaction` with `TransferCreate` (no HTTPException leak to bot: catch and re-raise as domain error OR validate first with `validate_transfer_refs`)

Prefer calling `validate_transfer_refs` + constructing `Transaction` the same way as `create_transfer_transaction` (may call `create_transfer_transaction` directly with a `TransferCreate` body).

- [ ] **Step 1: Write failing create/resolve tests** (use existing DB fixtures from `test_quick_entry_create.py` / flow helpers)

```python
# backend/tests/test_quick_entry_transfer_create.py
# Use the same family/user/wallet seed pattern as other quick_entry tests.
# 1) resolve two UZS wallets by hints "карта" / "наличн"
# 2) create_quick_entry_transfer same currency → type transfer, to_amount == amount, rate None
# 3) create with USD→UZS + rate 12800 → to_amount == 100*12800
# Assert balances via wallet_balance change.
```

Copy fixture setup from `backend/tests/test_quick_entry_create.py` (read that file; do not invent a new DB harness).

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement resolve + create**

- [ ] **Step 4: Run create tests — PASS; full suite still green**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quick_entry_transfer.py backend/app/services/quick_entry_wallets.py backend/tests/test_quick_entry_transfer_create.py
git commit -m "$(cat <<'EOF'
feat: resolve transfer wallets and create quick-entry transfers

EOF
)"
```

---

### Task 5: Transfer/exchange card texts and keyboards

**Files:**
- Modify: `backend/bot/quick_entry/texts.py`
- Modify: `backend/bot/quick_entry/cards.py`
- Create: `backend/tests/test_quick_entry_transfer_cards.py`

**Interfaces:**
- Consumes: `format_amount`, `_format_date`, `MINI_APP_URL`
- Produces:
  - `MSG_EXCHANGE_RATE_REQUIRED` exact two-line §8.3 refusal
  - `format_transfer_card(*, amount, currency, from_wallet_name, to_wallet_name, op_date, from_balance, to_balance) -> str`
  - `format_exchange_card(*, amount, from_currency, to_amount, to_currency, rate, op_date, from_wallet_name, to_wallet_name, from_balance, to_balance) -> str`
  - `transfer_card_keyboard(transaction_id) -> InlineKeyboardMarkup` — only `Изменить` (WebApp) and `Удалить` (callback `qe:del:`). **No `Кошелёк`.**

Exact layouts (spaces and separators matter):

Transfer:
```
↔️ **{amount}** · Перевод
{from} → {to} · {date}
{from}: {from_bal} · {to}: {to_bal}
```

Exchange:
```
🔄 **{amount_from} → {amount_to}** · Обмен
Курс {rate} · {date}
{from}: {from_bal} · {to}: {to_bal}
```

Where amounts use `format_amount` (no leading minus). Rate formatted with spaces like amounts (integer). Balance lines use `format_amount` with each wallet's currency.

- [ ] **Step 1: Write failing card tests** asserting exact strings for the §8.2 / §8.3 examples (with fixed dates/balances).

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/bot/quick_entry/texts.py backend/bot/quick_entry/cards.py backend/tests/test_quick_entry_transfer_cards.py
git commit -m "$(cat <<'EOF'
feat: add transfer and exchange quick-entry card layouts

EOF
)"
```

---

### Task 6: Wire handlers — create, refuse, counters

**Files:**
- Modify: `backend/bot/quick_entry/handlers.py`
- Create: `backend/tests/test_quick_entry_transfer_flow.py`

**Interfaces:**
- Consumes: Tasks 1–5 APIs, existing counters, `set_parser_override`
- Produces: text handler behaviour:
  1. Stop dropping transfer/exchange in `_filter_countable` — include them in countable ops (they count toward the 5-ops limit).
  2. After parse, for each transfer/exchange op with amount:
     - resolve from/to wallets
     - `rate = effective_rate(op, text)`
     - if `needs_exchange_refusal(...)`: spend unparsed (if allowed), send `MSG_EXCHANGE_RATE_REQUIRED`, **do not write**, continue
     - else create via `create_quick_entry_transfer`, reply with transfer or exchange card + `transfer_card_keyboard`
  3. Expense/income/ambiguous behaviour unchanged.
  4. Model call still spent once when model was called (same as Phase 1 rules).
  5. Mixed message: process clear expense ops and transfer ops independently; refusal for one op must not invent rates for another.
  6. Delete callback already uses `qe:del:` — works for transfer rows; ensure card re-format for transfer is not required on delete (message deleted / gone). If delete currently re-fetches expense card only, leave delete as soft-delete + confirm (read current code; keep behaviour).

- [ ] **Step 1: Write failing flow tests** (mirror `test_quick_entry_flow.py` harness):

1. Same-currency transfer stub → one transfer row; balances change; reply text matches transfer card shape; keyboard has no `Кошелёк`.
2. Exchange with `по 12800` → row with rate; balances change.
3. Cross-currency no rate (RU) → **zero** new transactions; balances unchanged; reply == `MSG_EXCHANGE_RATE_REQUIRED`; `daily_unparsed` +1.
4. Same sentence Uzbek stub → same refusal + balances untouched.
5. `поменял 100 долларов на сумы 12800` → refusal (marker missing) even if stub rate were set — use stub with rate set AND text without `по` to prove bot-side gate.
6. `такси 25 тысяч` still creates expense (regression).

- [ ] **Step 2: Run — FAIL** (transfers still filtered)

- [ ] **Step 3: Implement handler changes**

Remove/replace `_filter_countable` so transfer/exchange with `amount is not None` are processed. Keep skipping unknown types. Order: spend model call as today; then process transfers/exchanges and expenses.

For exchange card vs transfer card: if currencies differ and rate present → exchange card; if same currency → transfer card.

- [ ] **Step 4: Run flow tests + full suite — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/bot/quick_entry/handlers.py backend/tests/test_quick_entry_transfer_flow.py
git commit -m "$(cat <<'EOF'
feat: handle transfer and exchange in quick-entry text flow

EOF
)"
```

---

### Task 7: Delete path + full suite gate + phase checklist

**Files:**
- Modify: `backend/bot/quick_entry/handlers.py` only if delete/wallet callbacks break on transfer (no `Кошелёк` on transfer cards — wallet callback may remain for expense cards only)
- Modify/create tests as needed: `backend/tests/test_quick_entry_transfer_flow.py` or callbacks test
- Do not touch mini-app

**Interfaces:**
- Consumes: existing `qe:del:` handler
- Produces: soft-delete of a transfer created via quick entry succeeds; gone message for missing id; expense wallet button still present on expense cards only

- [ ] **Step 1: Write failing test** — create transfer via handler path / service, fire `qe:del:{id}`, assert soft-deleted and balances restored.

- [ ] **Step 2: Run — observe pass or fail; fix only if fail**

- [ ] **Step 3: Run full suite**

```bash
cd backend && ./venv/bin/pytest -q
```

Expected: all green. Record count.

- [ ] **Step 4: Self-check phase acceptance mapping**

| Acceptance | Covered by |
|------------|------------|
| §8.2 transfer card | `test_quick_entry_transfer_cards` + flow |
| §8.3 exchange with rate | cards + flow |
| §8.4 / §8.3 refusal RU | sanity + flow |
| Uzbek same refusal | stub + flow |
| No `по` → refusal | sanity + flow |
| Expense regression | flow |

- [ ] **Step 5: Commit** (only if code changed); otherwise note no-op

```bash
git add -A backend/tests backend/bot/quick_entry
git commit -m "$(cat <<'EOF'
test: cover transfer delete and phase-2 acceptance gates

EOF
)"
```

---

## Self-review (plan author)

1. **Spec coverage:** §8.2 create+card, §8.3 rate/refusal, §8.4 bot-side gate, counters, stub/Uzbek, expense regression, prompt immutable→mutable — each has a task. Out-of-scope items explicitly excluded.
2. **Placeholders:** none intentional; Task 4 says copy fixture from existing create tests.
3. **Types:** `rate: int | None` on parse; `Decimal | None` at DB boundary via `Decimal(rate)` when creating.
4. **Dead controls:** transfer keyboard omits `Кошелёк`.
5. **Phase 13:** prompt split is done here; caching not enabled.
