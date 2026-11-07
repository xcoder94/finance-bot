# Frontend UI/UX and performance audit — GPT-5.6 Sol, 2026-07-23

Original audit findings, produced before any Task 17 implementation.
The audit covered every file under `frontend/src`, the production bundle
shape, the product requirements, roadmap, frontend task decisions, and
project rules. Member-management actions are intentionally deferred to
v2 and are not treated as missing functionality.

## Known-issue conclusions

1. **Settings appears cut off on Telegram Desktop:** refuted as a
   Settings-specific clipping defect. The page has no fixed/capped
   height or `overflow: hidden`; `min-height: 100svh` permits the
   document to grow and scroll. Settings differs from the other tabs
   only by being much longer. Bottom clearance is nevertheless brittle:
   it assumes a 72 px Tabbar and uses only the browser safe-area
   environment value, not Telegram viewport/content-safe-area data.
2. **Tabbar has no icons:** confirmed. The first translated letter is
   intentionally rendered as the icon placeholder. This is design debt,
   not an accidental implementation bug.
3. **UZS/USD control is too large:** confirmed as a visual/polish
   problem. Home and Analytics deliberately force it to full width;
   History uses the same full-width treatment for period tabs, while
   Settings does not force its language control to that width.
4. **Palette is weak in light and dark themes:** confirmed. Telegram
   theme binding is present and correct at the root, but many semantic
   and chart colors remain fixed hex values. Category-chart colors were
   an intentional Task 12 decision, but they still need cross-theme
   contrast review.
5. **Category hierarchy is weak:** confirmed. Subcategories differ from
   parent categories only by 24 px indentation; the current source does
   not contain the reported `↓` prefix, weight change, size change, or
   other persistent hierarchy cue.
6. **iOS native swipe-back does not work:** confirmed at the application
   integration level. The router is not connected to Telegram's
   `BackButton`, and no swipe-behavior API is used. Telegram's
   swipe-behavior API governs host vertical gestures rather than
   horizontal route history, so it would not replace BackButton/router
   integration.
7. **Screens feel 1–3 seconds slow:** confirmed as a credible cumulative
   frontend problem. The main contributors are blocking authentication,
   large route bundles, uncached route-level refetching, Analytics render
   gating, Recharts initialization, request fan-out, and spinner-only
   transitions. Main-screen requests are generally parallel rather than
   serial, so a simple API waterfall is not the sole cause.

## High impact

### 1. Bug — Telegram-native back navigation is not integrated

Where:
- `frontend/src/components/AppShell.tsx`
- `frontend/src/components/transaction-form/TransactionFormShared.tsx`
- `frontend/src/pages/analytics/AnalyticsCategoriesPage.tsx`
- `frontend/src/pages/analytics/AnalyticsCategoryDetailPage.tsx`
- all `frontend/src` SDK integration

There is no use of Telegram `BackButton`, route-aware back handling, or
swipe-behavior control anywhere in the source. Add/edit forms and
Analytics drill-down pages expose only custom in-page buttons that push
fixed destinations through `BrowserRouter`. Consequently, Telegram's
native header cannot reflect the internal route stack, and the observed
iOS edge-swipe behavior has no application-level integration to fall
back on.

The edit flow also pushes `/history` after saving instead of retiring
the edit entry. Browser back, where the host does expose it, can
therefore return to a stale edit form after a successful save.

Recommendation:
- Define one route-stack policy for root tabs, forms, drill-down pages,
  and modals, and connect it to Telegram's native back affordance.
- Ensure completed edit flows cannot return users to stale forms.

### 2. Visual/polish problem — semantic colors are only partially theme-aware

Where:
- `frontend/src/index.css`
- `frontend/src/components/analytics/TrendChart.tsx`
- `frontend/src/components/analytics/WeekdayBarChart.tsx`
- `frontend/src/utils/chartColors.ts`
- Home, History, Analytics, transaction forms, and delete confirmations

`themeParams.mount()` and `themeParams.bindCssVars()` correctly bind
Telegram theme values, and `AppRoot` correctly follows
`themeParams.isDark`. The screen backgrounds, primary text, muted text,
and many expense states consume those variables.

However, income uses fixed `#2e7d32`/`#43a047`, chart expense uses fixed
`#e53935`, transfer uses fixed `#78909c`, and the transaction submit
button uses fixed `#4db6ac`. Recharts grid, tooltip, and legend chrome
use library defaults. Card elevation is a light-theme-oriented fixed
black shadow. Delete confirmations also treat the Telegram destructive
text color inconsistently: as text in History and as a filled
background in Settings, without independently establishing readable
button text.

