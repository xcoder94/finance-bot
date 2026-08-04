# Phase 6 — Settings: wallets, categories, default, language

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Rebuild Settings into a §17.6 TOC; manage shared wallets, income/expense categories (with soft-delete and §5 colour), default wallet, and language; show exact §19.1 limit strings; leave members/notifications as honest shells.

**Architecture:** Backend enforces name ≤30, count limits, colour assignment, and PATCH `/me` for default wallet + language. Frontend replaces the MVP1 single-scroll Settings page with nested routes under `/settings/*` matching design chips. Create stays visible; at limit the entity sheet opens with the §19.1 hint under the name field and Save disabled (design look + PRD “button stays enabled”). Personal wallet create is not offered (Phase 7). Members/notifications screens are read-only shells without invite/transfer/exit/switches.

**Tech Stack:** Python/FastAPI/Alembic/pytest; React/Vite/TypeScript/TelegramUI/Zustand/react-i18next; vitest. No new packages without asking.

## Global Constraints

- Spec: `docs/tasks/phase-06-settings-entities.md` + PRD §17.6 rows 1–4+7, §17.7 entity forms, §4, §15.1–§15.2/§15.4–§15.5, §5 colour, §19.1.
- Design: `docs/design/Chontak MVP2.dc.html` Settings TOC + entity screens one-to-one (placement/spacing/copy). Behaviour: PRD/spec win (create stays enabled; members subtitle `N из 4`; notifications subtitle `Выключены`).
- Limit strings character-for-character from §19.1 (never rephrase). Numbers 50 and 20 stay `DAILY_*` env config — never hard-code them. Product ceilings 10/5/8/8/30 are code constants OK.
- Soft-delete package §15.4: no restore; deleted absent from pickers/filters; visible in analytics/History; same-name = new entity + new colour.
- Colour bound to category (§5): free among active and not used by category deleted in last 12 months; else longest-deleted’s colour. Not list order.
- §15.5: no migration of old families’ category sets. New budgets still seed §15.1–§15.2 only.
- Rows 5–6: shells only — no invites/transfer/exit; no notification switches. Personal wallet create = Phase 7 (section may list none; never fake create success).
- User-facing Russian verbatim. Words never used: ошибка, сессия, сервер, токен, запрос. Uzbek UI out of scope except language row label `Oʻzbekcha`.
- Do **not** edit `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/*`, `docs/tasks/*`.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-6-settings-entities` (already checked out — do not create/switch/merge).
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Commit after each task. TDD. Report pytest + vitest before/after in task reports.
- Stop at end of Phase 6. Do not start Phase 7.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/config.py` | Optional entity-limit constants (not 50/20) |
| `backend/app/services/entity_limits.py` (new) | Count + name validation; §19.1 message builders |
| `backend/app/services/category_colors.py` (new) | §5 colour assignment |
| `backend/app/services/wallets_categories.py` | Soft-delete helpers (existing) |
| `backend/app/api/v1/wallets.py` | Shared limit; expose `is_personal`; name trim/len |
| `backend/app/api/v1/categories.py` | Parent/sub/income limits; colour on create; name trim/len |
| `backend/app/api/v1/me.py` | `PATCH /me` default_wallet_id + language |
| `backend/app/schemas/wallets_categories.py` | `is_personal`, `color_index`; name max 30 |
| `backend/app/schemas/auth.py` | `MeUpdate` |
| `backend/app/models/expense_category.py` / `income_category.py` | `color_index` column |
| `backend/alembic/versions/m3b4c5d6e7f8_category_color_index.py` (new) | Add `color_index` |
| `backend/bot/onboarding.py` | Assign colours when seeding new budgets |
| `backend/tests/test_phase6_settings.py` (new) | Limits, soft-delete picker, colour, me patch, no migration |
| `frontend/src/pages/SettingsPage.tsx` | TOC only |
| `frontend/src/pages/settings/*` (new) | Entity screens + shells |
| `frontend/src/components/settings/*` | Rebuild lists/sheets/swipe/confirm; drop inline row delete |
| `frontend/src/api/me.ts` / `wallets.ts` / `categories.ts` | PATCH helpers; `is_personal`; `color_index` |
| `frontend/src/utils/chartColors.ts` + analytics consumers | Prefer stored `color_index` |
| `frontend/src/i18n/locales/ru.json` | TOC/entity/limit strings |
| `frontend/src/components/AppShell.tsx` | Nested settings routes |
| Vitest | Limit strings char-for-char; subtitles; name truncate; soft-delete filter helper |

