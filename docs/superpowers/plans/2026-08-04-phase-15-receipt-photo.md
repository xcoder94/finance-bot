# Phase 15 — Receipt photo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute. `composer-2.5-fast` is forbidden.

**Goal:** Accept a Telegram photo of a receipt, parse total/merchant/category via the same Google Gemini parser path Task A established for binary content, and reply with one ordinary expense card — behind an isolation flag so text/voice keep working when photo is disabled.

**Architecture:** Reuse `ParseRequest` binary fields by adding optional `image_base64` / `image_mime_type` (same pattern as audio). Extend `ParseResponse` with optional `receipt_status`. New isolated module `bot/quick_entry/receipt_photo.py` owns the photo handler and router; `bot/main.py` includes it only when `RECEIPT_PHOTO_ENABLED` is truthy. Handler reuses wallet/category/counter/card helpers from the existing quick-entry path without duplicating create/card logic. Album = N independent photo messages → N model calls (Telegram already delivers separately).

**Tech Stack:** Python, httpx, Aiogram 3, pytest. No new packages. Backend only — frontend untouched (205 / 37).

## Global Constraints

- Spec: `docs/tasks/phase-15-receipt-photo.md` + PRD §10 (incl. 10.1, 10.2) + §23 receipt row only.
- One receipt = one expense operation for the **total** amount. No line items.
- Category from merchant + visible contents; comment = merchant name; wallet = default unless caption names a wallet.
- Date = receipt date if legible and within 31 days, else today (`apply_date_hint` already enforces lookback).
- Caption priority: e.g. `с наличных` → cash wallet wins (bot-side hint override after parse).
- Album: each photo = own model call + own card (opposite of voice’s single-call-per-message).
- Typing indicator only; no interim text.
- Timeout **20 seconds** per attempt; then existing §7.12 retry rules in HttpParser (`_MAX_ATTEMPTS`, retry on 429/5xx) — raise timeout for image-bearing requests only.
- Counters: +1 `daily_model_calls` per photo; unreadable → +1 `daily_unparsed`. No new counter kind.
- Failure text exact §10.1:
  ```
  Не разобрал чек. Сфотографируйте его целиком при хорошем свете или запишите
  сумму текстом.
  ```
- Isolation mandatory: env `RECEIPT_PHOTO_ENABLED` (truthy = `1`/`true`/`yes` case-insensitive) + separate handler module. Flag off → router not included; text/voice tests unchanged.
- Provider/model: `PARSER_*` only; Google for images (same gate style as voice). No new model env key.
- Do not change text/voice behaviour when flag off or on (except photo messages handled when on).
- Customer 20-receipt gate: always «pending customer» — never mark done. Do not claim phase «shipped».
- Branch: `mvp2/phase-14b-and-15`. Git allowed/forbidden same as Task A. Never touch `docs/context/**`.
- Worker: `composer-2.5` only.
- Baseline: frontend 205/37; backend last known green 403 when PG up. Counts must not shrink.

## Design decisions (locked)

### Binary image contract (reuse Task A pattern)

```python
@dataclass(frozen=True)
class ParseRequest:
    text: str  # caption or ""
    ...
    audio_base64: str | None = None
    audio_mime_type: str | None = None
    image_base64: str | None = None
    image_mime_type: str | None = None  # e.g. "image/jpeg"
```

`_post_google` parts: text JSON first; then audio inlineData if present; then image inlineData if present. Image-only requests (photo handler) set `image_*` and `text=caption`.

### Receipt status signal

```text
receipt_status: "ok" | "unreadable" | null
```

- Text/audio requests: null/absent (ignored).
- Image requests: model MUST set it.
  - `"unreadable"` → §10.1 + `spend_unparsed`; no record.
  - `"ok"` + no countable expense → treat as unreadable (§10.1) — crumpled total etc.
  - `"ok"` + one expense op → create card (if model returns >1 ops, take **first expense with amount only** — one receipt = one op; ignore extras rather than inventing multi-line behaviour).
  - Missing `receipt_status` on image request → `ParserMalformed` → `MSG_MODEL_FAIL`, no unparsed.

