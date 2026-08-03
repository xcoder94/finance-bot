# Phase 5 — Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Person opens Analytics with tabs `Графики` / `История`, shares one period, filters charts by UZS/USD without conversion, drills parent→subcategory→filtered History, and reads the three blocks under the donut — shared wallets only.

**Architecture:** Keep existing `/api/v1/analytics/*` and `/api/v1/transactions/history` shapes; extend them (personal exclusion, trend end-month, weekday averages + most-expensive day, history `expense_category_id`, soft-deleted parent subcategory). Rebuild Analytics UI into in-page tabs with shared period state; replace MVP1 `/analytics/categories/*` route drill-down with in-place donut ladder. Keep standalone `/history` for Home entry (Phase 4). Seed personal/multi-month fixtures only in pytest — never the working DB.

**Tech Stack:** Python/FastAPI/pytest; React/Vite/TypeScript/TelegramUI/Zustand/react-i18next/recharts; vitest. No new packages without asking.

## Global Constraints

- Spec: `docs/tasks/phase-05-analytics.md` + PRD §17.4, §17.5, §5, §15.4 (display). Design: `docs/design/Chontak MVP2.dc.html` Analytics screens one-to-one **except** approved UZS/USD switch on `Графики`.
- Tab names exactly `Графики` · `История`. Period shared; never reset by tab switch or drill-down back.
- Currency switch = wallet filter, never conversion. No dividing UZS by a rate. Switch governs `Графики` only; `История` lists every op in its own currency.
- Ladder: parent → subcategory → History filter. «Другое» tap is a no-op. No third chart level.
- Exactly 8 category colours + «Другое» overflow (§5). Colour bound to category.
- Shared wallets only in all chart aggregates. Personal ops excluded from aggregates (fixtures until Phase 7 UI).
- Empty month replaces **whole** `Графики` tab (donut + all three blocks), not donut alone.
- Soft-deleted category with past ops: own name, own colour, no marker (§15.4). Seed soft-deleted in tests.
- Block titles/captions verbatim Russian from PRD/design: `Доход и расход, 12 месяцев`; `Средний расход в день`; `Самый дорогой день`; `Расход по дням недели`; unit `млн сум` / `$`; caption `сум · N день/дня/дней`; `в среднем … сум` / `$`.
- Twelve-month window ends at **selected** month.
- Elapsed days / “today” use Asia/Tashkent.
- Uzbek out of scope. Do **not** edit `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/*`, `docs/tasks/*`.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-5-analytics` (already checked out — do not create/switch/merge branches).
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Commit after each task. Report pytest + vitest; list stubs/finish-later.
- Stop at end of Phase 5. Do not start Phase 6 / Settings category CRUD.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/history_analytics.py` | Personal exclusion; trend end-month; Tashkent elapsed days; weekday averages; most expensive weekday; history category filter; soft-deleted parent subcategory |
| `backend/app/schemas/history_analytics.py` | Summary fields for most expensive weekday |
| `backend/app/api/v1/analytics.py` | `end_month` on `/trend` |
| `backend/app/api/v1/history.py` | Optional `expense_category_id` query |
| `backend/app/services/wallets_categories.py` | Parent lookup that allows soft-deleted for analytics drill |
| `backend/tests/test_history_analytics.py` | Update + Phase 5 fixture/tests |
| `backend/tests/test_phase5_analytics.py` | New focused Phase 5 tests + seed fixture |
| `frontend/src/api/analytics.ts` / `history.ts` | Client params + summary types |
| `frontend/src/contexts/AnalyticsContext.tsx` | Tabs, drill, history filter state |
| `frontend/src/pages/AnalyticsPage.tsx` / `analytics/*` | Tabs UI; remove category routes |
| `frontend/src/pages/analytics/AnalyticsChartsTab.tsx` | Donut ladder + blocks + empty |
| `frontend/src/pages/analytics/AnalyticsHistoryTab.tsx` | History list inside Analytics |
| `frontend/src/components/analytics/CategoryDonutChart.tsx` | Clickable sectors/legend; «Другое» inert |
| `frontend/src/utils/analytics*.ts` + new helpers | «Другое», day plurals, most expensive, no conversion |
| `frontend/src/i18n/locales/ru.json` | Verbatim strings |
| `frontend/src/index.css` | Design match for tabs/tiles/empty |
| Vitest | Period retention, currency isolation, drill, «Другое», trend window, no conversion helper |