This creates inconsistent contrast and emphasis across arbitrary
Telegram light/dark palettes. The fixed eight-color category palette is
intentional per Task 12, but its theme suitability has not been
established by the implementation.

Recommendation:
- Establish and contrast-test theme-aware semantic tokens for positive,
  negative, neutral, destructive, chart chrome, and elevated surfaces.
- Reassess the intentional fixed chart palette against both Telegram
  appearances while preserving stable category-to-color identity.

### 3. Performance problem — first Analytics entry has a large blocking cost

Where:
- `frontend/src/components/AppShell.tsx` (`AnalyticsRoute`)
- `frontend/src/pages/AnalyticsPage.tsx`
- `frontend/src/pages/analytics/AnalyticsMainPage.tsx`
- `frontend/src/components/analytics/*`
- production bundles in `frontend/dist/assets`

Analytics is route-lazy as required, but all Analytics subpages and all
Recharts components are statically included behind that single
boundary. The measured production Analytics chunk is about 402 KB raw
(114 KB gzip). The main entry is about 495 KB raw (147 KB gzip).

After the chunk loads, `AnalyticsMainPage` starts its requests in
parallel, which is good, but it withholds every card until the category
metadata request succeeds. Trend and summary therefore remain hidden
even when their independent requests have finished. Once the gate
opens, several Recharts SVG trees may initialize together. Filter
changes replace existing chart contents with spinners and remount the
charts, adding visible flicker and repeated main-thread work.

Recommendation:
- Make independent Analytics sections paint progressively instead of
  sharing the category-metadata gate.
- Review the Analytics bundle boundary and chart initialization strategy
  against real Telegram mobile hardware.
- Preserve useful prior content or geometry during refetches so network
  and chart work does not present as a blank transition.

### 4. Performance problem — Analytics drill-down multiplies and repeats requests

Where:
- `frontend/src/pages/analytics/AnalyticsCategoriesPage.tsx`
- `frontend/src/pages/analytics/AnalyticsCategoryDetailPage.tsx`
- `frontend/src/utils/analyticsDrillDown.ts`

Opening the category drill-down refetches expense categories and
top-level expense analytics already fetched on the main Analytics
screen. It then waits for one subcategory request per visible parent
card; the “Other” card can issue additional requests for every overflow
parent. All card data is awaited before any card renders. The detail
route repeats base fetches again even when route state already contains
the selected card's subcategory data.

This fan-out is bounded for the MVP but directly affects the transition
the user taps, and its all-or-nothing spinner amplifies the delay.

Recommendation:
- Reuse already-fetched Analytics metadata and results for the lifetime
  of the Analytics flow.
- Reduce or progressively expose the per-card request fan-out rather
  than blocking the whole drill-down on every response.

## Medium impact

### 5. UX problem — Settings overflow is expected, but viewport and Tabbar clearance are brittle

Where:
- `frontend/src/index.css` (`body`, `#root`, `.app-shell`,
  `.app-shell__main`)
- `frontend/src/components/AppShell.tsx`
- `frontend/src/pages/SettingsPage.tsx`

The source does not impose a fixed height on Settings or the shared
content area, so its long content should extend the document and use
normal scrolling. There is no Settings-only overflow rule and no
evidence that `100svh` itself clips the page: it is used as a minimum,
not a maximum.

The app does not mount or consume Telegram viewport, safe-area, or
content-safe-area signals, though. Bottom spacing is a fixed
`72px + env(safe-area-inset-bottom)` estimate rather than a value tied
to the rendered Tabbar and Telegram viewport. This can make the final
rows appear cut off or obscured in a host whose available content area
or Tabbar geometry differs from the assumption. Settings exposes the
risk first because it is the longest page.

Recommendation:
- Treat the symptom first as ordinary scrollable overflow and verify
  whether the last row remains reachable on Telegram Desktop.
- If content is actually obscured, align shared-shell scrolling and
  bottom clearance with Telegram's reported viewport/content-safe-area
  and the real Tabbar footprint.

### 6. Visual/polish problem — currency controls dominate their surrounding UI