Also extend `IMMUTABLE_PARSER_INSTRUCTIONS` with receipt rules: total only, merchant in comment, category from merchant/contents, `date_hint` from receipt date when legible, `receipt_status`.

### Caption wallet override

After a successful parse with `receipt_status=ok`, if `message.caption` is non-empty, set `wallet_hint` used for `resolve_wallet` to the caption string (or merge: prefer caption over `op.wallet_hint`). Exact rule: `effective_hint = caption.strip() if caption else op.wallet_hint`.

### Timeout

When `request.image_base64` is set, use `httpx.Timeout(20.0)` for that parse call (HttpParser may accept optional timeout or create client with 20s for image requests). Text/audio stay at 10s.

### Isolation mechanism (exact)

1. `RECEIPT_PHOTO_ENABLED = os.environ.get("RECEIPT_PHOTO_ENABLED")` in `app/config.py`; helper `receipt_photo_enabled() -> bool` true iff value lowercased in `{"1","true","yes","on"}`.
2. New file `backend/bot/quick_entry/receipt_photo.py` with its own `router = Router()` and `handle_receipt_photo`.
3. `bot/main.py`:
   ```python
   if receipt_photo_enabled():
       from bot.quick_entry.receipt_photo import router as receipt_photo_router
       dp.include_router(receipt_photo_router)
   ```
4. Tests for photo set the flag via monkeypatch; a dedicated test asserts flag off → `receipt_photo` router not required by text/voice imports.

### Reuse without duplication