---

### Task 1: Backend — exclude personal wallets from analytics aggregates + fixtures

**Files:**
- Modify: `backend/app/services/history_analytics.py` — in `get_expenses_by_category`, `get_expenses_by_subcategory`, `get_income_by_category`, `get_trend`, `get_summary`: join wallet and require `wallet.is_personal.is_(False)` (for transfer legs in summary, both from/to wallets must be non-personal, matching `get_wallet_balances`).
- Create: `backend/tests/test_phase5_analytics.py` — seed fixture across ≥2 months, both currencies, ≥2 parents, plus a personal wallet expense that must not appear in aggregates.
- Modify: `backend/tests/test_history_analytics.py` only if existing tests break due to personal exclusion (prefer keeping them green by ensuring seeded wallets stay shared).

**Interfaces:**
- Produces: all chart aggregate queries ignore `Wallet.is_personal == True` operations.
- Does not change History list visibility (History still returns personal ops of the family as today — Phase 7 product rules).

- [ ] **Step 1: Write failing tests** in `backend/tests/test_phase5_analytics.py`:

```python
# seed: shared UZS/USD wallets; personal UZS wallet; parents Food + Transport with subs;
# expenses in selected month on shared + personal; expense previous month on shared.
# Assert GET /analytics/expenses-by-category?currency=UZS for selected month
# amount equals shared only (personal amount absent).
# Assert GET /analytics/summary same period: by_currency UZS expense excludes personal.
# Assert GET /analytics/trend entries for that month UZS expense exclude personal.
```

- [ ] **Step 2:** Run `cd backend && ./venv/bin/pytest -q tests/test_phase5_analytics.py -k personal` — FAIL (personal currently included).

- [ ] **Step 3:** Add `is_personal.is_(False)` filters to the five aggregate functions (and summary transfer destination join).

- [ ] **Step 4:** Focused tests PASS; `cd backend && ./venv/bin/pytest -q` green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/history_analytics.py backend/tests/test_phase5_analytics.py backend/tests/test_history_analytics.py
git commit -m "$(cat <<'EOF'
feat(analytics): exclude personal wallets from chart aggregates

EOF
)"
```

---

### Task 2: Backend — trend ends at selected month; summary weekday averages + most expensive day; Tashkent elapsed days

**Files:**
- Modify: `backend/app/services/history_analytics.py`
  - `last_twelve_months(end: datetime)` already exists — change call sites so `get_trend` accepts `end: datetime | None` (default now UTC→Tashkent month) and builds months ending at that month.
  - `elapsed_days_in_period`: compare against `datetime.now(ZoneInfo("Asia/Tashkent")).date()` instead of UTC `now.date()`.
  - In `get_summary`: compute weekday **averages** for expenses: for each currency and weekday index 0..6, `avg = total_sum // occurrence_count` where `occurrence_count` is the number of calendar dates in `[date_from.date(), min(date_to.date(), tashkent_today)]` with that ISO weekday (at least 1 if sum>0 and count would be 0 — use max(count,1) only when summing days in range; if a weekday never occurs in range, avg stays 0).
  - Add to each `PerCurrencySummary`: `most_expensive_weekday: int | None` (0=Mon..6=Sun) and `most_expensive_weekday_average: int` — weekday with highest average expense; if all zero, both `None`/`0`.
  - Keep `day_of_week_expense` / `day_of_week_income` lists as **averages for expense**, income may stay sums or averages consistently — Phase 5 UI only needs expense averages; set expense list to averages; leave income as sums unless tests require otherwise (document in report).
- Modify: `backend/app/schemas/history_analytics.py` — extend `PerCurrencySummary`:

```python
most_expensive_weekday: int | None = None  # 0=Mon .. 6=Sun
most_expensive_weekday_average: int = Field(default=0, ge=0)
```

- Modify: `backend/app/api/v1/analytics.py` — `GET /trend` accepts optional `end_month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$")`. Parse to first day of that month UTC; pass as `end` into `get_trend`. Invalid → 422.
- Modify: frontend types later (Task 5); this task is backend-only.
- Tests in `backend/tests/test_phase5_analytics.py` + update `TestAnalyticsTrendAndSummary` in `test_history_analytics.py` for average semantics / new fields.

