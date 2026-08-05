# Report — Phase 16b: bugfix batch Home / Analytics / Settings

Branch: `mvp2/phase-16-cascade-demo-protected-support`  
Range: `7c9f5ef` → `32eceed` (7 commits)  
Date: 2026-08-05  
Orchestrator: Cursor Grok 4.5  
Workers: `composer-2.5` only (all implementation + review tasks)

---

## Tests

| Moment | Backend (`pytest -q`) | Frontend (`npx vitest run`) |
|--------|------------------------|-----------------------------|
| Baseline claimed in prompt | 461 passed | 206 passed |
| Observed at start of batch | ~460 passed + intermittent shared-DB flakes | **206 passed** |
| After Task 2 | 460 + 1 unrelated fail | **208 passed** |
| After Task 5 | 460 + 1 unrelated fail | **211 passed** |
| After Task 8 | **464** + 1 unrelated fail | **222 passed** |
| **Final (this report)** | **464 passed, 1 failed**, 1 warning | **38 files / 222 passed** |

Final failure (unchanged through the batch, not introduced by Tasks 2–9 diffs):

`tests/test_wallets_categories.py::TestIncomeCategoriesApi::test_income_category_delete_returns_affected_count_and_hides_from_get`

Asserts that deleting an income category leaves `txn.is_deleted is False`, but the transaction is soft-deleted. Looks like a conflict with cascade/delete behaviour already on this branch (pre–16b or env), not with the wallet-balance / goals / seed / i18n / swipe / analytics layout commits. **Not fixed in this batch** — out of Tasks 1–9 scope.

Disabled / stubbed / mocked in this batch: **none**.

§11 (broader RU↔UZ UI string coverage) — **not implemented**, as ordered.

---

## Commits (this batch)

| SHA | Subject | Task |
|-----|---------|------|
| `a1d9aa7` | fix(analytics): keep currency toggle visible on all tabs | 2 |
| `f6884fb` | style(analytics): polish period filter controls to match chip styles | 3 |
| `7a8d3b1` | fix(settings): defer pointer capture until swipe drag threshold | 5 |
| `e2c9669` | feat(wallets): show per-wallet balance in settings list | 6 |
| `b1792e7` | fix(i18n): sync defaultEntities with budget_seed translation keys | 7 |
| `f6c040e` | Reject backdated goal deadlines on create and update. | 8 |
| `32eceed` | feat(seed): add proportional current-month demo operations | 9 |

Tasks 1 and 4: no commits (verify / correctly-hidden behaviour).

---

## Task-by-task

### Task 1 — month navigation (verify-only) — DONE, no code change

Month nav on Home and Analytics correctly refetches for the selected Tashkent month. Demo data lives in **July**; **August** (default at test time) is empty by design — that explains the PM screenshots, not missing expense seed.

Isolated API check (rolled-back seed): July summary UZS income **9 000 000** / expense **7 000 000**, USD **600** / **500**; history `total_count` **21**; category donut and July trend bar populated. Cross-currency SQL sums `9,000,600` / `7,000,500` from the architect note are the sum of both currencies; the UI correctly shows per-currency figures (no conversion).

Live PM account at verification time had **0** transactions (demo cleared via `DELETE /api/v1/demo-data`). Navigation itself still works.

Screenshots of live July UI were not captured in automation (no browser MCP); evidence is API + code-path review + uvicorn logs of successful July 200 responses.

### Task 2 — Analytics currency toggle on История — DONE (`a1d9aa7`)

Root cause confirmed: chip gated on `activeTab === 'charts'`. Fix: reuse Home `.home-header` + `.home-currency-chip`; toggle always rendered; `analytics-tabs` row below. Currency still drives charts only — not wired into История. Tests updated.

Review: **Approved**. Minor leftover: header vs tabs horizontal padding may differ slightly (`.home-header` vs `.analytics-toolbar` inset).

### Task 3 — Period filter cosmetic polish — DONE (`f6884fb`)