---

### Task 1: Backend — name validation + count limits + §19.1 detail

**Files:**
- Create: `backend/app/services/entity_limits.py`
- Create: `backend/app/services/limit_messages.py` (or fold into entity_limits)
- Modify: `backend/app/schemas/wallets_categories.py` — trim + `max_length=30` on name fields via field validators
- Modify: `backend/app/api/v1/wallets.py` — before create, count active shared (`is_personal.is_(False)`); on limit raise `HTTPException(409, detail=<exact §19.1 string>)`
- Modify: `backend/app/api/v1/categories.py` — income active count ≤8; expense parents (`parent_id.is_(None)`) ≤8; subcats per parent ≤8; 409 with exact strings
- Create: `backend/tests/test_phase6_settings.py` — focused tests

**Interfaces:**
- Produces:
  - `SHARED_WALLET_LIMIT = 10`, `PERSONAL_WALLET_LIMIT = 5` (enforce personal only if create path exists — do not add personal create), `PARENT_CATEGORY_LIMIT = 8`, `SUBCATEGORY_LIMIT = 8`, `ENTITY_NAME_MAX = 30`
  - `normalize_entity_name(name: str) -> str` — strip; raise/return validation for empty or >30
  - Message constants exact:
    - `LIMIT_SHARED_WALLETS = "Больше 10 общих кошельков создать нельзя. Удалите ненужный — место освободится."`
    - `LIMIT_PERSONAL_WALLETS = "Больше 5 личных кошельков создать нельзя. Удалите ненужный — место освободится."` (constant present for tests; unused until Phase 7 create)
    - `LIMIT_EXPENSE_PARENTS = "Больше 8 категорий расходов создать нельзя. Удалите ненужную — место освободится."`
    - `LIMIT_INCOME_CATEGORIES = "Больше 8 категорий доходов создать нельзя. Удалите ненужную — место освободится."` (parallel; §19.1 omits income — orchestrator decision for this phase)
    - `limit_subcategories(parent_name: str) -> str` → `В категории «{parent_name}» уже 8 подкатегорий — это предел. Удалите ненужную, чтобы добавить новую.`
- Consumes: existing create endpoints; soft_delete frees slots (deleted not counted).

- [ ] **Step 1: Write failing tests** in `backend/tests/test_phase6_settings.py`:

```python
async def test_shared_wallet_11th_returns_exact_19_1(api_client):
    # seed 10 shared wallets; POST 11th → 409; detail == LIMIT_SHARED_WALLETS character-for-character

async def test_delete_shared_frees_slot(api_client):
    # 10 shared; DELETE one; POST succeeds 201

async def test_wallet_name_31_rejected(api_client):
    # 422

async def test_wallet_name_only_spaces_rejected(api_client):
    # 422

async def test_expense_parent_9th_exact_message(api_client):
    # 8 parents; 9th → 409 LIMIT_EXPENSE_PARENTS

async def test_subcategory_9th_under_food_exact_message(api_client):
    # parent Еда with 8 subs; 9th → 409 with «Еда» in template

async def test_income_9th_exact_message(api_client):
    # 8 income; 9th → 409 LIMIT_INCOME_CATEGORIES

async def test_deleted_category_frees_parent_slot(api_client):
    # 8 parents; delete one; create succeeds
```