**Interfaces:**
- `get_trend(session, family_budget_id, end: datetime | None = None) -> list[TrendEntry]`
- `GET /api/v1/analytics/trend?end_month=YYYY-MM`
- `PerCurrencySummary.most_expensive_weekday`, `.most_expensive_weekday_average`
- `day_of_week_expense[currency][i]` = average expense for that weekday

- [ ] **Step 1:** Failing tests:
  - Selecting end_month=`2026-03` returns months `2025-04`..`2026-03` (not rolling from “today” if today ≠ March).
  - Weekday averages: seed two Mondays expenses 100 and 300 → Monday avg 200 (with two Mondays in range).
  - Most expensive weekday matches highest average.
  - Elapsed days for current month uses Tashkent today (unit-test `elapsed_days_in_period` with fixed now).

- [ ] **Step 2:** Implement; update old tests that asserted weekday **sums**.

- [ ] **Step 3:** `pytest -q` green; commit:

```bash
git commit -m "$(cat <<'EOF'
feat(analytics): anchor trend window and weekday averages

EOF
)"
```

---

### Task 3: Backend — history `expense_category_id` filter; soft-deleted parent subcategory + soft-deleted category fixture

**Files:**
- Modify: `backend/app/services/history_analytics.py` `get_history` — optional `expense_category_id: uuid.UUID | None`. When set, filter `Transaction.type == "expense"` AND `Transaction.expense_category_id == expense_category_id`.
- Modify: `backend/app/api/v1/history.py` — add Query `expense_category_id: uuid.UUID | None = None`.
- Modify: `get_expenses_by_subcategory` — resolve parent with a helper that allows soft-deleted parents (name e.g. `get_expense_parent_including_deleted`) instead of `get_active_expense_parent`. Still 404 if missing / wrong family / not a parent (`parent_id is not None`).
- Modify: `backend/app/services/wallets_categories.py` — add `get_expense_parent_including_deleted`.
- Tests: soft-deleted parent still returns subcategory amounts; soft-deleted category appears in `expenses-by-category` with its name; history filter returns only matching subcategory ops.

**Interfaces:**
- `GET /api/v1/transactions/history?date_from&date_to&expense_category_id=&limit&offset`
- Soft-deleted parents drillable in analytics.

- [ ] Steps: TDD → implement → `pytest -q` → commit:

```bash
git commit -m "$(cat <<'EOF'
feat(analytics): history category filter and soft-deleted drill

EOF
)"
```

---

### Task 4: Frontend API clients + pure helpers (TDD)

**Files:**
- Modify: `frontend/src/api/analytics.ts` — `fetchTrend(endMonth: string)`; extend summary types with `most_expensive_weekday`, `most_expensive_weekday_average`.
- Modify: `frontend/src/api/history.ts` / `home.ts` types as needed; `fetchHistoryPage(..., expenseCategoryId?: string)`.
- Modify: `frontend/src/utils/analyticsCharts.ts` — other label consumers use «Другое»; ensure overflow key stays `OTHER_CATEGORY_KEY`.
- Create: `frontend/src/utils/analyticsPeriod.ts` + `.test.ts`:
  - `twelveMonthKeysEndingAt(selected: SelectedMonth): string[]` — 12 keys ending at selected.
  - Prove it does not use a FX rate / division helper.
- Create: `frontend/src/utils/dayCountLabel.ts` + `.test.ts` — Russian plural: `1 день`, `2 дня`, `3 дня`, `4 дня`, `5 дней`, `21 день`, `31 день`.
- Create: `frontend/src/utils/analyticsDrill.ts` + `.test.ts`:
  - `isOtherCategoryKey(key: string): boolean`
  - `shouldIgnoreDonutTap(key: string): boolean` — true for other
  - `historyFilterAfterSubcategoryTap(subId, name, colorIndex)` / `clearHistoryFilter`
