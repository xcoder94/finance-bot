# Task 12 — Frontend: Analytics

Depends on: Task 09 (`09-frontend-home.md` — done, `SegmentedControl`
currency toggle pattern, month-navigation pattern), Task 11
(`11-frontend-history.md` — done, period-filter tab pattern:
`SegmentedControl` "Месяц"/"Диапазон", masked `ДД.ММ.ГГГГ` range
inputs, `BlockError`/`Spinner`/retry pattern), Task 06
(`06-api-history-analytics.md` — done, all analytics endpoints already
implemented in `analytics.py`/`history_analytics.py`, confirmed
sufficient for this task, **no backend changes**), Task 04
(`04-api-wallets-categories.md` — category list endpoints, needed to
resolve stable category color order, see "Color assignment" below).

PRD reference: §4.6 (Analytics)

## Goal

Replace the `PlaceholderPage` currently mounted at `/analytics` in
`AppShell.tsx` (via the existing lazy-loaded `AnalyticsRoute`, do not
change the lazy-loading setup) with a real Analytics screen: period
filter, currency toggle, expense-category donut, conditional
income-category donut, 12-month income/expense trend, month summary,
and a full-width weekday-expense chart.

**This task is delivered in two parts, both living in this same task
file (not two separate task numbers), per the Task 11 precedent:**
- **Part 1 (this prompt)**: the main Analytics screen described below.
- **Part 2 (separate follow-up prompt, sent later)**: drill-down —
  tapping the "Расходы по категориям" card opens an internal page with
  one card per parent expense category, each showing its own
  subcategory donut; tapping one of those cards shows a plain list of
  subcategories with amounts. Do **not** build any drill-down
  navigation, routes, or subcategory components in Part 1 — out of
  scope until the Part 2 prompt is sent.

## Reference mockup

Two screenshots are provided alongside this task file ("Аналитика").
**Scope of the mockup**: card order, chart types (donut for
categories, grouped bar for the 12-month trend, bar for weekday
expenses), and general layout/spacing are the source of truth. The
mockup is **not** the source of truth for the following — this
document wins where they differ:
- **Colors**: the mockup's pastel category colors are not used. Use
  the fixed 8-color categorical palette specified below.
- **Category color order**: the mockup implies color-by-amount-rank.
  This project uses **color-by-category, fixed forever** (confirmed
  decision) — see "Color assignment".
- **Period selector**: the mockup shows Home-style `‹ Июнь 2026 ›`
  arrows only. This screen uses the same two-tab
  "Месяц"/"Диапазон" `SegmentedControl` pattern as `HistoryPage.tsx`
  instead (reuse that component/logic exactly, do not reimplement).
- **"Доходы по дням недели"**: shown in the mockup, but is **removed**
  from this build — do not render it. "Расходы по дням недели"
  becomes full width in its place.

## Dependencies / setup

Install `recharts` (latest stable). If `npm install recharts` reports
a peer-dependency conflict against React 19, use
`npm install recharts --legacy-peer-deps`, consistent with the
existing `@telegram-apps/telegram-ui` install convention in this
project (expected, not a bug — do not attempt to work around it
another way). Add it to `frontend/package.json` `dependencies`.

## Period filter & currency toggle

Reuse `HistoryPage.tsx`'s period-filter implementation as closely as
possible (ideally by extracting/reusing the same tab component and
date-range-resolution logic, not by duplicating it): `SegmentedControl`
with "Месяц" (default) and "Диапазон" tabs, identical month-navigation
and masked-date-range behavior, identical validation rules.

Add a second `SegmentedControl` for currency (`UZS`/`USD`), same
pattern as Home's currency toggle. **One currency selection applies to
every chart on this page** — there is no per-chart currency control.

Both the resolved `date_from`/`date_to` (from the active period tab)
and the selected currency are inputs to the data-fetching described
below. Changing either re-fetches the affected charts.

## Data fetching & charts