Where:
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/analytics/AnalyticsMainPage.tsx`
- `frontend/src/index.css` (`.home-page__currency-toggle`)
- comparison: `HistoryPage` period control and `SettingsPage` language control

Home and Analytics wrap a two-option `SegmentedControl` and force its
internal root to `width: 100%`. The result is consistent between those
two screens, but visually much larger than the compact month arrows,
headings, and adjacent metrics. History also uses full-width segmented
period tabs, whereas the Settings language control is left at the
component's natural layout, so there is no single sizing convention by
control purpose.

Recommendation:
- Define a consistent sizing hierarchy for primary view modes, period
  modes, currency selection, and language selection, then reassess the
  full-width currency treatment in that system.

### 7. UX problem — expense parent/subcategory hierarchy is too weak

Where:
- `frontend/src/components/settings/ExpenseCategoriesSection.tsx`
  (`CategoryRow`)
- `frontend/src/index.css` (`.settings-expense-group`,
  `.settings-expense-subcategory`, `.settings-entity-icon`)

Parent and child rows use the same component, typography, emoji scale,
delete treatment, and row structure. A child receives only 24 px left
padding. Adjacent parent groups have only 4 px separation. The current
source contains no `↓` prefix, connector, disclosure state, or
font-weight distinction, so hierarchy becomes difficult to scan in a
long category list.

Recommendation:
- Strengthen persistent parent/child differentiation through hierarchy,
  typography, spacing, or icon treatment without changing the
  underlying two-level category model.

### 8. Performance problem — routine route transitions repeat uncached fetching

Where:
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/components/settings/WalletsSection.tsx`
- `frontend/src/components/settings/IncomeCategoriesSection.tsx`
- `frontend/src/components/settings/ExpenseCategoriesSection.tsx`
- `frontend/src/components/TransactionDetailModal.tsx`
- add/edit transaction pages

Home remounts and repeats summary, wallet-balance, and recent-history
requests whenever the user returns from another tab or form. Settings
starts three independent list requests on every mount. Add/edit pages
reload the same wallets and categories. Opening a History row fetches
the full transaction, then entering edit fetches that same transaction
again alongside reference data.

Most calls within each screen are correctly parallel, so the problem is
not serial code. It is repeated network latency with no cross-route
reuse, coupled with spinners that replace or precede content.

Recommendation:
- Define freshness and reuse rules for stable reference data, recent
  results, and transaction details across nearby route transitions.
- Keep independent blocks progressive and avoid making a repeated
  request the only visible response to a tap.

### 9. Performance problem — only Analytics is split from a large main bundle

Where:
- `frontend/src/components/AppShell.tsx`
- production main entry in `frontend/dist/assets`

Home, History, Settings, all add forms, all edit forms, and their shared
components are eagerly imported into the main entry. The measured main
entry is about 495 KB raw (147 KB gzip), before the 402 KB Analytics
chunk is requested. This shifts work away from later tab transitions
but increases cold-start download, parse, and execution before the
first useful screen.

Recommendation:
- Re-evaluate route-level bundle boundaries using cold-start and
  first-navigation measurements from Telegram mobile and desktop
  clients, not bundle size alone.

### 10. Bug — successful add forms do not clear fields at the documented time

Where:
- `frontend/src/pages/AddIncomePage.tsx`
- `frontend/src/pages/AddExpensePage.tsx`
- `frontend/src/pages/AddTransferPage.tsx`
- `frontend/src/components/transaction-form/TransactionFormShared.tsx`

Task 10 requires fields to clear immediately when creation succeeds,
before or as the success modal appears. All three pages only open the
modal on success. They call `resetForm()` later, and only when the user
chooses “Add another.” Choosing “Home” never clears the mounted form
before navigation.

The modal is non-dismissible, which limits exposure, but the
implementation still violates the accepted behavior and retains stale
submitted state behind the modal.

Recommendation:
- Make successful creation and form reset one consistent state
  transition regardless of which modal action the user chooses.

### 11. Bug — automatic expense-subcategory creation can fail without feedback

Where:
- `frontend/src/pages/AddExpensePage.tsx`
  (`ensureSubcategoryForParent`)

When a parent has no subcategories, the page automatically creates the
task-specified “Общее” child as soon as the parent is selected. If that
request fails, the catch path only clears `subcategoryId`. The form then
keeps the submit button disabled with no error or retry explanation.
The subcategory select is also always rendered and temporarily disabled,
although Task 10 explicitly described this fallback as hidden from the
user.

The Russian fallback name itself was explicitly required by Task 10 and
is therefore not classified here as an accidental i18n bug.

Recommendation:
- Give the implicit fallback operation a recoverable failure state and
  keep its UI behavior consistent with the documented hidden fallback.

### 12. UX problem — transaction loading failures remove all navigation

Where:
- `frontend/src/components/transaction-form/TransactionFormShared.tsx`
  (`TransactionFormLoadError`, `TransactionFormLoading`)
- all add/edit transaction pages

The normal form layout has a visible back action, but loading and
reference-data error states replace the entire layout. The error state
offers only “Retry.” If the backend continues failing, the user has no
in-app route back to Home or History and must depend on host/browser
navigation—which is itself not integrated with Telegram.