- Create: `frontend/src/utils/noCurrencyConversion.ts` + `.test.ts` — export a guard/test that USD mode uses raw USD wallet amounts only (document: tests assert charts path never calls a `convertUzsToUsd` / divide-by-rate helper; keep a trivial `assertNoFxConversionUsed` constant `false` for FX helper existence check — or simply test that selecting USD filters by currency tag without transforming amounts).
- Modify: `frontend/src/i18n/locales/ru.json` — add keys (verbatim):
  - `analytics.tabCharts`: `Графики`
  - `analytics.tabHistory`: `История`
  - `analytics.other`: `Другое` (replace `Прочее`)
  - `analytics.trendTitle`: `Доход и расход, 12 месяцев`
  - `analytics.trendUnitUzs`: `млн сум`
  - `analytics.trendUnitUsd`: `$`
  - `analytics.avgDaily`: `Средний расход в день`
  - `analytics.mostExpensiveDay`: `Самый дорогой день`
  - `analytics.weekdayExpenses`: `Расход по дням недели` (update if different)
  - `analytics.avgDailyCaption`: `сум · {{count}} {{dayWord}}` / USD variant `$ · {{count}} {{dayWord}}`
  - `analytics.mostExpensiveCaption`: `в среднем {{amount}}`
  - `analytics.chartsEmptyTitle`: `За {{month}} расходов нет` (or match design month form)
  - `analytics.chartsEmptyHint`: `Диаграмма появится после первой операции месяца.`
  - `analytics.sharesInside`: `Доли внутри категории · {{month}}`
  - `analytics.resetFilter`: `Сбросить`
  - Weekday short labels already exist — ensure `Сб` etc. match design.

- [ ] Vitest green for new helpers; `npx vitest run --reporter=dot`; commit:

```bash
git commit -m "$(cat <<'EOF'
feat(analytics): client params and chart helper tests

EOF
)"
```

---

### Task 5: Analytics shell — shared period, tabs `Графики`/`История`, currency on charts only

**Files:**
- Modify: `frontend/src/contexts/AnalyticsContext.tsx` — add:
  - `activeTab: 'charts' | 'history'`
  - `setActiveTab`
  - `drillParent: { id: string; name: string } | null` + setter
  - `historyCategoryFilter: { id: string; name: string; color: string } | null` + setter
  - Keep period + currency; switching tab must not reset period or drill unless explicitly clearing filter on back rules in Task 6/7.
- Modify: `frontend/src/pages/analytics/AnalyticsLayout.tsx` — render shared period header (month pager / range) once; tab strip `Графики` | `История` matching design; currency chip **only when `activeTab === 'charts'`** (Home-style chip, approved deviation).
- Modify: `frontend/src/pages/AnalyticsPage.tsx` — remove routes `categories` and `categories/:categoryKey`; single outlet content switching by `activeTab` OR child components rendered by layout.
- Delete or stop routing: `AnalyticsCategoriesPage.tsx`, `AnalyticsCategoryDetailPage.tsx`, `CategoryDrillDownCard.tsx` (remove imports; delete files if unused).
- Create tests: `frontend/src/pages/analytics/analyticsTabState.test.ts` — pure reducer/helper proving tab switch keeps `selectedMonth` / range; currency change does not apply to history filter object.

**Interfaces:**
- Shared period state owned by `AnalyticsLayout` / context.
- `activeTab` toggled by tab buttons without remounting period state.

- [ ] Implement → vitest → commit:

```bash
git commit -m "$(cat <<'EOF'
feat(analytics): tabs with shared period and currency on charts

EOF
)"
```

---

### Task 6: `Графики` tab — in-place drill, «Другое» no-op, blocks, whole-tab empty

**Files:**
- Create: `frontend/src/pages/analytics/AnalyticsChartsTab.tsx` (replace/rewrite `AnalyticsMainPage.tsx` content).
- Modify: `frontend/src/components/analytics/CategoryDonutChart.tsx` — accept `onSliceActivate?(key: string)` / pass category id via slice metadata; legend/sector clickable; if `shouldIgnoreDonutTap` → no handler call. Extend `DonutSlice` with optional `key: string`.
- Modify: `TrendChart.tsx` — title/unit from props (`млн сум` / `$`); data from `fetchTrend(endMonth)` filtered by selected currency; months = `twelveMonthKeysEndingAt(selectedMonth)`.
- Modify: tiles: remove old transfer/net summary card; show two tiles `Средний расход в день` + `Самый дорогой день` then `Расход по дням недели` using **averages**.
- Empty: if no expense slices (and no expense total for currency/period), render **only** the empty card (design copy); hide donut + three blocks.
- Drill: tap parent → set `drillParent`, fetch subcategories, rebuild donut with shares inside parent, heading = back + parent name, total under heading.
- Tap subcategory → set `historyCategoryFilter`, `setActiveTab('history')`; period unchanged.
- Tap «Другое» → nothing.
- Back from drill → `drillParent = null`; period unchanged.
- Fast month paging: fetches keyed by `rangeKey`+currency so UI never shows previous month figures under new heading (keep existing fetchKey pattern; disable stale writes with request id or rely on fetchKey in `useFetchBlock`).
- CSS in `frontend/src/index.css` to match design spacing/tiles/tabs.
- Tests: «Другое» no-op helper; drill → history filter helper; empty whole-tab predicate; trend keys end at selected month; assert no FX conversion helper imported by charts module (grep-style unit test).

