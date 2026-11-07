# Task 18 — Default entity translations (categories & wallets)

Depends on: Task 14 (`14-frontend-settings.md` — done), Task 03 (`03-bot-onboarding.md` — seed data source)
PRD reference: §5, §9

## Goal

Default-seeded wallets, income categories, and expense categories
(created automatically during onboarding) should display translated
per the user's selected language (RU/UZ). User-created entities keep
displaying their literal `name`, untranslated, in any language.

This does NOT change seed content, structure, or count — only adds a
translation layer on top of the existing default list.

## Backend changes

### 1. Migration

Add `translation_key` (string, nullable, no default) to:
- `wallets`
- `income_categories`
- `expense_categories`

Not unique, not indexed — low cardinality, no lookup by this column
planned.

### 2. Seed data (`bot/onboarding.py`)

Set `translation_key` on every default row created during Owner
onboarding. User-created rows (via `POST /wallets`,
`POST /categories/income`, `POST /categories/expense`) leave
`translation_key = NULL` — no change needed there, it's simply not
passed.

Proposed keys (confirm before Cursor implements):

**Wallets:**
| name (RU, unchanged) | translation_key |
|---|---|
| Карта сум | card_uzs |
| Наличный сум | cash_uzs |
| Карта USD | card_usd |
| Наличный USD | cash_usd |

**Income categories:**
| name | translation_key |
|---|---|
| Зарплата | salary |
| Подработка | side_job |
| Подарки | gifts |
| Прочее | income_other |

**Expense categories (top-level → key):**
| Еда | food |
| Развлечения | entertainment |
| Транспорт | transport |
| Дом | home |
| Прочее | expense_other |

**Expense subcategories:**
| Продукты | groceries |
| Обед | lunch |
| Вода и напитки | drinks_water |
| Кафе | cafe |
| Playstation | playstation |
| Кино | cinema |
| Подписки | subscriptions |
| Такси | taxi |
| Топливо | fuel |
| Аренда | rent |
| Коммуналка | utilities |
| Другое | subcategory_other |

Note: `income_other` / `expense_other` / `subcategory_other` are
distinct keys (not one shared `other`) since they translate to
different UZ/RU phrasing depending on context.

### 3. API response schemas

Add `translation_key: str | None` to the Pydantic response models for
wallets, income categories, and expense categories
(`app/schemas/wallets_categories.py`). Existing endpoints — no new
endpoints, no route changes.

## Frontend changes

### 4. i18n keys

New top-level namespace `defaultEntities` in `ru.json` / `uz.json`,
one key per `translation_key` above (e.g.
`defaultEntities.card_uzs`, `defaultEntities.food`,
`defaultEntities.groceries`). RU values = current seed names verbatim
(no visible change for RU users). UZ values = actual Uzbek
translations (need real translations, not placeholders).

### 5. Shared display helper

New helper, e.g. `frontend/src/utils/getDisplayName.ts`:

```ts
function getDisplayName(entity: { name: string; translation_key: string | null }, t: TFunction): string {
  return entity.translation_key
    ? t(`defaultEntities.${entity.translation_key}`)
    : entity.name
}
```

Replace every direct `entity.name` render with
`getDisplayName(entity, t)` in:
- `WalletsSection.tsx`, `IncomeCategoriesSection.tsx`,
  `ExpenseCategoriesSection.tsx` (Settings)
- Add Income / Add Expense / Add Transfer forms (wallet/category
  selects)
- `History` table (category column, wallet references if shown)
- `Analytics` chart labels/legends

### 6. TypeScript types

Add `translation_key: string | null` to the shared entity types
(wherever `Wallet` / `IncomeCategory` / `ExpenseCategory` interfaces
are defined, likely `frontend/src/types/` or inline per API module).

## Out of scope

- Translating user-created entity names (explicitly not required).
- Renaming/editing default entities (still out of scope per Task 14).
- Retroactive translation of already-seeded DB rows — moot here since
  the local DB was just truncated (Task 18 prep session); first
  onboarding after this change seeds with `translation_key` already
  set.
- Any change to which categories/subcategories exist, their count, or
  hierarchy.

## Acceptance criteria