Recommendation:
- Preserve a reliable route-exit affordance across loading, error, and
  success states, consistent with the native-back policy.

### 13. UX problem — some shipped text bypasses the active language

Where:
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/utils/formatCurrency.ts`

Settings renders raw API roles (`owner`/`member`) instead of localized
labels. Analytics compact axis formatting always uses `ru-RU` and the
Russian suffixes `тыс`, `млн`, and `млрд`, so Uzbek users see Russian
chart units after selecting Uzbek.

Recommendation:
- Include role labels and compact-number units in the same locale policy
  as the rest of the visible UI.

### 14. UX problem — Settings lacks the page hierarchy used by other tabs

Where:
- `frontend/src/pages/SettingsPage.tsx`
- comparison: `HomePage`, `HistoryPage`, `AnalyticsMainPage`

Home, History, and Analytics render a level-one page title. Settings
starts with a TelegramUI `Section` whose header repeats the navigation
label, then displays raw role/name metadata. This makes “Settings” read
as a section caption rather than the current screen title and gives the
longest page the weakest top-level orientation.

Recommendation:
- Apply the established page-title hierarchy consistently while keeping
  the intentionally removed shared app header removed.

## Low impact

### 15. Visual/polish problem — Tabbar placeholders are language-dependent, non-semantic icons

Where: `frontend/src/components/AppShell.tsx` (`TabIcon`)

Each icon is `label.slice(0, 1)`, so it changes when the language
changes and conveys no stable visual meaning. This was explicitly
intentional in Tasks 07 and 14, and the absence of an icon dependency is
not a bug.

Recommendation:
- Revisit the “no icon dependency” constraint as a product tradeoff:
  semantic consistency and accessibility versus bundle/dependency cost
  and the maintenance cost of local assets. Establish one real icon
  system when that decision is made.

### 16. Bug — over-length pasted amounts are silently truncated

Where:
- `frontend/src/components/transaction-form/TransactionFormShared.tsx`
  (`LimitedDigitInput`)

Keyboard entry rejects an eleventh digit and sets an error state, but
paste and generic change handling slice input to ten digits before
checking its length. Their over-limit checks therefore cannot observe
the original excess input. Pasted values are silently shortened instead
of following the documented rejection/error behavior.

Recommendation:
- Make keyboard, paste, and mobile input paths communicate the same
  length-limit outcome.

### 17. UX problem — interactive and asynchronous states have accessibility gaps

Where:
- `frontend/src/index.css`
- loading/error components across Home, History, Analytics, Settings,
  and transaction forms

There are no application-defined `:focus-visible` styles, `aria-live`
regions, or alert roles. Custom month, card, back, and list-row buttons
therefore depend entirely on user-agent/component defaults for keyboard
focus, while spinner-to-content and inline-error transitions are not
announced by the application.

Recommendation:
- Include visible keyboard focus and screen-reader announcements in the
  shared interaction and loading/error patterns.

### 18. Visual/polish problem — document metadata does not match the Mini App

Where: `frontend/index.html`

The document remains `lang="en"` even though the UI is Russian or Uzbek,
and the active language is not reflected there. The viewport metadata
also omits full safe-area coverage, while the CSS assumes safe-area
environment values for bottom padding.

Recommendation:
- Align document language and viewport/safe-area metadata with the
  runtime language and Telegram host strategy.

### 19. UX problem — History detail fetch does not drive the displayed details

Where: `frontend/src/components/TransactionDetailModal.tsx`

The modal fetches the authoritative transaction before displaying
details, but nearly every visible value still comes from the older
History list item. The fetched record is used mainly for permission and
edit routing. If the record changed after the list loaded, the modal can
show stale values despite completing a fresh request; cross-currency
destination amount is also not surfaced.

Recommendation:
- Decide whether the modal is a lightweight list preview or an
  authoritative detail view, then align its request cost and displayed
  data with that role.

## Intentional decisions not classified as defects

- Member-management actions and rendered Members section are deferred
  to v2; their absence is not a bug.
- Unicode category emoji and first-letter Tabbar icons are documented
  placeholders.
- The shared app-title header was intentionally removed.
- Home's primary currency is local and affects only its summary.
- Analytics trend ignores the page period by design.
- The fixed category-to-color assignment and eight-color palette were
  explicit Task 12 decisions, though cross-theme contrast remains an
  audit concern.
- Splash authentication is intentionally blocking per Task 07. It is a
  measurable perceived-latency contributor, not an implementation
  deviation.
- UTC period boundaries and the temporary “Общее” expense fallback were
  explicitly required by their task files and are not reclassified here.