No backend changes in this task — all endpoints below already exist
in `analytics.py` / `history_analytics.py`. Add typed fetch helpers in
a new `frontend/src/api/analytics.ts`, following the same
`apiGet`/`HomeApiError` pattern already used in `history.ts`.

### 1. "Расходы по категориям" (donut)

`GET /api/v1/analytics/expenses-by-category?currency&date_from&date_to`
→ `CategoryAmount[]`. Render as a donut (Recharts `PieChart` +
`Pie` with `innerRadius`), legend below listing name + percentage of
total, same visual pattern as shown in the widget already reviewed
with the user in chat. If the response is empty (no expenses in the
period/currency), show an empty-state message in the card instead of
an empty chart — do not render a zero-value donut.

### 2. "Доходы по категориям" (donut, conditional)

`GET /api/v1/analytics/income-by-category?currency&date_from&date_to`
→ `CategoryAmount[]`. **Always call this endpoint** when the page
loads/refetches, but **only render the card** if the response contains
3 or more entries with `amount > 0`. Otherwise the card is not shown
at all (not shown empty, not shown collapsed — simply absent from the
layout). This is a frontend-only condition; backend is unchanged.

### 3. "Доход и расход по месяцам" (trend)

`GET /api/v1/analytics/trend` — **no query parameters**, this endpoint
always returns the last 12 months regardless of the page's period
filter (confirmed, matches existing `get_trend` backend behavior,
intentionally not wired to the period tabs). Response is
`TrendEntry[]` with `month`, `currency`, `income`, `expense` for every
month/currency combination that has any activity. Filter the response
client-side to `entry.currency === selectedCurrency` before rendering.
Render as a grouped/paired bar chart, one pair (income + expense) per
month, x-axis labeled with short month names (reuse or add a
`month`-key → short-label formatter, e.g. `"2026-07"` → `"Июл"`).
Colors: income green (`c-green`/status-success token), expense red
(`c-red`/status-danger token) — semantic pair, not from the
categorical palette. If a given month has no entry for the selected
currency, treat it as `{income: 0, expense: 0}` (do not skip the
month — all 12 months must always appear on the x-axis).

**Y-axis tick formatting (found during Part 1 verification, fix before
closing Part 1)**: raw UZS amounts are commonly 7+ digits and get
clipped by recharts' default Y-axis left margin (right-aligned tick
text overflowing past the chart's left edge — a known recharts
behavior with large numbers, not specific to this codebase). Add a
`tickFormatter` on the `YAxis` that renders a compact form with three
tiers: **≥1,000,000,000 → `млрд`** (e.g. `2,8 млрд` for 2800000000,
not `2 800 млн`), **≥1,000,000 → `млн`** (e.g. `2,1 млн` for 2100000),
**≥1,000 → `тыс`** (e.g. `850 тыс` for 850000), plain number below
1000. One decimal place, comma as decimal separator (`ru` locale
convention already used elsewhere in this project). Increase the
chart's left margin / explicit `YAxis width` enough that the compact
label never clips at any of the 12 months' values, and add enough top
margin/padding above the chart's plot area that the topmost Y-axis
tick label is never clipped by the card's edge. Apply the same
compact-tick treatment to any other chart on this screen whose Y-axis
can reach 4+ digit UZS values (the weekday expense bar chart) for
consistency — do not leave one chart compact and the other raw.

### 4. Сводка за месяц (summary card)

Reuse `GET /api/v1/analytics/summary?date_from&date_to` (already
fetched the same way `HistoryPage.tsx` fetches it via
`fetchSummaryForRange`) — this task adds a **new** card, distinct from
History's summary cards, showing (for the selected currency only, one
`PerCurrencySummary` entry): Доход, Расход, Переводы (нетто)
(`transfer_net`), Итоговое изменение (`net_change`), and — used for
the first time in this project — **Средний расход в день**
(`average_daily_expense`), all formatted with the existing
`formatCurrency` helper. Layout: metric-card grid, matching the
reviewed mockup structure (two-column top row, average-daily-expense
as a wide row below). If the selected currency has no entry in
`by_currency` (no activity at all), show all values as zero rather
than erroring.

