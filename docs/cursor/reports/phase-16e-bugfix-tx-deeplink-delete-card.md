# Report — Phase 16e: bot card deep-link, delete-card text, wallet-picker

Branch: `mvp2/phase-16-cascade-demo-protected-support` (continued; no new branch)  
Date: 2026-08-05  
Orchestrator: Cursor Grok 4.5  
Workers: `composer-2.5` only

---

## Tests

| Moment | Backend (`pytest -q`) | Frontend (`npx vitest run`) |
|--------|------------------------|-----------------------------|
| Baseline (before 16e changes) | **502 passed**, 1 warning | **39 files / 235 passed** |
| Final (after Tasks 1 + 3) | **502 passed**, 1 warning | **42 files / 244 passed** |

Delta: backend unchanged (existing wallet-picker / cards tests updated in place). Frontend **+9** tests (deep-link parse / route / gone page).

Disabled / stubbed / mocked: **none**.

---

## What shipped

### Task 1 — `«Изменить»` / `?tx=` deep-link into mini app — **done**

**Live / local verification before fix**

- Grep confirmed: nothing in `frontend/src` previously read a launch `tx` query param.
- Headless Chrome + CDP on Vite: `http://127.0.0.1:5173/?tx=<uuid>` did **not** crash. Home rendered; `tx` was inert. No console exception captured for the blank-white symptom on this local path. (App already uses `react-router-dom` inside `AppShell`; navigation is route-based, but cold launch never consumed `tx`.)

**Behaviour shipped**

- After auth `ready`, `useTxDeepLink` reads `?tx=` from `window.location.search`.
- Valid UUID → `fetchTransaction` → `navigate(editRouteForItem(...), { replace: true })`; `tx` cleared from the URL.
- Invalid `tx` → clear param, normal Home.
- HTTP 404 → `/transaction-gone` with verbatim `Запись больше не существует.` (`MSG_GONE` / `transaction.gone`) and existing i18n button `На главную` (`addTransaction.goHome`).
- Other fetch failures → clear `tx`, fall through to Home.
- No `tx` → unchanged boot.

### Task 2 — `«Удалить»` leaves stale card text — **done** (phase 16f follow-up)

Root cause confirmed in code: `handle_quick_entry_delete` only called `edit_reply_markup(reply_markup=None)` after soft-delete; it never touched message text (unlike wallet-set / type-choice paths that call `_format_transaction_card` + `edit_text`).

**PM decision (16f):** do **not** re-render copy — **delete the bot message entirely** (`callback.message.delete()`), so the card disappears from the chat.

**Fix (composer-2.5):** after soft-delete + commit + `_check_wallets_after_write`:

1. `await callback.answer()` (clears Telegram’s button loading spinner)
2. `await callback.message.delete()` — `TelegramBadRequest` swallowed so a race (message already gone) does not undo the soft-delete

No new user-facing RU strings.

### Task 3 — `«Кошелёк»` no visible reaction — **done**

**Investigation (neither of the two prompt hypotheses alone)**

1. One-wallet UX illusion — possible in screenshots (`Наличный сум` dominates) but **not** the failure mode observed live.
2. Silently swallowed exception — **yes, with a concrete Telegram API error**.

Live bot terminal (`python3 -m bot.main`):

```text
aiogram.exceptions.TelegramBadRequest: Telegram server says - Bad Request: BUTTON_DATA_INVALID
  ... in handle_quick_entry_wallet_list
  edit_reply_markup(reply_markup=wallet_picker_keyboard(...))
```

Cause: picker buttons used `qe:walset:{txn_uuid}:{wallet_uuid}` = **83 bytes** > Telegram’s **64-byte** `callback_data` limit. Markup edit failed → no visible keyboard change; callback never answered successfully from the user’s POV.

**Fix**

- New format: `qe:ws:` + urlsafe base64 (no padding) of `transaction_id.bytes + wallet_id.bytes` → **49 bytes**.
- Helpers: `wallet_set_callback_data`, `parse_wallet_set_callback` in `cards.py`.
- Router: list stays `qe:wal:`; set is `qe:ws:` (no longer needs `~startswith("qe:walset:")` exclusion).
- Tests assert picker `callback_data` length `<= 64`.

### Home/History sort order

Not a bug (PM-confirmed). `get_history` `order_by` untouched.

---

## New / extended tests

**Frontend**

- `frontend/src/utils/txDeepLink.test.ts`
- `frontend/src/utils/txDeepLinkRoute.test.ts`
- `frontend/src/pages/TransactionGonePage.test.tsx`

**Backend** (updated in place)

- `tests/test_quick_entry_cards.py` — compact `qe:ws:` format + `len <= 64`
- `tests/test_quick_entry_callbacks.py` — wallet-set callbacks use new encoding

---

## Files touched (16e only)

| Path | Change |
|------|--------|
| `frontend/src/utils/txDeepLink.ts` | **created** — parse / resolve / clear `tx` |
| `frontend/src/utils/txDeepLink.test.ts` | **created** |
| `frontend/src/utils/txDeepLinkRoute.test.ts` | **created** |
| `frontend/src/hooks/useTxDeepLink.ts` | **created** — boot fetch + navigate |
| `frontend/src/pages/TransactionGonePage.tsx` | **created** |
| `frontend/src/pages/TransactionGonePage.test.tsx` | **created** |
| `frontend/src/components/AppShell.tsx` | deep-link gate + `transaction-gone` route |
| `frontend/src/api/transactions.ts` | `TransactionsApiError.status` for 404 branch |
| `frontend/src/i18n/locales/ru.json` | `transaction.gone` = `Запись больше не существует.` |
| `frontend/src/i18n/locales/uz.json` | matching key (draft) |
| `backend/bot/quick_entry/cards.py` | compact wallet-set callback encode/decode |
| `backend/bot/quick_entry/handlers.py` | parse `qe:ws:`; router filter |
| `backend/tests/test_quick_entry_cards.py` | picker length + format |
| `backend/tests/test_quick_entry_callbacks.py` | walset → `qe:ws:` |

No `docs/PRD.md` edits for this phase. Screenshots under `docs/bugs_screens/` may be removed after live verify of Task 2. No commit in this phase (not requested).

---

## Phase 16f follow-up — Task 2 message delete

Date: 2026-08-05  
Workers: `composer-2.5` only

### Tests

| Moment | Backend (`pytest -q`) | Frontend (`npx vitest run`) |
|--------|------------------------|-----------------------------|
| Baseline (before 16f) | **502 passed**, 1 warning | **42 files / 244 passed** |
| Final (after 16f) | **502 passed**, 1 warning | **42 files / 244 passed** |

Delta: none (existing delete-callback / transfer-delete tests updated in place).

Disabled / stubbed / mocked: **none**.

### Files touched (16f)

| Path | Change |
|------|--------|
| `backend/bot/quick_entry/handlers.py` | `handle_quick_entry_delete`: answer then `message.delete()` |
| `backend/tests/test_quick_entry_callbacks.py` | assert `delete`; mock `delete=AsyncMock()` |
| `backend/tests/test_quick_entry_transfer_flow.py` | transfer delete asserts `message.delete()` |

### Open

- Operator must restart the running `python3 -m bot.main` to load Task 2 (+ earlier Task 3) handler changes in the live process.