- [ ] **Step 2:** Run `cd backend && ./venv/bin/pytest -q tests/test_phase6_settings.py -k "limit or name"` — FAIL.

- [ ] **Step 3:** Implement constants, validators, create-path checks. Do not hard-code 50/20.

- [ ] **Step 4:** Same pytest PASS; full `./venv/bin/pytest -q` green.

- [ ] **Step 5:** Commit `feat(settings): enforce entity name and count limits`

---

### Task 2: Backend — category `color_index` + §5 assignment

**Files:**
- Create: `backend/alembic/versions/m3b4c5d6e7f8_category_color_index.py` — `down_revision = "l2a3b4c5d6e7"`; add nullable-then-backfill or `server_default` Integer `color_index` on `expense_categories` and `income_categories` (1–8); backfill existing rows round-robin by `created_at` within family (stable, one-time); NOT NULL after.
- Create: `backend/app/services/category_colors.py`
- Modify: models + schemas responses to include `color_index: int`
- Modify: `categories.py` create paths to call assigner
- Modify: `backend/bot/onboarding.py` — when seeding, assign distinct colours to first 8 parents / income cats (subs may share parent colour or get own — use assigner per created category)
- Modify: analytics frontend later (Task 7); backend analytics may pass through if category payloads gain field — list endpoints return `color_index`
- Tests in `test_phase6_settings.py`

**Interfaces:**
- Produces: `async def assign_category_color(session, family_budget_id, *, kind: Literal["expense","income"]) -> int`
  - Collect colour indices of **active** categories of that kind (expense: parents only for chart parents; also assign for subcats as their own index for consistency — use all active expense rows’ color_index for “in use by active”)
  - Collect colour indices of categories of that kind with `deleted_at >= now - 365 days`
  - Free = `{1..8} - active - recently_deleted`
  - If free non-empty: smallest free index
  - Else: colour of the longest-deleted category (`deleted_at` ascending / oldest deleted first)
- Same-name after delete gets a **new** colour via this rule (not copying deleted row).

- [ ] **Step 1: Failing tests** for colour:
  - New category gets colour not used by active siblings
  - Fixture: all 8 colours used by active → delete one → new gets freed colour
  - Fixture: 8 active using all colours; 8 deleted within 12 months holding… (arrange so no free) → new reuses longest-deleted’s colour
  - Soft-deleted category still returned in analytics payloads with its stored colour (existing analytics tests remain green)

- [ ] **Step 2:** pytest FAIL.

- [ ] **Step 3:** Migration + assigner + wire creates + seed.

- [ ] **Step 4:** pytest PASS; full suite green.

- [ ] **Step 5:** Commit `feat(settings): persist category colour_index per §5`

---

### Task 3: Backend — PATCH `/me` (default wallet + language) + wallet `is_personal` on list

**Files:**
- Modify: `backend/app/schemas/auth.py` — `MeUpdate` with optional `default_wallet_id: UUID | None`, `language: Literal["ru","uz"]`
- Modify: `backend/app/api/v1/me.py` — `PATCH /me` with `CurrentUserDep` (or AppPass + DB user); validate wallet belongs to user’s family, not deleted; set fields; return `MeResponse`
- Modify: `WalletResponse` + list/create responses to include `is_personal: bool`
- Tests: patch default wallet; quick-entry still uses `user.default_wallet_id` (existing bot test — run regression); patch language persists on GET `/me`
- Test: pre-MVP2 budget fixture — after migrations, category **names/count** unchanged (§15.5) — assert seed set not altered by colour migration alone

- [ ] **Step 1: Failing tests** for PATCH `/me` and `is_personal` on GET `/wallets`.

- [ ] **Step 2:** Implement.

- [ ] **Step 3:** Run `tests/test_phase6_settings.py` + `tests/test_quick_entry_flow.py` (or focused default-wallet test) + full pytest.