- [ ] Migration adds `translation_key` (nullable) to all 3 tables, reversible
- [ ] New onboarding (`/start`) seeds all default wallets/categories with correct `translation_key` values per table above
- [ ] User-created wallet/category via Settings has `translation_key = NULL`
- [ ] Switching language in Settings (RU ↔ UZ) changes displayed names for default entities everywhere listed in step 5, without a page reload
- [ ] User-created entity names never change regardless of language
- [ ] No TypeScript/build errors; `npm run lint` and `npm run build` pass
- [ ] Full pytest suite still passes

## Verification

1. Run new migration, confirm `translation_key` column exists on all 3 tables via `psql`.
2. Fresh `/start` in Telegram → confirm in `psql` that every seeded row has the expected `translation_key` (spot-check a few against the table above).
3. In the app, add one custom wallet and one custom expense category as Owner → confirm `translation_key IS NULL` for both via `psql`.
4. Switch language RU → UZ in Settings → confirm all default wallet/category names update to Uzbek across Settings, Add Income/Expense/Transfer selects, History, Analytics. Confirm the two custom entities from step 3 keep their original typed name unchanged.
5. Switch back UZ → RU → confirm default names revert, custom names still unchanged.
6. Run full pytest suite — confirm no regressions.

---

## Part 2 — Translation key on history/analytics responses

Depends on: Part 1 above (done)
PRD reference: §4.5, §4.6, §9

### Problem

`GET /transactions/history` (`HistoryItem`) and the analytics
category/subcategory endpoints (`CategoryAmount`, `SubcategoryAmount`)
return only flat name strings for categories, and (in `HistoryItem`)
no category IDs at all. The frontend currently works around this by
matching a transaction's stored category name against the active
category list fetched from `GET /categories/*` (see
`resolveDisplayNameByStoredName` in
`frontend/src/utils/getDisplayName.ts`).

This has two real problems:
1. **Soft-deleted categories/wallets are excluded** from
   `GET /wallets` / `GET /categories/*` (active-only per Task 04).
   A transaction referencing a deleted default category can never be
   matched, so its default name silently stops translating on
   language switch.
2. **Name-collision risk in History specifically**: matching is done
   by exact string equality (`entity.name === storedName`). If a user
   creates their own category with a name identical to a default
   one, History would incorrectly apply the default translation to
   the user's own entries.

Wallet lookups in History already use `wallet_id` (correct, ID-based)
and Analytics category/subcategory lookups already use
`category_id`/`subcategory_id` via a `Map` (correct, ID-based) — so
problem #2 above is History-categories-only. Problem #1 (soft-deleted
entities) affects every place listed below equally, regardless of
whether the existing lookup is ID-based or name-based, because the
active-only list is the shared root cause.

### Fix