### 5. "Расходы по дням неделе" (weekday bar chart)

From the same `summary` response, `day_of_week_expense[selectedCurrency]`
— an array of 7 integers, index 0 = Monday (matches Python
`datetime.weekday()`, already verified against `history_analytics.py`)
through index 6 = Sunday. Render as a full-width bar chart, single
series, red, x-axis labeled Пн–Вс. If the currency key is missing from
`day_of_week_expense` (no expenses that currency/period), render all
7 bars at zero rather than erroring. Do **not** render
`day_of_week_income` anywhere on this page.

## Color assignment

Add a new shared module, `frontend/src/utils/chartColors.ts`, exporting
the fixed 8-color categorical palette (hex values below) and a helper
that maps a stable list of category IDs (in a caller-supplied order)
to color indices, cycling positions 1–8 and folding any category
beyond the 8th into a shared "Прочее" bucket color (index 8, gray).

```
1 blue    #2a78d6
2 orange  #eb6834
3 aqua    #1baf7a
4 yellow  #eda100
5 magenta #e87ba4
6 green   #008300
7 violet  #4a3aa7
8 red     #e34948
```

**Stable order**: color is assigned by **category creation order in
the database**, never by amount, and never recalculated per period —
the same category must always render in the same color across every
period/currency selection. Since `expenses-by-category` and
`income-by-category` return entries sorted by amount (descending, see
`history_analytics.py`), the frontend must independently fetch the
canonical category list (check the existing categories endpoint in
`categories.py` / `frontend/src/api/*` — do not assume its response
shape or order, read the actual code first) to build a stable
`category_id → color index` map, then apply that map to the
amount-sorted analytics responses. Confirm with a quick manual check
that the categories endpoint returns categories in creation order
(e.g. ordered by primary key or `created_at` ascending) before relying
on array index as the order signal — if it does not, sort by whatever
field the model exposes for creation order, do not guess.

## Acceptance criteria (Part 1)

- [x] `recharts` installed and building cleanly.
- [x] `/analytics` renders the new screen inside the existing lazy
      `AnalyticsRoute`/`Suspense` boundary (Network tab still shows the
      analytics chunk loading separately from the main bundle).
- [x] Period filter (Месяц/Диапазон tabs) and currency toggle
      (UZS/USD) both work and drive all charts below.
- [x] "Расходы по категориям" donut renders correct data for the
      selected period/currency, with an empty-state when there is no
      data.
- [x] "Доходы по категориям" donut appears only when ≥3 income
      categories have nonzero amounts in the period/currency; hidden
      otherwise.
- [x] "Доход и расход по месяцам" always shows the last 12 months
      regardless of the period filter, correctly filtered to the
      selected currency, with all 12 months present even when some are
      zero.
- [x] Сводка за месяц card shows Доход/Расход/Переводы
      (нетто)/Итоговое изменение/Средний расход в день for the
      selected currency, zeroed gracefully when there's no activity.
- [x] "Расходы по дням недели" renders full width, Пн–Вс, correct
      values; "Доходы по дням недели" is not rendered anywhere.
- [x] Category colors are stable across period/currency changes (same
      category always same color), assigned by DB creation order, not
      by amount rank; categories beyond the 8th share a single
      "Прочее" color.
- [x] No TypeScript / build errors; `npm run lint` and `npm run build`
      pass.

## Verification (Part 1)

Manual, in browser, step by step:

1. Load `/analytics` with the default Month tab on a month with mixed
   expense categories — confirm donut renders, percentages roughly
   match manual expectation from seeded data.
2. Switch to a month/period with fewer than 3 income categories —
   confirm "Доходы по категориям" card is absent. Switch to a period
   with ≥3 — confirm it appears.
