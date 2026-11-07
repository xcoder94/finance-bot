# Task 17 — Frontend UX/UI Audit Fixes

Depends on: Task 14 (`14-frontend-settings.md` — done), Task 16
(`16-backend-optimization.md` — done, backend, no direct dependency
but immediately preceding in sequence).

Audit source: `docs/tasks/task17-original-audit-gpt56sol.md`
(GPT-5.6 Sol, 2026-07-23; 19 findings + 5 incidental functional bugs,
full report — read completely before starting any part of this task).

PRD reference: general UI/UX quality (§7 if present), no specific
section — this task does not add product scope, it improves the
existing screens.

## Goal

Fix the findings from the frontend audit: navigation, visual
consistency, category hierarchy, currency-control sizing, light
performance work, and the 5 functional bugs the audit surfaced
incidentally. This is **not** a new-feature task — every screen's
underlying data/logic stays the same unless a finding explicitly
describes broken behavior (the 5 bugs).

## Decisions made in the architecture-discussion chat (binding for all 3 parts)

- **Icon library**: add `lucide-react` as a new npm dependency.
  Replaces the Unicode-emoji Tabbar first-letter placeholders (Task 07/
  14 decision, now superseded) and the emoji category icons (Task 14
  decision, now superseded).
- **Navigation**: wire Telegram's native `BackButton`
  (`@tma.js/sdk-react`) so it appears on every screen that is not one
  of the 4 root tabs (Главная/Аналитика/История/Настройки) — this
  includes add/edit transaction forms, Analytics drill-down pages, and
  the transaction-detail bottom-sheet modal. `BackButton` must close an
  open modal first before navigating to the previous route (standard
  "top-most overlay first" behavior). Existing in-content manual back
  links (e.g. "‹ Мои финансы", "← Аналитика") are removed once
  `BackButton` covers the same screens — do not leave both.
- **Performance**: light-touch only.
  - IN scope: make independent Analytics sections
    (`AnalyticsMainPage`) paint as their own requests resolve instead
    of gating everything behind the category-metadata fetch; reuse/
    cache reference data (wallets, categories) and recently-fetched
    results (Home summary, transaction detail) across nearby route
    transitions instead of always refetching on remount.
  - OUT of scope: restructuring the main-entry bundle boundary, adding
    route-level code-splitting beyond the existing Analytics chunk,
    any bundler config changes. Findings #4 and #9 are addressed only
    to the extent covered by the caching/progressive-render work above
    — do not attempt a full fix.
- **Colors**: hybrid token strategy.
  - Pull from Telegram `themeParams` wherever a matching semantic
    value exists (backgrounds, primary/secondary text, destructive
    actions via `destructive_text_color`, buttons).
  - Telegram has no native concept of "income green" / "expense red" /
    "transfer neutral" / chart palette — define explicit CSS custom
    properties for these, with distinct light-theme and dark-theme
    values (not one fixed hex reused everywhere), checked for
    reasonable contrast against both `AppRoot` appearances.
  - The fixed 8-color category palette (Task 12 decision) keeps its
    category→color assignment; only re-tune the actual hex values if
    needed for dark-theme contrast, do not change the assignment
    logic.

## Scope — delivered as 3 separate Cursor prompts within this file

### Part 1 — Navigation, icons, color tokens, Analytics progressive render (High impact)

- Audit finding #1 — BackButton integration (see decision above for
  exact behavior, including the edit-flow stale-form issue described
  in the finding: after a successful edit, do not leave a route the
  user can navigate back into).
- Audit findings #2 and #15 — adopt `lucide-react`; replace Tabbar
  placeholder icons and category emoji.
- Audit finding #2 — theme-aware color tokens (hybrid strategy above).
- Audit finding #3 — Analytics progressive rendering: remove the
  shared category-metadata gate; each card/section shows its own
  result as soon as its own request resolves; avoid full remount/
  flicker on filter changes where reasonably achievable without a
  deeper rewrite.

### Part 2 — Hierarchy, control sizing, caching, layout, functional bugs (Medium impact)

- Audit finding #7 — strengthen parent/subcategory visual hierarchy in
  Settings (now easier with `lucide-react` icons available).
- Audit finding #6 — define one sizing convention for
  currency/period/language controls and apply it consistently (Home,
  Analytics, History, Settings currently disagree).
- Audit finding #8 — apply the caching/reuse approach from the
  performance decision above to the specific repeated-fetch cases
  listed in the finding (Home on tab return, Settings triple-fetch,
  add/edit reference data, History row → edit double-fetch).
- Audit finding #5 — align bottom scroll clearance with the real
  Tabbar footprint and Telegram viewport/safe-area signals instead of
  the fixed `72px` assumption.
- Audit finding #14 — give Settings the same page-title hierarchy as
  Home/History/Analytics.
- Bug #10 — add/edit forms must reset at the time specified in Task 10
  (immediately on success), regardless of which post-success action
  the user picks.
- Bug #11 — give the automatic "Общее" subcategory-creation fallback a
  recoverable failure state; keep it hidden from the user per Task
  10's original spec when it succeeds.

### Part 3 — Localization, accessibility, metadata, stale data (Low impact)

- Bug #13 — localize Settings role labels (`owner`/`member`) and
  Analytics compact-number chart units (currently hardcoded `ru-RU`).
- Audit finding #17 — add `:focus-visible` styles and appropriate
  `aria-live`/alert roles for loading/error transitions across the
  shared patterns.
