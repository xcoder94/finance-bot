# Phase 7 — Personal wallets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Each member creates and manages personal wallets that only they can see; personal ops stay out of shared Home/analytics/History for others; Home shows a subordinate `Мои личные` block when the viewer has a personal wallet in the selected currency.

**Architecture:** Enforce personal-wallet visibility in the data layer (SQL filters / 404 on forbidden ids), never by frontend hiding alone. Extend wallet CRUD so members create personal wallets (`is_personal` + `owner_user_id`) and holders edit/delete their own; keep shared create/edit/delete owner-only. Add personal summary/balance queries parallel to the shared ones for Home. Frontend wires Settings create (with Тип) and Home `Мои личные` to match design one-to-one.

**Tech Stack:** Python/FastAPI/pytest; React/Vite/TypeScript/TelegramUI/Zustand/react-i18next; vitest. No new packages.

## Global Constraints

- Spec: `docs/tasks/phase-07-personal-wallets.md` + PRD §3, §4, §7.3, §11, §17.2, §17.6, §19.1.
- Design: Home `Мои личные` block + wallets settings personal section / wallet form Тип field — appearance one-to-one.
- Visibility: personal wallet and its ops unreachable through every backend endpoint for anyone except the holder — **including owner**. No support bypass.
- Personal ops never enter shared analytics, shared Home top figures, digest aggregates, or another member's History.
- `Мои личные`: shown iff ≥1 personal wallet in selected currency; zero ops still shows block; never empty/zeroed when no wallet in that currency.
- Both Home blocks have headings; personal visually subordinate (`bg2`, smaller type) per design.
- Limit 5 personal per person; create button stays visible/enabled; at limit show exact `LIMIT_PERSONAL_WALLETS`.
- Shared create: owner only. Personal create: every member for themselves. Shared limit stays 10.
- §7.3: parse wallet names = shared + writer's personal only — cover with a test (regression already exists; keep green / strengthen if needed).
- Delete: Phase 6 swipe / entity sheet + shared confirm sheet; no delete control in list row.
- Name rules §4 unchanged (30 chars, trim, ellipsis never wrap).
- Income limit string from Phase 6 stays unchanged.
- Per-wallet balance subtitles on Settings wallet rows stay deferred — do not add balance to wallet list API.
- Do **not** edit `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/*`, `docs/tasks/*`.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-7-personal-wallets` (already checked out).
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Commit after each task. TDD. Stop at end of Phase 7 — no Phase 8, Goals, members lifecycle, change log, notifications.
- User-facing Russian verbatim. Forbidden words: ошибка, сессия, сервер, токен, запрос.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/wallet_visibility.py` (new) | SQL predicates + helpers: wallet visible to user; require access; filter clauses for lists/history |
| `backend/app/services/wallets_categories.py` | Optional: `get_visible_active_wallet` wrapping visibility |
| `backend/app/api/v1/wallets.py` | List filter; create shared/personal; patch/delete by role |
| `backend/app/schemas/wallets_categories.py` | `WalletCreate.is_personal: bool = False` |
| `backend/app/api/v1/me.py` | Default wallet must be visible (reject others' personal) |
| `backend/app/services/history_analytics.py` | History visibility filter; `get_personal_summary` / `get_personal_wallet_balances` |
| `backend/app/api/v1/history.py` | Pass viewer into `get_history` |
| `backend/app/api/v1/analytics.py` | Personal summary + balances endpoints |
| `backend/app/schemas/history_analytics.py` | Personal response schemas if needed |
| `backend/app/services/transactions.py` | Wallet access on create/update; hide foreign personal on get/modify |
| `backend/app/services/entity_limits.py` | Already has `PERSONAL_WALLET_LIMIT` / `LIMIT_PERSONAL_WALLETS` — use them |
| `backend/tests/test_phase7_personal_wallets.py` (new) | Visibility, CRUD, limits, Home personal, history, parse regression |
| `frontend/src/api/wallets.ts` | `is_personal` on create payload |
| `frontend/src/api/home.ts` | Personal summary/balances fetch |
| `frontend/src/components/settings/WalletFormSheet.tsx` | Тип field; personal/shared limits |
| `frontend/src/pages/settings/WalletsSettingsPage.tsx` | Create for all members; holder edit/delete personal |
| `frontend/src/pages/HomePage.tsx` + CSS | `Мои личные` block |
| `frontend/src/i18n/locales/ru.json` | Personal Home strings; member create intro |
| Vitest | Limit string; Home personal visibility helper; form limit wiring |

---

### Task 1: Backend — visibility helpers + wallet list + default-wallet guard

**Files:**
- Create: `backend/app/services/wallet_visibility.py`
- Modify: `backend/app/api/v1/wallets.py` — list filter
- Modify: `backend/app/api/v1/me.py` — reject invisible default wallet
- Create: `backend/tests/test_phase7_personal_wallets.py` — list/me tests
- Modify if needed: `backend/tests/test_phase6_settings.py` — `test_wallet_list_includes_is_personal` must still pass with **own** personal wallet (not another member's)

**Interfaces:**
- Produces:
  - `def wallet_is_visible(wallet: Wallet, user: User) -> bool`
  - `def require_wallet_visible(wallet: Wallet | None, user: User) -> Wallet` — 404 if missing or not visible
  - `def visible_wallets_clause(user: User)` → SQLAlchemy boolean expression: `(is_personal.is_(False)) | ((is_personal.is_(True)) & (owner_user_id == user.id))`
  - `def personal_ops_hidden_clause(viewer: User, from_wallet, to_wallet)` → exclude txns touching another person's personal wallet
- Consumes: `Wallet.is_personal`, `Wallet.owner_user_id`, `User.id`

- [ ] **Step 1: Write failing tests** in `backend/tests/test_phase7_personal_wallets.py`:

```python
async def test_list_hides_other_members_personal_wallet(api_client):
    # owner A + member B in same budget
    # seed B's personal wallet; as A GET /wallets → B's wallet absent
    # as B GET /wallets → B's wallet present with is_personal True

async def test_patch_me_rejects_others_personal_as_default(api_client):
    # B personal wallet id; as A PATCH /me default_wallet_id → 404
```

Reuse fixtures from `tests.test_wallets_categories` (`api_client`, `auth_headers`, `create_user_with_budget`). Add a second user in the same `family_budget_id` with `role="member"`.

- [ ] **Step 2:** Run `cd backend && ./venv/bin/pytest -q tests/test_phase7_personal_wallets.py -k "list_hides or patch_me_rejects"` — FAIL.

- [ ] **Step 3: Implement** `wallet_visibility.py`; apply `visible_wallets_clause` in `list_wallets` `.where(...)`; in `patch_me` after `get_active_wallet`, call `require_wallet_visible`.

- [ ] **Step 4:** Same tests PASS; `./venv/bin/pytest -q` green (fix any Phase 6 list test that seeded another user's personal into the caller's list).

- [ ] **Step 5:** Commit `feat(wallets): enforce personal wallet list visibility`

---

### Task 2: Backend — personal wallet create / update / delete + limit 5

**Files:**
- Modify: `backend/app/schemas/wallets_categories.py` — add `is_personal: bool = False` to `WalletCreate`
- Modify: `backend/app/api/v1/wallets.py` — create/update/delete auth matrix
- Modify: `backend/tests/test_phase7_personal_wallets.py`

**Interfaces:**
- `POST /api/v1/wallets` body: `{ name, currency, is_personal?: bool }`
  - `is_personal=False` (default): **OwnerUserDep** (or CurrentUser + 403 if not owner); count shared; set `is_personal=False`, `owner_user_id=None`
  - `is_personal=True`: **CurrentUserDep** (any member); count this user's active personal; on ≥5 → 409 `LIMIT_PERSONAL_WALLETS`; set `is_personal=True`, `owner_user_id=user.id`
  - Member posting `is_personal=False` → 403
- `PATCH` / `DELETE`:
  - Shared wallet → owner only (403 for non-owner)
  - Personal wallet → holder only (`owner_user_id == user.id`); non-holder including owner → **404** (do not leak existence)
- Soft-delete unchanged via `soft_delete`.

- [ ] **Step 1: Failing tests:**

```python
async def test_member_creates_personal_wallet(api_client): ...
async def test_member_cannot_create_shared(api_client): ...  # 403
async def test_personal_6th_returns_exact_19_1(api_client):
    # 5 personal for user; 6th → 409 detail == LIMIT_PERSONAL_WALLETS
async def test_delete_personal_frees_slot(api_client): ...
async def test_holder_renames_personal(api_client): ...
async def test_owner_cannot_patch_members_personal(api_client): ...  # 404
async def test_owner_cannot_delete_members_personal(api_client): ...  # 404
async def test_member_cannot_patch_shared(api_client): ...  # 403
```

- [ ] **Step 2:** Run focused pytest — FAIL.

- [ ] **Step 3: Implement** create path branching; change PATCH/DELETE deps from blanket `OwnerUserDep` to `CurrentUserDep` + permission checks using visibility helpers. Keep shared owner-only.

Implementation sketch for create:

```python
@router.post("/wallets", status_code=201)
async def create_wallet(body: WalletCreate, user: CurrentUserDep, session: ...):
    if body.is_personal:
        count = await session.scalar(
            select(func.count()).select_from(Wallet).where(
                Wallet.family_budget_id == user.family_budget_id,
                Wallet.is_deleted.is_(False),
                Wallet.is_personal.is_(True),
                Wallet.owner_user_id == user.id,
            )
        )
        if count is not None and count >= PERSONAL_WALLET_LIMIT:
            raise HTTPException(status_code=409, detail=LIMIT_PERSONAL_WALLETS)
        wallet = Wallet(
            family_budget_id=user.family_budget_id,
            name=body.name,
            currency=body.currency,
            is_personal=True,
            owner_user_id=user.id,
        )
    else:
        if user.role != "owner":
            raise HTTPException(status_code=403)
        # existing shared limit + create with is_personal=False
```

- [ ] **Step 4:** Tests PASS; full pytest green. Update any old test that POSTed without auth assumptions.

- [ ] **Step 5:** Commit `feat(wallets): personal wallet CRUD and limit 5`

---

### Task 3: Backend — history + transaction access for personal ops

**Files:**
- Modify: `backend/app/services/history_analytics.py` — `get_history(..., viewer: User)`
- Modify: `backend/app/api/v1/history.py` — pass `user`
- Modify: `backend/app/services/transactions.py` — validate wallet visibility on create/update; gate get/update/delete
- Modify: `backend/app/api/v1/transactions.py` if get path needs extra check
- Modify: `backend/tests/test_phase7_personal_wallets.py`
- Possibly adjust: `backend/tests/test_phase5_analytics.py` `test_history_still_includes_personal_wallet_ops` — still true for **holder**

**Interfaces:**
- History filter (after joining `from_wallet` / `to_wallet`): include row iff it does **not** touch a personal wallet owned by someone else:

```python
# Pseudo — implement via or_/and_ on aliases
visible = and_(
    or_(from_wallet.is_personal.is_(False), from_wallet.owner_user_id == viewer.id),
    or_(
        to_wallet.id.is_(None),
        to_wallet.is_personal.is_(False),
        to_wallet.owner_user_id == viewer.id,
    ),
)
```

Apply to both count and items queries (same filters).

- Transaction create/update: after `get_active_wallet`, `require_wallet_visible`; for transfers both wallets.
- `GET/PATCH/DELETE /transactions/{id}`: load wallets for the txn; if not visible → 404. For modify on personal-wallet txn: only holder (owner role does **not** bypass). Shared txn modify rules stay as today (`require_modify_permission`).

- [ ] **Step 1: Failing tests:**

```python
async def test_history_hides_others_personal_expense(api_client):
    # B expense on B personal; as A history → amount absent; as B → present

async def test_get_transaction_others_personal_404(api_client): ...

async def test_member_cannot_post_expense_on_others_personal(api_client): ...  # 404

async def test_analytics_summary_excludes_personal(api_client):
    # regression: shared summary unchanged when personal expense exists
```

- [ ] **Step 2:** FAIL.

- [ ] **Step 3: Implement** filters and guards.

- [ ] **Step 4:** PASS + full pytest.

- [ ] **Step 5:** Commit `feat(wallets): hide foreign personal ops in history and API`

---

### Task 4: Backend — personal Home figures API

**Files:**
- Modify: `backend/app/services/history_analytics.py` — add `get_personal_summary`, `get_personal_wallet_balances`, `list_personal_wallet_currencies` (or fold currencies into balances response)
- Modify: `backend/app/schemas/history_analytics.py` — e.g. `PersonalHomeResponse` or reuse `SummaryResponse` / `WalletBalancesResponse` plus `currencies_with_wallets: list[str]`
- Modify: `backend/app/api/v1/analytics.py` — two endpoints (or one combined)
- Modify: `backend/tests/test_phase7_personal_wallets.py`

**Interfaces (preferred — minimal surface):**

```
GET /api/v1/analytics/personal-summary?date_from&date_to
→ PersonalSummaryResponse {
    currencies_with_wallets: list[str],  # active personal wallets of viewer, by currency
    by_currency: list[{ currency, income, expense, balance }]
  }
```

Where for each currency in `currencies_with_wallets`:
- `income` / `expense` = month-scoped sums on viewer's personal wallets only (transfers net into balance like shared summary; income/expense labels match Home shared card: income and expense only for the two figure columns; **balance** = all-time personal wallet balance for that currency, same ledger rules as `get_wallet_balances` but `is_personal.is_(True)` and `owner_user_id == viewer.id`).

Alternatively two endpoints mirroring shared:
- `GET /api/v1/analytics/personal-summary` → income/expense per currency (viewer personal only)
- `GET /api/v1/analytics/personal-wallet-balances` → balance per currency + `currencies_with_wallets`

Choose the two-endpoint mirror of existing Home clients for consistency.

**Visibility of block (backend contract):** `currencies_with_wallets` lists currencies where viewer has ≥1 non-deleted personal wallet — **independent of operations**. Frontend shows block iff selected currency ∈ that list.

- [ ] **Step 1: Failing tests:**

```python
async def test_personal_summary_includes_holder_expense(api_client): ...
async def test_personal_currencies_with_wallet_no_ops(api_client):
    # personal UZS wallet, no txns → currencies_with_wallets contains UZS; income/expense 0
async def test_personal_not_visible_to_owner(api_client):
    # B has personal; as A currencies_with_wallets empty / no B amounts
async def test_shared_summary_unaffected(api_client): ...
```

- [ ] **Step 2:** FAIL.

- [ ] **Step 3: Implement** services + routes. Do not include personal in existing shared endpoints.

- [ ] **Step 4:** PASS + full pytest.

- [ ] **Step 5:** Commit `feat(home): personal summary and balance endpoints`

---

### Task 5: Frontend — Settings personal create / edit / delete + limit UX

**Files:**
- Modify: `frontend/src/api/wallets.ts` — `WalletCreatePayload.is_personal?: boolean`
- Modify: `frontend/src/components/settings/WalletFormSheet.tsx` — Тип field; personal count; limit hints
- Modify: `frontend/src/pages/settings/WalletsSettingsPage.tsx` — create button for all; holder swipe/edit on personal; owner shared as now
- Modify: `frontend/src/i18n/locales/ru.json` — `createIntroMember`: `Вы можете создать только личный кошелёк.` (design verbatim); ensure `walletType` keys used
- Vitest: form limit shows `LIMIT_PERSONAL_WALLETS` when personal count ≥ 5

**Behaviour:**
- Header `Добавить кошелёк` visible for **owner and member** (design `hasAction: true`).
- Create form:
  - Owner: intro owner text; Тип picker Общий | Личный (default Общий or as design shows Общий).
  - Member: intro member text; Тип = Личный locked (no picker / single value).
- At limit: button stays enabled; sheet opens; name-field hint = exact shared or personal §19.1 string; Save disabled (same pattern as Phase 6 shared).
- Personal rows: `swipeDeleteEnabled` and `editable` for **holder** (always true for listed personal — list only shows own). Shared rows: owner only.
- `onSave` passes `is_personal` on create.
- Verify no fake create success placeholder exists; remove if found.
- Do **not** add balance to row subtitles.

- [ ] **Step 1:** Write/adjust vitest for limit hint + create payload includes `is_personal`.

- [ ] **Step 2:** FAIL / red as needed.

- [ ] **Step 3: Implement** UI.

- [ ] **Step 4:** `cd frontend && npx vitest run --reporter=dot` green.

- [ ] **Step 5:** Commit `feat(settings): personal wallet create edit delete`

---

### Task 6: Frontend — Home `Мои личные` block

**Files:**
- Modify: `frontend/src/api/home.ts` — fetch personal summary/balances
- Modify: `frontend/src/pages/HomePage.tsx` — render block after recent ops (design order: figures → actions → recent → **personal**)
- Modify: `frontend/src/index.css` — styles matching design (`background:var(--bg2)`, heading 600 13px, subtitle hint, stats 13.5px mono)
- Modify: `frontend/src/i18n/locales/ru.json`:
  - `home.personalTitle`: `Мои личные`
  - `home.personalSubtitle`: `{{name}} · вне общего бюджета` (name = user first_name / display)
- Vitest helper: `shouldShowPersonalBlock(currencies, selected) -> boolean`

**Behaviour:**
- Fetch personal endpoints alongside shared Home data.
- Show block iff selected currency is in `currencies_with_wallets`.
- Figures: income, expense, balance for that currency only; format like shared (no USD conversion).
- Shared top card keeps its heading (`Остаток · {monthShort}` via existing `balanceMonthLabel`).
- Personal heading `Мои личные` + subtitle; visually subordinate.
- Loading/error: follow existing Home block patterns (do not invent empty personal card when no wallet).

- [ ] **Step 1:** Vitest for visibility helper.

- [ ] **Step 2:** Implement API + UI + CSS.

- [ ] **Step 3:** Vitest green; manual structure check against design snippet.

- [ ] **Step 4:** Commit `feat(home): Мои личные personal figures block`

---

### Task 7: §7.3 parse regression + phase verification

**Files:**
- Prefer existing: `backend/tests/test_quick_entry_wallets.py`, `test_quick_entry_flow.py` (`TestWalletNameLeak`)
- Optionally add one explicit test in `test_phase7_personal_wallets.py` that calls `list_wallets_for_parse` with A and B personal wallets and asserts B's names absent from A's list (duplicate of Phase 1 OK for phase report clarity)

- [ ] **Step 1:** Ensure parse tests still pass; add thin regression test if missing coverage for multi-member names.

- [ ] **Step 2:** Run full backend + frontend suites:

```bash
cd backend && ./venv/bin/pytest -q
cd frontend && npx vitest run --reporter=dot
```

- [ ] **Step 3:** Commit only if new test file changes: `test(wallets): reinforce parse personal wallet name isolation`

- [ ] **Step 4:** Orchestrator produces FINAL REPORT only (no Phase 8).

---

## Self-review checklist

1. Spec coverage: visibility data-layer; personal CRUD; limit text; Home block + currency rule; headings; history/analytics exclusion; Settings create; §7.3 test; subtitle counts via filtered list — each has a task.
2. No placeholders / TBD in steps.
3. Types: `WalletCreate.is_personal`, `LIMIT_PERSONAL_WALLETS`, `currencies_with_wallets` consistent across tasks 2/4/5/6.
4. Deferred explicitly: Goals, notifications/digest runtime, wallet-row balances, Uzbek, Phase 8+.