3. Switch currency UZS ↔ USD — confirm every chart on the page
   refetches/updates, including the trend chart (client-side filtered)
   and the weekday chart.
4. Switch to Диапазон tab, pick a custom range — confirm category
   donuts and summary update, but the 12-month trend chart does **not**
   change.
5. Pick a period/currency with zero activity — confirm each chart
   shows its empty/zero state instead of erroring or rendering a
   broken chart.
6. Confirm the same category keeps the same color across at least two
   different periods where its rank-by-amount would differ.
7. Confirm "Расходы по дням недели" spans the full card width and
   "Доходы по дням недели" is not present anywhere on the page.
8. Open Network tab, hard-reload the app at `/` — confirm the
   analytics JS chunk is not loaded until navigating to `/analytics`.
9. Stop the backend, reload `/analytics` — confirm inline error +
   retry per chart/section (not a full-page crash); restart backend,
   retry — confirm all sections recover.

## Part 2 — Subcategory drill-down

Depends on: Part 1 (this same file, already implemented and verified —
do not modify its code except to reuse existing patterns/components).
No backend changes — everything below is covered by the existing
`GET /api/v1/analytics/expenses-by-subcategory?parent_category_id&currency&date_from&date_to`
endpoint (`analytics.py` / `history_analytics.py`, unchanged).

### Goal

Make the "Расходы по категориям" donut card on the main Analytics
screen tappable, opening a two-level drill-down:

- **Level 2** — a list of cards, one per parent expense category that
  has a nonzero amount in the currently selected period/currency (same
  set of categories the main donut renders), **ordered by amount
  descending** — same principle as the main donut's underlying data
  order (the backend already returns `expenses-by-category` sorted by
  amount, see Part 1). The "Прочее" card (see below) is positioned in
  this same amount-sorted order using its own combined total, exactly
  like any other card — it is not pinned to the end. **Important:
  sort order is purely about screen position and is independent from
  color** — each category's color stays fixed by DB creation order
  regardless of where it lands in the amount-sorted list (see
  "Colors" below). Each card shows its own small donut of that
  category's subcategories.
- **Level 3** — tapping a Level 2 card opens a plain text list (no
  chart) of that category's subcategories with amounts, sorted by
  amount descending.

### Period & currency

Level 2 and Level 3 screens **inherit** the period (Месяц/Диапазон)
and currency (UZS/USD) selected on the main Analytics screen — there
is no independent period/currency control on either drill-down screen.

**Implementation (confirmed with user)**: keep
`periodTab`/`selectedMonth`/`rangeFrom`/`rangeTo`/`currency` state
lifted in a shared parent component (e.g. an `AnalyticsLayout` wrapping
`/analytics/*` routes via `<Outlet/>`), which passes the resolved
period/currency down to whichever of the three screens is currently
rendered. Do **not** introduce a new Zustand store for this — this is
local React state in a shared wrapper, scoped only to the Analytics
screens, per the project's existing "Zustand only where needed"
convention.

### Routing

Add nested routes under the existing lazy `AnalyticsRoute`:
- `/analytics` — existing main screen (Part 1, unchanged)
- `/analytics/categories` — Level 2 (list of parent-category cards)
- `/analytics/categories/:categoryKey` — Level 3 (subcategory list for
  one parent category; `:categoryKey` is the category's UUID for the
  8 named categories, and a fixed literal such as `other` for the
  "Прочее" card)

Read `AppShell.tsx` first and follow whatever nested-route/layout
pattern is already established there — do not invent a different
structure if an existing convention fits.

### "Прочее" handling (confirmed with user)

Categories beyond the 8th (by creation order) that are folded into
"Прочее" on the main donut **do** get their own Level 2 card. Tapping
it shows a donut merging subcategories from **all** overflow parent
categories together. Because subcategories from different parents are
mixed, every subcategory in this specific card — both in the donut
legend and in its Level 3 text list — must be labeled with its parent
category name, e.g. `Спорт: Абонемент`, `Питомцы: Корм`. This labeling
applies **only** to the "Прочее" card; the 8 named-category cards show
subcategory names alone, exactly as in a normal card, since there is
no ambiguity there.