Move translation resolution to the backend: compute `translation_key`
via a `LEFT JOIN` against the relevant category/wallet table **without
filtering on `is_deleted`** (unlike `GET /wallets`/`GET /categories/*`,
which intentionally stay active-only for those endpoints — do not
change that filtering, it's correct for its own purpose). Add the
resolved key straight onto the response items below. This removes the
frontend's dependency on holding a full active-entity list just to
resolve a name, and fixes both problems in one place.

### Backend changes

**`app/schemas/history_analytics.py`**

Add nullable `translation_key` fields to `HistoryItem`:
- `wallet_translation_key: str | None`
- `to_wallet_translation_key: str | None`
- `income_category_translation_key: str | None`
- `expense_category_translation_key: str | None` (top-level parent)
- `expense_subcategory_translation_key: str | None`

Add nullable `translation_key` fields to `CategoryAmount` and
`SubcategoryAmount`:
- `CategoryAmount.category_translation_key: str | None`
- `SubcategoryAmount.subcategory_translation_key: str | None`

Keep every existing field unchanged (all current `*_name` string
fields stay exactly as they are — nothing is removed, this is
additive only).

**Service layer** (wherever `HistoryItem`, `CategoryAmount`,
`SubcategoryAmount` are populated — history query, `analytics/summary`
category breakdown, `analytics/expenses-by-subcategory`)

Join each item to its source table (`wallets`, `income_categories`,
`expense_categories`) by ID, selecting `translation_key` alongside the
existing `name` column, with **no `is_deleted` condition on the
join** — a soft-deleted category must still resolve its
`translation_key` for historical transactions. This mirrors the
existing pattern already used to fetch `wallet_name` /
`*_category_name` for these same items (find and reuse that exact
join, just add one more selected column) — do not introduce a second
query or N+1 per item.

**`app/schemas/transactions.py` (`TransactionResponse`, used by
`GET /transactions/{id}`)**

No new field needed here — this endpoint is only used by
`TransactionDetailModal.tsx`, which already resolves display names
correctly via ID lookups against `GET /wallets`/`GET /categories/*`
(Part 1 already covers this path). Confirm this stays true; if you
find `TransactionResponse` also lacks something needed for the
modal's fallback path (see frontend step below), flag it before
proceeding rather than guessing.

### Frontend changes

**Types**

Add the corresponding `*_translation_key: string | null` fields to
the `HistoryItem` type (`frontend/src/api/home.ts` and
`frontend/src/api/history.ts` if it's duplicated there — check both),
and to the `CategoryAmount`/`SubcategoryAmount` types in
`frontend/src/api/analytics.ts`.

**`frontend/src/utils/getDisplayName.ts`**

- Remove the string-matching path for categories: `getHistoryItemTitle`
  and `getHistoryItemSubtitle` must resolve category names using the
  new `*_translation_key` fields directly on `item`, not by scanning
  `references.incomeCategories`/`references.expenseCategories`.
  Keep the same fallback rule as `getDisplayName` (`translation_key ?
  t('defaultEntities.' + key) : storedName`).
- `getHistoryWalletDisplayName` and the wallet resolution inside
  `getHistoryItemSubtitle`: switch from `resolveWalletDisplayNameById`
  (which depends on the active `references.wallets` list) to using
  `item.wallet_translation_key` / `item.to_wallet_translation_key`
  directly, same fallback rule.
- `resolveDisplayNameByStoredName` and `resolveWalletDisplayNameById`
  become unused after this change — remove them if nothing else calls
  them (grep first to confirm), rather than leaving dead code.
- `HistoryDisplayReferences` (the `{ wallets, incomeCategories,
  expenseCategories }` type) may become unnecessary for these
  functions — only remove it if it's confirmed unused elsewhere after
  the change (check `TransactionDetailModal.tsx`'s own usage
  carefully, it constructs its own authoritative item and may still
  need this type for its ID-based lookups — do not break that path).

**`frontend/src/pages/HistoryPage.tsx`, `HomePage.tsx`**

Update calls to `getHistoryItemTitle`/`getHistoryItemSubtitle`/
`getHistoryWalletDisplayName` if their signatures changed (dropping
the now-unused `references` param, if you removed it above) — check
both call sites, don't miss `HomePage.tsx`'s recent-transactions list.

**`frontend/src/components/TransactionDetailModal.tsx`**

Leave `buildAuthoritativeHistoryItem`'s ID-based resolution as-is
(it's already correct). Only change: where it currently falls back to
`fallback.wallet_name` / `fallback.income_category_name` /
`fallback.expense_category_name` / `fallback.expense_subcategory_name`
(i.e. when the entity isn't found in the active list — soft-deleted
case), use the new translated fallback instead: resolve
`fallback.*_translation_key` the same way `getDisplayName` does,
rather than the raw stored name. This also fixes the brief
untranslated flash during `loadStatus === 'loading'`, since
`TransactionDetails` renders `listItem` directly during that state.

**`frontend/src/utils/analyticsCharts.ts`,
`analyticsDrillDown.ts`**

In `buildParentCategoryCards` and `prepareDonutSlices`: prefer
`entry.category_translation_key` (resolve via `t('defaultEntities.' +
key)`) over the existing `displayNameById?.get(entry.category_id) ??
entry.category_name` fallback chain — try translation_key first, then
`displayNameById`, then raw name, in that order. Same pattern in
`buildSubcategoryDisplayEntries` for `subcategory_translation_key`.
Do not remove the `displayNameById` parameter/plumbing — keep it as a
secondary fallback for any caller that hasn't been updated to pass
translation keys, so nothing breaks silently if a call site is missed.

### Explicitly out of scope

- Settings screens, Add/Edit transaction forms — already correct via
  Part 1 (`GET /wallets`/`GET /categories/*` responses already carry
  `translation_key`, ID-based, active-only is intentional there).
- Any change to `is_deleted` filtering behavior on `GET /wallets` /
  `GET /categories/*` themselves.
- Any change to which fields are required vs optional on existing
  request schemas.
- Adding category/wallet IDs to `HistoryItem` — not needed, the new
  translation_key fields make ID exposure unnecessary for this
  purpose.

### Acceptance criteria

- [ ] `HistoryItem`, `CategoryAmount`, `SubcategoryAmount` responses
      include the new nullable `translation_key` fields, computed via
      JOIN with no `is_deleted` filter on the joined table.
- [ ] A transaction referencing a soft-deleted default category or
      wallet still shows the correctly translated name in History,
      History detail modal, and Analytics after a language switch.
- [ ] A user-created category with a name identical to a default
      category's name is never translated in History (confirms the
      string-matching removal actually took effect).
- [ ] No regression in Settings/Add-transaction category/wallet
      display (Part 1 behavior unchanged).
- [ ] No N+1 query introduced — confirm via existing query-count test
      pattern (see `backend/tests/test_history_analytics.py`,
      Task 16 precedent) that the new joins don't add a
      per-item query.
- [ ] Full backend pytest suite passes.
- [ ] `npm run lint` and `npm run build` pass.

### Verification

1. Fresh `/start`, add one income/expense transaction using default
   (seeded) categories and wallets.
2. As Owner, soft-delete the expense category used in step 1 via
   Settings.
3. Switch language RU → UZ. Confirm: History list, History detail
   modal, and Analytics (category card + subcategory drill-down) all
   show the translated name for the now-deleted category — not the
   raw Russian name.
4. Create a new custom expense category named identically to one of
   the default top-level categories (e.g. "Еда"). Add a transaction
   using this custom category. Switch language RU → UZ. Confirm this
   transaction's category is NOT translated (stays "Еда" in both
   languages) while the real default "Еда" category's transactions
   ARE translated.
5. Run the query-count / EXPLAIN checks from the acceptance criteria.
6. Run full pytest suite and frontend lint/build.

## Changelog

**Part 1 — implemented 2026-07-23.**

### Backend
- Migration `backend/alembic/versions/g7b8c9d0e1f2_add_translation_key_to_entities.py` — nullable `translation_key` on `wallets`, `income_categories`, `expense_categories` (reversible).
- Models: `backend/app/models/wallet.py`, `income_category.py`, `expense_category.py` — added column.
- Seed: `backend/bot/onboarding.py` — all default rows get `translation_key` per spec table; user-created rows unchanged (NULL).
- API schemas: `backend/app/schemas/wallets_categories.py` — `translation_key: str | None` on Wallet/Income/Expense **Response** models only.
- API routes: `backend/app/api/v1/wallets.py`, `backend/app/api/v1/categories.py` — include `translation_key` in list/create/update responses.
- Tests updated: `backend/tests/test_onboarding.py` (seed key assertion), `backend/tests/test_wallets_categories.py` (response field sets).

### Frontend
- Types: `frontend/src/api/wallets.ts`, `categories.ts`, `transactions.ts` — `translation_key: string | null`.
- i18n: `frontend/src/i18n/locales/ru.json`, `uz.json` — new `defaultEntities` namespace (all 25 keys).
- Helper: `frontend/src/utils/getDisplayName.ts` — `getDisplayName()` plus History/Analytics resolver helpers.
- Settings: `WalletsSection.tsx`, `IncomeCategoriesSection.tsx`, `ExpenseCategoriesSection.tsx`, `EditableEntityList.tsx`.
- Add/Edit forms: `AddIncomePage.tsx`, `AddExpensePage.tsx`, `AddTransferPage.tsx`, `EditIncomePage.tsx`, `EditExpensePage.tsx`, `EditTransferPage.tsx`.
- History/Home: `HistoryPage.tsx`, `HomePage.tsx`, `TransactionDetailModal.tsx` — resolve display names from cached entities (History API still returns stored RU names).
- Analytics: `AnalyticsMainPage.tsx`, `AnalyticsCategoriesPage.tsx`, `AnalyticsCategoryDetailPage.tsx`, `CategoryDrillDownCard.tsx` (via chart data), `analyticsCharts.ts`, `analyticsDrillDown.ts`.

### Test results
- Backend pytest: **84 passed** (baseline before: 84 collected; 3 failures after initial implementation fixed by updating response-field assertions → **84 passed**).
- Frontend: `npm run lint` — pass (2 pre-existing oxlint warnings); `npm run build` — pass.

### Deviations
- Task file mentions an "i18n keys" section with exact UZ strings; that section was not present in the doc — UZ values were written as proper translations (not placeholders).
- History/Home use cached entity lists + name/ID lookup because the History API returns denormalized name strings, not entity objects with `translation_key` (no History schema/route changes per spec).
- Category icon lookup (`getIncomeCategoryIcon` / `getExpenseCategoryIcon`) still keys off stored `name` (RU seed text), not translated label — icons are not user-visible names.

**Part 2 — implemented 2026-07-23.**

### Backend
- Schemas: `backend/app/schemas/history_analytics.py` — nullable `*_translation_key` fields on `HistoryItem` (wallet, to_wallet, income/expense category, expense subcategory), `CategoryAmount.category_translation_key`, `SubcategoryAmount.subcategory_translation_key`.
- Service: `backend/app/services/history_analytics.py` — extended existing LEFT JOINs in `get_history`, `get_expenses_by_category`, `get_expenses_by_subcategory`, `get_income_by_category` to select `translation_key` alongside `name` (no `is_deleted` filter on joins; added to `GROUP BY` where applicable).
- Tests: `backend/tests/test_history_analytics.py` — new `TestTranslationKeysOnResponses` class (soft-deleted entity keys on history/analytics, null keys for user-created entities, query-count unchanged with translation_key in SELECT).

### Frontend
- Types: `frontend/src/api/home.ts` (`HistoryItem`), `frontend/src/api/analytics.ts` (`CategoryAmount`, `SubcategoryAmount`) — matching `*_translation_key` fields.
- Helper: `frontend/src/utils/getDisplayName.ts` — `getHistoryItemTitle`/`getHistoryItemSubtitle`/`getHistoryWalletDisplayName` now resolve from item `*_translation_key` fields directly; added `resolveStoredEntityDisplayName`, `resolveCategoryAmountDisplayName`, `resolveSubcategoryAmountDisplayName`; removed `resolveDisplayNameByStoredName`, `resolveWalletDisplayNameById`, `HistoryDisplayReferences`.
- History/Home: `frontend/src/pages/HistoryPage.tsx`, `frontend/src/pages/HomePage.tsx` — dropped wallet/category reference fetching; updated helper call signatures (no `references` param).
- Detail modal: `frontend/src/components/TransactionDetailModal.tsx` — `buildAuthoritativeHistoryItem` populates `*_translation_key` fields; fallback branches use `resolveStoredEntityDisplayName` instead of raw stored names; ID-based resolution unchanged.
- Analytics: `frontend/src/utils/analyticsCharts.ts`, `frontend/src/utils/analyticsDrillDown.ts`, `AnalyticsMainPage.tsx`, `AnalyticsCategoriesPage.tsx`, `AnalyticsCategoryDetailPage.tsx` — translation_key-first display name resolution (then `displayNameById`, then raw name); `displayNameById` plumbing retained.

### Test results
- Backend pytest: **88 passed** (baseline before: **84 passed**; +4 new tests, 0 regressions).
- Frontend: `npm run lint` — pass (2 pre-existing oxlint warnings); `npm run build` — pass.

### Deviations
- Subcategory analytics test uses an active parent + soft-deleted subcategory (not soft-deleted parent): `GET /analytics/expenses-by-subcategory` validates parent via `get_active_expense_parent` and returns 404 for a soft-deleted parent ID — endpoint behaviour unchanged per spec.
- `TransactionResponse` unchanged — modal fallback resolves via `HistoryItem.*_translation_key` from the history list item, no new field needed on `GET /transactions/{id}`.