Month row reuses `home-month-bar`; segmented control widened so «Диапазон» is not truncated; hint text and behaviour unchanged.

Review: **Approved**. Judged by eye / style reuse (no design mock for this control).

### Task 4 — «Мои личные» missing — DONE, no code change

Not a regression. PRD §11: personal block is shown only when the viewer has at least one personal wallet in the **selected currency**. PM test account has none → block correctly hidden. Design does not mandate an empty-state for zero personal wallets. No inventing UI; no ask needed.

### Task 5 — Settings rows not tappable — DONE (`7a8d3b1`)

`SwipeableSettingsRow`: `setPointerCapture` only after **7px** horizontal move; taps below threshold keep normal click → `onOpen`. Delete button / swipe width / reveal unchanged. No action-sheet. Shared by wallets, income categories, expense categories/subcategories. Unit tests for threshold helper (+3 vitest).

Review: **Approved**. Live Telegram WebView tap not manually verified here — **please re-test on device** (wallet tap-to-edit, income row, expense parent → subcategories, subcategory).

### Task 6 — Wallet balances in Settings list — DONE (`e2c9669`)

`GET /wallets` items include `balance: int` via `wallet_balance()`. Subtitle e.g. `UZS · 840 000 сум` / `USD · $1 240`. `WalletFormSheet` unchanged. Currency-aggregated balance endpoints unchanged. N+1 per wallet on list — acceptable at family limits.

Review: **Approved**.

### Task 7 — defaultEntities i18n sync — DONE (`b1792e7`)

`ru.json` / `uz.json` `defaultEntities` synced to all **39** seed `translation_key`s; 21 missing keys added; 7 orphans removed; `utilities` → «Коммунальные услуги». Grep-diff seed ↔ locales: zero gaps. Broader UI UZ (§11) not touched.

Review: **Approved**.

### Task 8 — reject backdated goal deadlines — DONE functionally (`f6c040e`)

Backend create/update reject `deadline < tashkent_today()` (HTTP 400 `deadline_before_today`), with carve-out to **keep** an already-past deadline unchanged on edit (Acceptance 9). Frontend `goalFormDeadline` mirrors that. Passed-deadline label behaviour unchanged; Acceptance 9 tested via DB fixture + mocked today, not POST past through API.

**Open copy decision for PM:** backdate UX hint reuses existing `addTransaction.invalidDate` («Введите корректную дату») because PRD has no goals-specific past-date phrase and `goals.form.deadlineInvalid` is format-only. Brief said to ask rather than invent — confirm this reuse **or** supply the exact Russian string to use.

Review: Approved functionally; copy held for PM.

### Task 9 — partial current-month demo seed — DONE (`32eceed`)

Previous month still fully seeded. Current month gets proportional subset from the same `expense_specs` / `income_specs`, dated 1…today (UTC, consistent with existing seed helpers), never future. Still `is_demo=True`, same clear endpoint. Tests updated (no longer assert empty current month). Early-month days may seed few/zero current-month rows.

Review: **Approved**. Note: seed «today» is UTC (parity with old seed), while analytics «today» is Tashkent — edge case near midnight boundary only.

---

## Deferred (explicitly out of this prompt)

- §11 — full audit of UZ coverage for Home / Analytics / Goals / Settings UI chrome (beyond default entity names). Confirmed wanted before release; separate prompt later.
- Unrelated failing income-category-delete test (see Tests).
- Manual WebView confirmation of Task 5.
- Optional polish: Analytics header/tabs padding alignment (Task 2 minor).

---

## PM asks (need answers)

1. **Task 8 hint text:** keep «Введите корректную дату» (`addTransaction.invalidDate`) for a well-formed but backdated goal deadline, or give the exact Russian phrase for a new `goals.form.*` key?
2. **Task 5:** after pulling this branch, tap rows in Settings → Кошельки / Категории доходов / Категории расходов on a real Telegram client and confirm edit opens.