Fetching for the "Прочее" card: call
`expenses-by-subcategory?parent_category_id=...` once per overflow
parent category, merge the results client-side into one combined list
before building the donut/list.

### Data fetching

New fetch helper(s) in `frontend/src/api/analytics.ts`, following the
existing `apiGet` pattern:
`fetchExpensesBySubcategory(parentCategoryId, currency, dateFrom, dateTo) → SubcategoryAmount[]`.

Level 2 screen: for each of the (up to 9, including "Прочее") cards,
call this once (for "Прочее", multiple calls merged as described
above) to get the mini-donut data. Reuse `CategoryDonutChart` (Part 1
component) at a smaller size if practical, or a scoped-down variant —
check the existing component's props before deciding whether to reuse
directly or extend.

Level 3 screen: reuse the same fetched data already available from
Level 2 for that category (pass it down via route state / a shared
fetch, avoid an unnecessary duplicate network call when navigating
from Level 2 → Level 3 for the same category) — if this isn't
straightforward with the existing data-fetching pattern, a fresh fetch
on Level 3 is an acceptable fallback, but prefer reusing what Level 2
already has.

### Colors

Same fixed 8-color categorical palette (`chartColors.ts`), same
principle as parent categories: color assigned by **subcategory
creation order**, stable across periods, applied **independently per
parent card** (no global uniqueness needed between different parents'
donuts — e.g. color #1 can mean a different subcategory in the "Еда"
card than in the "Транспорт" card).

**Order vs. color — these are two separate things, do not conflate
them**: within any card's donut legend or Level 3 list, subcategories
are **positioned/sorted by amount descending** (consistent with the
rest of this project), but the **color** each subcategory gets is
assigned from a stable `subcategory_id → color index` map built from
DB creation order, independent of where that subcategory currently
ranks by amount. A subcategory must render in the same color in every
period, even though its position in the sorted list can move.

For the "Прочее" card specifically: build the stable color map by
concatenating subcategories in order of (overflow-parent creation
order, then subcategory creation order within that parent) — i.e.
process overflow parents in the order they'd appear after the 8th
slot, and within each, subcategories in their own creation order. This
color map is then applied to the amount-sorted, parent-labeled list
used for display.

### Empty / zero states

A parent category with zero expense in the selected period/currency
does not get a Level 2 card at all (matches main donut's existing
zero-filtering behavior — do not show a zero-value card). If, after
switching period/currency on the main screen and returning to a
drill-down screen, a category that had a card no longer has one,
handle this gracefully (e.g. redirect back to Level 2, or show a
"no data" state) rather than crashing — decide the simplest correct
behavior when implementing, consistent with existing `BlockError`/
empty-state patterns elsewhere in this project.

### Out of scope for Part 2

- No backend changes of any kind.
- No changes to Part 1's main Analytics screen behavior, only adding
  the tap affordance on the "Расходы по категориям" card to navigate
  to `/analytics/categories`.
- No independent period/currency controls on drill-down screens.
- No changes to "Доходы по категориям", trend, summary, or weekday
  cards — this task is scoped to the expense-category donut only.

## Acceptance criteria (Part 2)

- [x] "Расходы по категориям" card on `/analytics` is tappable and
      navigates to `/analytics/categories`.
- [x] `/analytics/categories` shows one card per parent expense
      category with nonzero amount in the current period/currency,
      ordered by amount descending (including the "Прочее" card in its
      natural amount-sorted position, not pinned to the end).
- [x] Each Level 2 card renders its own subcategory donut, colored
      per the stable per-parent color-by-creation-order rule.
- [x] Tapping a Level 2 card (named category) opens Level 3: a plain
      text list of subcategories with amounts, sorted descending,
      no parent-name prefix.