- Audit finding #18 — set `lang` dynamically to match the active
  language; review viewport/safe-area meta coverage.
- Bug #19 — decide TransactionDetailModal's role (lightweight preview
  vs authoritative detail) and make its displayed data consistent with
  that choice; surface cross-currency destination amount if the
  authoritative-view option is chosen.
- Bug #16 — make paste and programmatic input follow the same
  10-digit limit/error behavior as keyboard entry in `LimitedDigitInput`.

## Explicitly out of scope for all 3 parts

- Any backend change.
- Member management UI (Task 15 — still cancelled/deferred to v2).
- Deep bundle-splitting rework (see Performance decision above).
- Any new feature or screen not already in the product.
- Changing the fixed category-to-color assignment order (Task 12).

## Verification

Frontend task — no Python verification script. Manual verification in
the real Telegram client (mobile and, where relevant to a specific
finding, desktop), step by step, with screenshots per point, per
established project convention. Each part gets its own verification
pass before moving to the next part.

## Changelog

- **2026-07-23 — Part 1 implemented:**
  - Installed `lucide-react`; replaced language-dependent Tabbar
    placeholders with stable Home/Analytics/History/Settings icons and
    replaced Settings income/expense category emoji with multilingual
    keyword-to-Lucide mappings plus a generic folder fallback.
  - Integrated `@tma.js/sdk-react` `backButton` for every non-root route
    and transaction-detail overlays. Overlay back closes the modal
    before route navigation; root tabs hide the native control. Removed
    the covered in-content back links and changed all successful edit
    saves to replace the edit route with `/history`.
  - Added separate light/dark semantic, chart-chrome, category-palette,
    and elevation tokens. Telegram theme variables remain the source for
    matching platform semantics; delete confirmations now consistently
    use destructive text on a neutral button surface. Recharts grid,
    axes, tooltip, legend, cursor, and series colors now follow the
    active appearance. The fixed category-color assignment order is
    unchanged.
  - Removed the Analytics-wide category-metadata render gate. Donuts
    wait only for their own data plus metadata, while trend, summary,
    and weekday cards render independently. Successful card data remains
    visible during filter refetches to avoid blank chart remounts.
  - Automated verification: `npm run build` passes; `npm run lint`
    passes with the two pre-existing Fast Refresh warnings in
    `analyticsShared.tsx` and `AnalyticsContext.tsx`. Real-Telegram
    light/dark, BackButton, progressive-load, RU/UZ, and screenshot
    verification remains pending.
- **2026-07-23 — Part 2 implemented:**
  - Strengthened the Settings expense hierarchy with a larger child
    indent, connector line, muted smaller child icons and labels,
    stronger parent labels, and wider separation between parent groups.
    Standardized currency, period, and language segmented controls on a
    centered compact/content-width convention across Home, Analytics,
    History, and Settings.
  - Added a lightweight family-keyed Zustand memory cache with request
    deduplication: Home results use a 30-second freshness window,
    wallets/categories use 5 minutes, and transaction details use 2
    minutes. Home, Settings, Analytics metadata, add/edit forms, and the
    History detail-to-edit flow reuse fresh data. Relevant transaction,
    wallet, and category mutations invalidate or update affected cache
    entries.
  - Replaced the fixed 72 px bottom-clearance estimate with the measured
    rendered Tabbar height. The shell also mounts Telegram's viewport,
    consumes safe/content-safe-area signals, binds reported viewport
    dimensions, and falls back to browser safe-area/viewport values.
    Added a Settings level-one page title and removed its duplicated
    Settings section caption.
  - All three add forms now reset immediately after a successful create,
    before opening the success modal, and invalidate Home data. The
    implicit expense “Общее” fallback stays hidden, now reports a
    localized recoverable error and offers Retry if creation fails.
  - No scope deviations or backend changes. Automated verification:
    `npm run build` passes; `npm run lint` passes with the same two
    pre-existing Fast Refresh warnings. Real-Telegram mobile/desktop
    verification and requested screenshots remain pending.
- **2026-07-23 — Part 3 implemented:**
  - Localized Owner/Member role labels and compact Analytics axis units
    in Russian and Uzbek; number formatting now follows the active
    locale. The document defaults to Russian, synchronizes its `lang`
    attribute on every language change, and opts the viewport into full
    safe-area coverage with `viewport-fit=cover`.
  - Added visible keyboard focus indicators for custom buttons, links,
    clickable cards, and transaction rows. Primary shared loading states
    now expose polite status regions with localized text, while shared
    load, submit, delete, and inline validation failures use alert
    semantics across Home, History, Analytics, Settings, and transaction
    forms.
  - Made transaction detail authoritative: each open forces a fresh
    transaction fetch, resolves its current wallet/category/author IDs
    through existing reference APIs, replaces the immediate list-item
    preview when ready, ignores superseded requests, and displays the
    destination amount for cross-currency transfers. Because the
    existing detail response intentionally contains IDs rather than
    display names, cached reference data is used for current labels and
    the list snapshot is retained only as a fallback for soft-deleted
    referenced records; no backend change was needed.
  - Fixed `LimitedDigitInput` so paste and generic input changes inspect
    the unsliced digit string, reject values over 10 digits without
    changing the accepted value, and show the same localized accessible
    error as keyboard entry.
  - No out-of-scope or backend changes. Automated verification:
    `npm run build` passes; `npm run lint` passes with the same two
    pre-existing Fast Refresh warnings. Real-Telegram accessibility,
    RU/UZ, cross-currency detail, paste, and screenshot verification
    remains pending.