Photo handler:
1. typing
2. download largest photo size
3. provider gate (google + key) → else `MSG_MODEL_FAIL`
4. counters / user / default wallet (same as voice)
5. `ParseRequest(text=caption or "", image_base64=..., image_mime_type="image/jpeg", ...)`
6. parse (20s)
7. branch on `receipt_status`
8. On ok: build one expense via existing `create_quick_entry_expense` + `format_card` + `card_keyboard` (same as clear expense loop) — either call a thin shared helper extracted from handlers, or duplicate the minimal expense-card loop once carefully. Prefer exporting a small `create_and_reply_expense_card(...)` from `handlers.py` **only if** extraction is small; otherwise inline the same calls in `receipt_photo.py` importing services directly (allowed — do not import voice/text handlers in a way that creates cycles). **Chosen approach:** implement card creation inline in `receipt_photo.py` using existing services (`resolve_wallet`, `create_quick_entry_expense`, `format_card`, counters) — do not force a large refactor of `handlers.py`.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/config.py` | `RECEIPT_PHOTO_ENABLED` + `receipt_photo_enabled()` |
| `backend/app/parsing/types.py` | `image_base64`, `image_mime_type`; `receipt_status` on response |
| `backend/app/parsing/prompt.py` | Receipt rules in immutable instructions |
| `backend/app/parsing/http_adapter.py` | Image part; parse `receipt_status`; 20s timeout for images; google-only gate for images |
| `backend/bot/quick_entry/texts.py` | `MSG_RECEIPT_UNREADABLE` exact §10.1 |
| `backend/bot/quick_entry/receipt_photo.py` | Isolated photo handler + router |
| `backend/bot/main.py` | Conditional include |
| `backend/tests/test_phase15_receipt_photo.py` | All phase-15 stubbed tests |
| Frontend | **Do not touch** |

---

### Task 1: Types + prompt + config flag + failure text

**Files:**
- Modify: `types.py`, `prompt.py`, `config.py`, `texts.py`
- Create: `backend/tests/test_phase15_receipt_photo.py` (unit section)

**Interfaces:**
- `ParseRequest.image_base64`, `image_mime_type`
- `ParseResponse.receipt_status: Literal["ok","unreadable"] | None = None`
- `receipt_photo_enabled() -> bool`
- `MSG_RECEIPT_UNREADABLE` exact two-line §10.1 string
- Instructions mention `receipt_status`, receipt total-only rules

- [ ] **Step 1: Failing tests** for new fields, flag helper, MSG constant, instructions contain `receipt_status`

- [ ] **Step 2: Implement**

- [ ] **Step 3: PASS focused**

- [ ] **Step 4: Commit** `feat: add receipt photo parse fields and feature flag`

---

### Task 2: HttpParser image part + receipt_status + 20s timeout

**Files:**
- Modify: `http_adapter.py`
- Modify: `test_phase15_receipt_photo.py`

**Interfaces:**
- Gate: image present + provider ≠ google → `ParserUnavailable`
- Append `inlineData` image part (camelCase)
- Parse `receipt_status` (invalid → `ParserMalformed`)
- Image requests use 20.0s timeout

- [ ] **Step 1: Failing MockTransport tests** (image part present; non-google rejects; receipt_status parsed)

- [ ] **Step 2: Implement**

- [ ] **Step 3: PASS + existing parser tests PASS**

- [ ] **Step 4: Commit** `feat(parsing): Gemini inline image and receipt_status`

---

### Task 3: Isolated receipt_photo handler + main wiring

**Files:**
- Create: `backend/bot/quick_entry/receipt_photo.py`
- Modify: `backend/bot/main.py`
- Modify: `test_phase15_receipt_photo.py` (acceptance)

**Handler behaviour:**
1. `@router.message(F.photo)`
2. typing immediately
3. download `message.photo[-1]`
4. google/key gate → `MSG_MODEL_FAIL`
5. budget counters; spend model call on successful parse path (always when model answered with ok/unreadable — same as text: spend after successful parse before branching; on ParserUnavailable do not spend unparsed)
6. `receipt_status == unreadable` or ok-with-no-expense → `MSG_RECEIPT_UNREADABLE` + spend_unparsed
7. else create one expense; caption overrides wallet hint; date via `apply_date_hint(response.date_hint, today)`
8. Album test: call handler 3 times with FixedParser → 3 cards, `daily_model_calls == 3`

**Tests (stubbed):**
1. Receipt photo → card: amount, category, default wallet, merchant comment
2. Caption `с наличных` → cash wallet
3. Non-receipt (`receipt_status=unreadable`) → exact §10.1; no txn; unparsed +1
4. `date_hint` two months ago → today
5. Album of 3 → 3 model calls / 3 cards
6. Flag off: `receipt_photo_enabled()` false; importing/running text tests unaffected — assert `bot.main` does not include receipt router when flag false (unit test of wiring helper)

- [ ] **Step 1: Write failing acceptance tests**

- [ ] **Step 2: Implement handler + conditional main include**

- [ ] **Step 3: PASS; confirm `test_quick_entry_flow.py` still collects/passes non-DB or with DB**

- [ ] **Step 4: Commit** `feat(bot): isolated receipt photo quick-entry handler`

---

### Task 4: Flag-off regression + smoke script + suite gate

**Files:**
- Create: `backend/scripts/smoke_receipt_image.py` (optional; mirrors voice smoke)
- Create: `docs/superpowers/plans/phase15-task4-report.md`
- Tests: assert text/voice modules import without receipt_photo; flag-off wiring

- [ ] **Step 1: Test** — with `RECEIPT_PHOTO_ENABLED` unset/false, `from bot.quick_entry import handlers` and voice tests still import; `receipt_photo_enabled()` is False

- [ ] **Step 2: If possible, download 1–2 public receipt images and run smoke against live Gemini; else document blocker (same .env cursorignore)**

- [ ] **Step 3: Full pytest + vitest; commit report**

- [ ] **Step 4: Commit** `test: phase 15 isolation and suite gate`

---

## Self-review

1. Spec §10 decisions 1–12 mapped. Isolation exact. Binary reuse from Task A. Album = N calls. Customer gate pending.
2. No placeholders.
3. `receipt_status` / `image_*` names consistent.
4. Text/voice untouched when flag off.