- [x] Tapping the "Прочее" Level 2 card opens Level 3 with
      subcategories from all overflow parents merged, each labeled
      `Родитель: Подкатегория`, sorted descending by amount.
- [x] Period (Месяц/Диапазон) and currency (UZS/USD) selected on
      `/analytics` are inherited by both drill-down screens without
      an independent control anywhere in the drill-down flow.
- [x] Switching period/currency on the main screen and re-entering
      drill-down reflects the new period/currency correctly.
- [x] No TypeScript / build errors; `npm run lint` and `npm run build`
      pass.

## Verification (Part 2)

Manual, in browser, step by step (to be run after implementation,
one step confirmed before moving to the next):

1. From `/analytics`, tap "Расходы по категориям" — confirm navigation
   to `/analytics/categories` with the same set of categories as the
   main donut, ordered by amount descending; "Прочее" present only if
   the main donut has an overflow slice in this period, positioned by
   its own amount rank rather than always last.
2. Tap a named-category card — confirm its subcategory donut looks
   correct and colors are stable if you navigate back and re-enter.
3. Tap through to Level 3 for that category — confirm plain list,
   sorted by amount descending, no parent-name prefix.
4. Tap the "Прочее" card (if present) — confirm its donut mixes
   subcategories from multiple parents; tap through to its Level 3 —
   confirm every row is labeled `Родитель: Подкатегория`.
5. On `/analytics`, change period or currency, then re-enter
   `/analytics/categories` — confirm the drill-down reflects the new
   period/currency without any separate selector on the drill-down
   screens themselves.
6. Pick a period/currency where a previously-visible category now has
   zero expense — confirm its card no longer appears at Level 2.

## Changelog

### 2026-07-20 — Part 1 implemented and verified

**Routing**: `/analytics` now renders the real `AnalyticsPage` inside
the existing lazy `AnalyticsRoute`/`Suspense` boundary; `AppShell.tsx`
itself was not changed.

**Period filter & currency toggle**: `PeriodFilterControls` +
`utils/periodFilter.ts`, reusing `HistoryPage`'s Месяц/Диапазон tab
pattern (month navigation, masked date-range inputs, validation).
UZS/USD `SegmentedControl` reuses the Home pattern. Both drive all
charts on the page.

**API layer** (`frontend/src/api/analytics.ts`): typed fetch helpers
for `expenses-by-category`, `income-by-category`, `trend`, `summary`;
reuses `fetchSummaryForRange` from `history.ts`. No backend changes.

**Color assignment** (`frontend/src/utils/chartColors.ts`): fixed
8-color categorical palette. Stable `category_id → color index` map
built from the existing `/api/v1/categories/expense` and
`/api/v1/categories/income` endpoints (parent categories, `created_at`
order), then applied to the amount-sorted `expenses-by-category` /
`income-by-category` responses — category color stays fixed across
periods regardless of amount rank.

**Five sections**:
- Расходы по категориям — donut + legend, empty state when no data.
- Доходы по категориям — donut, rendered only when the response has
  ≥3 categories with `amount > 0`; otherwise the card is absent.
- Доход и расход по месяцам — always the last 12 months
  (`GET /analytics/trend`, no date params), independent of the page's
  period filter by design; filtered client-side to the selected
  currency.
- Сводка за месяц — Доход/Расход/Переводы (нетто)/Итоговое
  изменение/Средний расход в день (`average_daily_expense`, used here
  for the first time in the project).
- Расходы по дням недели — full-width bar chart; Доходы по дням
  недели is not rendered anywhere.

**Y-axis fixes (found and resolved during Part 1 verification, before
closing the task, per project convention)**: large UZS amounts (7+
digits) were clipped on the trend and weekday charts' Y-axis due to
recharts' default left margin being too narrow for right-aligned tick
text. Fixed with a new `formatCompactAxisAmount` tick formatter
(three tiers — `млрд` ≥1B, `млн` ≥1M, `тыс` ≥1K, plain below 1000; one
decimal, comma separator), applied to both charts, plus increased
chart top margin (8 → 20) and `YAxis` width (56 → 64) so the topmost
tick is never clipped by the card edge. Tooltips unaffected — they
still show full precise amounts via `formatCurrency`.