- [ ] **Step 4:** Commit `feat(settings): PATCH /me default wallet and language`

---

### Task 4: Frontend — Settings TOC + routes + i18n

**Files:**
- Rewrite: `frontend/src/pages/SettingsPage.tsx` — design TOC: profile badge card + 7 rows with icons/subtitles/chevrons; footer hint `Каждая сущность настраивается на своём экране. Удаление живёт там же — не в строке списка.`
- Create stubs: `frontend/src/pages/settings/WalletsSettingsPage.tsx`, `DefaultWalletSettingsPage.tsx`, `IncomeCategoriesSettingsPage.tsx`, `ExpenseCategoriesSettingsPage.tsx`, `ExpenseSubcategoriesSettingsPage.tsx`, `MembersSettingsShellPage.tsx`, `NotificationsSettingsShellPage.tsx`, `LanguageSettingsPage.tsx`
- Modify: `frontend/src/components/AppShell.tsx` — nested routes:
  - `/settings` TOC
  - `/settings/wallets`, `/settings/default-wallet`, `/settings/income-categories`, `/settings/expense-categories`, `/settings/expense-categories/:parentId`, `/settings/members`, `/settings/notifications`, `/settings/language`
- Create: `frontend/src/utils/settingsSubtitles.ts` + vitest
- Update: `ru.json` keys for row titles (verbatim §17.6) and subtitle patterns

**Subtitle rules:**
1. Кошельки: `{n} общих · {m} личных` (shared = `!is_personal`, personal = `is_personal`; personal may be 0)
2. Кошелёк по умолчанию: display name of selected wallet (or `—` if none)
3. Категории доходов: `{n} категорий` (active income count)
4. Категории расходов: `{n} родительских · {m} подкатегории` (pluralise подкатегори*/подкатегорий per Russian rules already in project if any; else match design wording)
5. Участники: `{n} из 4` (PRD/spec; not design’s «человека»)
6. Уведомления: `Выключены`
7. Язык: `Русский` or `Oʻzbekcha`

- [ ] **Step 1:** Vitest for subtitle helpers.

- [ ] **Step 2:** Implement TOC + routes (stub pages with title + back `‹ Настройки`).

- [ ] **Step 3:** `npx vitest run` relevant + smoke.

- [ ] **Step 4:** Commit `feat(settings): TOC and nested routes`

---

### Task 5: Frontend — wallets screen + entity sheet + confirm delete

**Files:**
- Implement `WalletsSettingsPage.tsx` per design: groups `Общие · …` / `Личные · видны только вам`; rows chevron to edit sheet; swipe reveals `Удалить` → shared confirm sheet
- Create: `frontend/src/components/settings/EntityDeleteConfirmSheet.tsx` — title/body per design confirm chip (entity confirm, not op confirm)
- Create: `frontend/src/components/settings/WalletFormSheet.tsx` — name ≤30 with `N / 30`; currency UZS/USD; **no personal type** this phase; owner-only open from `Добавить кошелёк`
- At shared count ≥10: create button still shown; opening sheet shows name field error hint = exact `LIMIT_SHARED_WALLETS`; Save disabled
- Member: no create button (cannot create shared; personal deferred)
- Personal section: list personal wallets if any; **no create**; note from design OK
- API: wire PATCH name, DELETE; map `is_personal`
- Truncate long names with ellipsis CSS (`white-space: nowrap; overflow: hidden; text-overflow: ellipsis`) — never wrap
- Remove inline `Удалить` from old `WalletsSection` / stop using it on TOC

**Design confirm (settings entity):** read confirm chip in design file — use those Russian strings character-for-character for wallet/category delete.

- [ ] **Step 1:** Vitest for limit string constant export matching §19.1 exactly.

- [ ] **Step 2:** Implement UI + API client updates.

- [ ] **Step 3:** vitest + ensure no row-level delete buttons in list markup tests if present.