- [ ] Commit:

```bash
git commit -m "$(cat <<'EOF'
feat(analytics): charts tab drill-down blocks and empty state

EOF
)"
```

---

### Task 7: `История` tab inside Analytics + filter chip + back clears filter

**Files:**
- Create: `frontend/src/pages/analytics/AnalyticsHistoryTab.tsx` — list ops for shared period via `fetchHistoryPage` (all currencies); when `historyCategoryFilter` set, pass `expense_category_id` and show chip (color + name + `Сбросить`).
- `Сбросить` or leaving filter: clear `historyCategoryFilter`; if coming from subcategory drill, return `activeTab` to `charts` **keeping** `drillParent` (spec: Back → subcategory chart; filter cleared). Implement `clearHistoryFilter({ returnToDrill: true })` used by chip reset when filter was set from drill.
- Reuse History row rendering patterns from `HistoryPage.tsx` (extract shared presentational helpers into `frontend/src/components/history/HistoryTransactionList.tsx` if duplication is large; otherwise carefully duplicate minimal list markup to avoid breaking `/history`).
- Standalone `HistoryPage.tsx` remains for Home → `/history`; do not remove.
- Extend `historyBackTarget` only if needed for edit sheets opened from analytics history (prefer `state: { from: 'analytics' }` → back to `/analytics` with history tab — if edit routes already use location state, wire analogously).
- Vitest: filter clear restores charts drill; period unchanged; history fetch args include category id when filter set; currency switch on charts does not change history query currency (history has no currency param).

- [ ] Commit:

```bash
git commit -m "$(cat <<'EOF'
feat(analytics): history tab with subcategory filter

EOF
)"
```

---

### Task 8: Integration polish, full suites, soft-deleted display check, phase exit

**Files:**
- Ensure soft-deleted category colour/name still shown (backend already; frontend uses API names + `buildCategoryColorIndexMap` including deleted ids present in expense list — if categories list omits deleted, color map must fall back by stable id hash or include deleted-from-analytics entries; fix so soft-deleted keeps bound colour without a “deleted” marker).
- Remove dead MVP1 analytics drill routes/files if still present.
- Run full: `cd backend && ./venv/bin/pytest -q` and `cd frontend && npx vitest run --reporter=dot`.
- Fix failures.
- Confirm acceptance mapping in worker report.
- Final commit if needed:

```bash
git commit -m "$(cat <<'EOF'
fix(analytics): phase 5 polish and suite green

EOF
)"
```

**Deferred allowed:** hand-check of soft-deleted in real Telegram client if delete UI is Phase 6 — but automated fixture test must exist (Task 3). Do not defer personal exclusion tests.

---

## Spec coverage checklist (self-review)

| Acceptance / requirement | Task |
|--------------------------|------|
| Tabs `Графики`/`История`; shared period | 5 |
| UZS/USD filter on charts; no conversion | 5, 6, 4 |
| History lists all currencies | 7 |
| Donut parent→sub; shares inside parent | 6 |
| Subcategory → History filter; back clears; period kept | 6, 7 |
| «Другое» no-op | 4, 6 |
| Three blocks order + units | 6 |
| 12-month ends at selected month; paging consistency | 2, 6 |
| Whole-tab empty | 6 |
| Personal excluded from aggregates (fixtures) | 1 |
| Soft-deleted name/colour in analytics | 3, 8 |

No placeholders remain. Types aligned across tasks: `end_month`, `most_expensive_weekday`, `expense_category_id`, `activeTab`, `drillParent`, `historyCategoryFilter`.