**Dependencies**: `recharts` installed with `--legacy-peer-deps`
(expected React 19 peer conflict, same pattern as `@telegram-apps/telegram-ui`);
`react-is` added as a transitive dependency required by the Vite
production build.

**Verification**: `npm run lint` and `npm run build` pass; analytics
chunk confirmed lazy-loading separately from the main bundle (Network
tab, not present until navigating to `/analytics`). All 9 steps of
the Verification checklist manually confirmed in browser, including:
currency toggle refetches every chart; Диапазон tab updates
categories/summary but correctly leaves the trend chart unchanged;
zero-activity periods render empty/zero states without errors; only
Расходы по дням недели is present (full width), Доходы по дням недели
removed; per-section `BlockError`/retry confirmed for
currency-triggered refetches with the backend stopped (a full-page
reload instead hits the earlier, already-existing Task 07
auth-bootstrap network-error screen — expected, not a Part 1 concern,
same as noted in Task 11).

Part 2 (subcategory drill-down) not started.

### 2026-07-21 — Part 2 implemented (subcategory drill-down)

**Routing**: nested routes under the existing lazy `AnalyticsRoute` via
`analytics/*` in `AppShell.tsx` — `/analytics` (main), `/analytics/categories`
(Level 2), `/analytics/categories/:categoryKey` (Level 3, UUID or `other`).
`AnalyticsPage.tsx` is now a route table; screen logic lives under
`frontend/src/pages/analytics/`.

**Shared layout & state**: `AnalyticsLayout` + `AnalyticsContext` lift
`periodTab`/`selectedMonth`/`rangeFrom`/`rangeTo`/`currency` for all three
screens via `<Outlet/>`. Period/currency controls remain on the main screen
only; drill-down inherits the layout state without independent selectors.

**Main screen change (only Part 1 delta)**: the "Расходы по категориям"
card is tappable when it has data, navigating to `/analytics/categories`.
All other Part 1 sections unchanged.

**Level 2** (`AnalyticsCategoriesPage`): one compact card per parent expense
category with nonzero amount in the current period/currency, ordered by amount
descending (including "Прочее" in its natural rank). Each card fetches
subcategory data via `fetchExpensesBySubcategory` and renders a compact
`CategoryDonutChart`. Tapping a card opens Level 3.

**Level 3** (`AnalyticsCategoryDetailPage`): plain text list of subcategories
with amounts, sorted by amount descending. Reuses route state from Level 2
when available; otherwise refetches. Stale/missing categories (e.g. after
period/currency change) redirect to Level 2. "Прочее" rows labeled
`Родитель: Подкатегория`; named categories show subcategory name only.

**API & utilities**: `fetchExpensesBySubcategory` in `analytics.ts`;
`buildParentCategoryCards`, subcategory donut/list helpers in
`analyticsCharts.ts`; drill-down fetch/merge logic in `analyticsDrillDown.ts`.
"Прочее" merges subcategory responses from all overflow parent categories;
colors assigned by stable subcategory creation order (per-parent for named
cards; concatenated overflow-parent-then-subcategory order for "Прочее"),
independent of amount-sorted display order.

**Shared components**: `analyticsShared.tsx` (`useFetchBlock`, `BlockError`,
`AnalyticsCard` with optional tap); `CategoryDonutChart` gained a `compact`
size variant.

**i18n**: `analytics.categoriesTitle`, `backToAnalytics`, `backToCategories`
in `ru.json` / `uz.json`.

**Verification**: `npm run lint` and `npm run build` pass. Manual browser
Manually verified end-to-end on a real Telegram client (via Cloudflare Tunnel + BotFather Menu Button, not just browser) — confirmed working, including the "Прочее" overflow scenario with 10 parent expense categories.