- [ ] **Step 4:** Commit `feat(settings): wallets screen with limits and swipe delete`

---

### Task 6: Frontend — income / expense / subcategory screens

**Files:**
- `IncomeCategoriesSettingsPage.tsx` — flat list; add sheet; swipe/delete on entity; limit 8 → §19.1 income string under field
- `ExpenseCategoriesSettingsPage.tsx` — parents list; tap → subcats route; add parent; limit 8 → expense parents string
- `ExpenseSubcategoriesSettingsPage.tsx` — list + add + swipe delete; danger `Удалить категорию` for parent; limit 8 → dynamic parent name in template
- Reuse `EntityDeleteConfirmSheet`; no restore control anywhere
- `ENTITY_NAME_MAX_LENGTH = 30` in `entityNameValidation.ts`
- Retire/stop mounting old `EditableEntityList` inline-delete behaviour for these screens

- [ ] **Step 1:** Tests for name validation 30 + limit string helpers with parent interpolation.

- [ ] **Step 2:** Implement screens.

- [ ] **Step 3:** vitest pass.

- [ ] **Step 4:** Commit `feat(settings): category screens with soft-delete UX`

---

### Task 7: Frontend — default wallet, language, colour consumption, soft-delete picker tests

**Files:**
- `DefaultWalletSettingsPage.tsx` — radio list of all user’s wallets (shared + personal); tap → PATCH `/me`; instant, no confirm
- `LanguageSettingsPage.tsx` — radio `Русский` / `Oʻzbekcha` (sub `Lotin` on uz per design); PATCH language + `i18n.changeLanguage`; Uzbek strings for rest of product remain out of scope
- Update analytics colour maps to prefer `color_index` from category API when building charts (fallback only if missing)
- Soft-delete exclusion: add/extend vitest or backend test that operation category picker data source / GET categories omit deleted; History/analytics filter helpers omit deleted (backend list already filters — add explicit phase6 test if missing)
- Carry-over: soft-deleted category check deferred from Phase 5 — cover by test now that delete UI exists (API soft-delete + list exclusion + form uses list)

- [ ] **Step 1:** Failing tests (default wallet patch client; colour map uses stored index; deleted category not in picker list fixture).

- [ ] **Step 2:** Implement.

- [ ] **Step 3:** Full vitest + pytest.

- [ ] **Step 4:** Commit `feat(settings): default wallet, language, bound colours`

---

### Task 8: Frontend — members + notifications shells + design CSS polish

**Files:**
- `MembersSettingsShellPage.tsx`: title `Участники`; back; read-only list from `GET /members`; group title `{n} из 4 · …`; **do not render** invite link button, regenerate, transfer, exit, or member delete
- `NotificationsSettingsShellPage.tsx`: title `Уведомления`; show two **static** rows `Напоминание вечером` / `Итоги недели` with design subtitles; **no toggle controls** (Phase 11); TOC subtitle stays `Выключены`
- CSS in `frontend/src/index.css` (or settings CSS module) to match design spacing/type for TOC and entity lists
- Remove obsolete MVP1 settings sections from tree if unused
- Smoke: owner vs member — non-owned create actions hidden

- [ ] **Step 1:** Implement shells + CSS.

- [ ] **Step 2:** vitest for “members shell has no invite button”; “notifications shell has no checkbox/switch”.

- [ ] **Step 3:** Full `cd backend && ./venv/bin/pytest -q` and `cd frontend && npx vitest run --reporter=dot`.

- [ ] **Step 4:** Commit `feat(settings): members and notifications shells`

---

## Self-review checklist

1. Acceptance 1–10 mapped to tasks 4–8 (UI) + 1–3 (API) + soft-delete/colour tests.
2. No placeholder TBD steps.
3. Income limit string noted as orchestrator parallel of §19.1 (flag in final QUESTIONS).
4. Personal create not implemented; 50/20 untouched.
5. No migration of old category sets — colour column backfill only.
