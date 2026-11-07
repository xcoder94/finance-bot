# Task 07 — Frontend: App Shell, Routing, Store, i18n

Depends on: Phase 0 (`00-local-env.md`); backend Tasks 01–06 (all done,
including the 2026-07-18 `GET /api/v1/me` fix — `role`, `family_budget_id`,
`language` now returned)
PRD reference: §4.1, §9, §3 (role visibility), §10 (frontend NFR — lazy-load
Analytics)

## Goal

Build the app shell only: routing skeleton, Zustand store structure, the
initData → `GET /api/v1/me` auth flow, i18n (ru/uz), TelegramUI base layout
with bottom navigation. Screen *content* for Home/Analytics/History is out
of scope (Tasks 08, 11, 10) — those routes get empty placeholder
components in this task, just enough to navigate to and confirm routing
works. Settings is a partial exception: it needs a **working** language
switcher in this task, since PRD §9 is explicitly in scope here.

Visual reference only (not to be copied 1:1 as vanilla JS): `docs/design/
Family Budget.html` — bottom tab bar Home/Analytics/History/Settings.

## Scope

### Routing (react-router-dom)

- Routes: `/` (Home), `/analytics`, `/history`, `/settings`.
- `/analytics` route component is lazy-loaded (`React.lazy` + `Suspense`)
  — PRD §10 explicitly calls this out as the heaviest screen.
- Unknown path → redirect to `/`.

### Zustand store structure

- `useAuthStore`:
  - `status`: `'loading' | 'ready' | 'error'`
  - `user`: `{ id, telegramId, familyBudgetId, role, firstName, username, language } | null`
  - `errorType`: `'unauthorized' | 'not_onboarded' | 'removed_from_family' | 'network' | null`
- No wallets/categories/transactions store yet — added in Task 08+ as each
  screen needs it. Don't pre-build empty slices for future tasks.

### Auth flow

1. On app mount, get the raw `initData` string via `@tma.js/sdk-react`.
2. Call `GET /api/v1/me` with header `Authorization: tma <initData>`.
3. Blocking splash screen until this call resolves (decided earlier in
   chat — not a background fetch).
4. `200` → populate `useAuthStore`, set i18next language from
   `user.language`, render shell.
5. `401` → error screen: "authentication failed" (shouldn't happen inside
   real Telegram; must not crash if it does).
6. `404` (`not_onboarded`) → error screen: "start the bot first",
   pointing the user back to the bot chat.
7. `403` (`removed_from_family`) → error screen: "you were removed from
   this family budget".
8. Network/5xx error → error screen with a retry button.
9. Build a small reusable helper (e.g. `getAuthHeader()`) that later
   tasks' API calls will reuse — initData is re-sent on every request,
   per Task 01's no-session-layer decision.

### TelegramUI base layout

- Bottom tab bar (TelegramUI `Tabbar` or closest equivalent) wired to
  `NavLink`, 4 tabs per the design reference.
- Header: app title only. Space for the "primary currency" toggle (PRD
  §4.1) is reserved but not built — that's Task 08.

### i18n (react-i18next)

- `ru.json`, `uz.json` — initial keys: nav labels, splash/error screen
  strings. Screens themselves have no translatable content yet (they're
  placeholders).
- Active language is set from `user.language` after `/me` resolves. Splash
  screen text itself: hardcode in Russian for now, or pick one fallback
  language before auth resolves — no user identity to base a guess on yet.

### Settings screen (placeholder, but with a working language switcher)

- Displays: family budget name is NOT available yet (no endpoint) — show
  role and first_name from the auth store as a placeholder confirmation
  that auth worked, plus the language switcher (ru/uz toggle).
- Switching language: updates `i18next` immediately, no backend
  persistence (see "Decided: language switcher is client-side-only"
  below).
- Everything else in PRD §4.7 (category/wallet/member management) — out of
  scope, Task 12.

## Decided: local dev auth (no real Telegram)

`mockTelegramEnv` is NOT used — its fake `hash` won't pass the backend's
real HMAC check. Instead:

- New dev-only file `frontend/src/dev/signInitData.ts`, gated behind
  `import.meta.env.DEV`, mirrors the signing algorithm from
  `backend/scripts/gen_test_initdata.py::build_init_data` in TypeScript
  (same steps as `01-auth-telegram.md`: sorted `data_check_string`,
  `HMAC-SHA256("WebAppData", BOT_TOKEN)` → secret, `HMAC-SHA256(secret,
  data_check_string)` → hash).
- Reads `BOT_TOKEN` from a frontend-local dev env var (e.g.
  `VITE_DEV_BOT_TOKEN` in `frontend/.env.development`, gitignored,
  **never committed, never bundled into a production build** — the
  `import.meta.env.DEV` gate plus Vite's dead-code elimination must
  guarantee this code path and the token are stripped from `npm run
  build` output).
- Produces a signed `initData` string for a hardcoded test `telegram_id`
  (111111, matching the backend's Owner test user; a constant nearby for
  222222/Member, commented, for manually testing Member-role behavior by
  swapping the value).
- The real auth flow (`@tma.js/sdk-react` raw launch params) is
  attempted first; if unavailable (i.e. not running inside Telegram) AND
  `import.meta.env.DEV`, fall back to `signInitData.ts`'s output instead.
  In production builds this fallback branch does not exist.

## Decided: language switcher is client-side-only for now

No `PATCH /api/v1/me` in this task. The Settings switcher updates
`i18next` + local Zustand state immediately; on page reload it resets to
whatever `user.language` comes back from `/me`. Persisting the choice to
the backend is deferred to Task 12 (full Settings screen) as its own
follow-up decision then.

## Out of scope for this task

- Home/Analytics/History screen content (Tasks 08, 11, 10)
- Any wallet/category/transaction data fetching
- Member management, invite links (Task 12/13)
- "Primary currency" toggle logic (Task 08)
- Family budget name/info display (no endpoint yet)

## Acceptance criteria

- [ ] `npm run dev` builds and runs without errors
- [ ] `signInitData.ts` produces a hash matching the backend's own
      validation for the same inputs (spot-checked against Task 01's
      published test vector — same bot token, same expected hash)
- [ ] Splash screen shown until `/me` resolves
- [ ] `200` → shell renders, all 4 routes reachable via tab bar
- [ ] `401`/`404`/`403`/network error → distinct correct error screen, no crash
- [ ] Tab navigation updates the URL and highlights the active tab
- [ ] `/analytics` route component is lazy-loaded (confirmed via Network tab / bundle split)
- [ ] Language switcher changes UI language immediately, resets on reload (no persistence)
- [ ] Unknown route redirects to `/`
- [ ] `npm run build` (production) contains no `VITE_DEV_BOT_TOKEN` value and no dev-signing code path (spot-check the built bundle)

## Verification

First frontend task — no Python script. Manual steps, with backend +
Postgres running locally:

1. `npm run dev`, open in a regular browser (not Telegram) — dev fallback
   auth kicks in automatically, should reach the shell as Owner (111111).
2. Confirm splash → shell, tab bar navigates all 4 routes, active tab
   highlights correctly, URL changes.
3. Switch language in Settings, confirm nav labels update immediately;
   reload the page, confirm it resets to the backend's stored `language`.
4. Temporarily break the dev-signing token (wrong `VITE_DEV_BOT_TOKEN`)
   → confirm 401 error screen, no crash.
5. Point the dev telegram_id at one with no `User` row → confirm 404
   error screen. Point it at a soft-deleted test user → confirm 403
   error screen.
6. Stop the backend server → confirm network error screen with working
   retry button.
7. `npm run build`, inspect output bundle — confirm no dev bot token or
   signing code present.

## Changelog

- **2026-07-18**: Task 07 implemented. Installed `react-router-dom`, `zustand`,
  `react-i18next`, `i18next`, `@telegram-apps/telegram-ui` (with
  `--legacy-peer-deps` — library peer-declares React 18, project uses React
  19). Vite dev proxy `/api` → `http://127.0.0.1:8000`; committed
  `frontend/.env.development.example` (`VITE_DEV_BOT_TOKEN=` placeholder);
  `frontend/.env.development` gitignored via root `.gitignore`.
- **Routing** (`AppShell.tsx`): `/`, `/analytics`, `/history`, `/settings`;
  unknown paths → redirect `/`. `AnalyticsPage` lazy-loaded via `React.lazy`
  + `Suspense` (separate production chunk `AnalyticsPage-*.js` confirmed).
  Home/History/Analytics are `PlaceholderPage` only; Settings is functional
  (see below).
- **Auth store** (`store/authStore.ts`): `useAuthStore` with `status`, `user`
  (`id`, `telegramId`, `familyBudgetId`, `role`, `firstName`, `username`,
  `language`), `errorType`; `setLocalLanguage` for client-side switcher.
- **Auth flow** (`hooks/useAuthBootstrap.ts`, `api/me.ts`, `api/authHeader.ts`):
  on mount, `useRawInitData()` from `@tma.js/sdk-react`; `GET /api/v1/me` with
  `Authorization: tma <initData>`; blocking splash until resolve; distinct
  error screens for 401 / 404 (`not_onboarded`) / 403 (`removed_from_family`) /
  network (with retry). Empty `rawInitData` → `errorType: 'unauthorized'`
  (no crash). `getAuthHeader()` + `setInitData()` exported for later tasks.
  i18n language set from `user.language` on success.
- **Dev signing** (`dev/signInitData.ts`): mirrors
  `backend/scripts/gen_test_initdata.py::build_init_data` / Task 01 algorithm
  (sorted `data_check_string`, `HMAC-SHA256("WebAppData", token)` → secret,
  `HMAC-SHA256(secret, data_check_string)` → hex hash) via Web Crypto
  `crypto.subtle`; reads `VITE_DEV_BOT_TOKEN`; default `telegram_id` 111111
  (Owner), exported `DEV_TELEGRAM_ID_MEMBER` (222222) for manual swap.
  Used by `dev/mockTelegramEnv.ts` (not called directly from auth bootstrap).
  Production build verified: no `buildDevInitData`, `AAHtestQueryId`, or
  `VITE_DEV_BOT_TOKEN` strings in `dist/`.
- **Dev Telegram env mock** (`dev/mockTelegramEnv.ts`): DEV-only; calls
  `mockTelegramEnv()` from `@tma.js/sdk-react` with signed `tgWebAppData`
  from `buildDevInitData()`, `tgWebAppThemeParams` (light palette default,
  exported `DEV_THEME_PARAMS_DARK` for local dark-mode testing), platform
  `tdesktop`, version `8`. Dynamically imported from `main.tsx` before React
  render (production path tree-shaken).
- **Theme binding** (`telegram/bindThemeParams.ts`, called from `main.tsx`):
  `init()` → `themeParams.mount()` → `themeParams.bindCssVars()` from
  `@tma.js/sdk-react` (re-exported from `@tma.js/sdk` singleton
  `themeParams`). Injects `--tg-theme-*` CSS variables on
  `document.documentElement` from real Telegram launch params or dev mock.
  `App.tsx` derives `<AppRoot appearance>` from `useSignal(themeParams.isDark)`
  (not OS `prefers-color-scheme` alone).
- **Layout** (`App.tsx`, `AppShell.tsx`): single `<AppRoot>` in `App.tsx`
  wrapping splash, error screens, and shell (TelegramUI components require it).
  Header with `app.title` + reserved right slot for future primary-currency
  toggle; bottom `Tabbar` with `NavLink`-wrapped `Tabbar.Item` (first-letter
  icon placeholders, not copied from design HTML). `AppShell.tsx` no longer
  owns `AppRoot`.
- **Settings** (`pages/SettingsPage.tsx`): shows authenticated `role` and
  `first_name`; `SegmentedControl` ru/uz switcher updates `i18next` +
  `useAuthStore.setLocalLanguage` immediately, no backend persistence.
- **i18n** (`i18n/index.ts`, `locales/ru.json`, `locales/uz.json`): nav
  labels, splash-adjacent auth error strings, placeholder/settings keys; splash
  loading text hardcoded Russian (`SplashScreen.tsx`).
- **2026-07-18 (manual verification fixes)**:
  - **`LaunchParamsRetrieveError` in local dev**: `useRawInitData()` throws
    during render when launch params are absent (outside Telegram), before auth
    try/catch runs. Fixed by `dev/mockTelegramEnv.ts` + dynamic import in
    `main.tsx` before React render; removed direct `buildDevInitData()` fallback
    from `useAuthBootstrap.ts`.
  - **`[TGUI] Wrap your app with <AppRoot>` on splash/error screens**: moved
    `<AppRoot>` from `AppShell.tsx` to `App.tsx` so splash and auth error
    screens (which use TelegramUI `Spinner` / `Placeholder`) are inside a
    single root instance.
  - **Invisible auth error text (Placeholder header)**: root cause was missing
    `--tg-theme-*` CSS variable binding — `tgWebAppThemeParams` in the dev mock
    alone does not populate DOM vars; TelegramUI `--tgui--text_color` fell back
    to white when AppRoot detected OS dark mode without bound theme params.
    Interim hardcode (`appearance="light"`, `color-scheme: light`) replaced by
    proper SDK theme binding (`init` / `themeParams.mount` /
    `themeParams.bindCssVars`) plus dynamic `AppRoot` appearance from
    `themeParams.isDark`; `:root { color-scheme: light dark }` restored.

- **2026-07-22 (Addendum — remove app-shell header)**: removed the shared
  `app-shell__header` bar from `AppShell.tsx` on all routes (previously
  hidden on `/` only; now absent everywhere so Analytics/History/Settings
  match Home — page content starts directly below Telegram's native bar).
  Removed unused `Title` import, `useLocation`, and `isHome`. Removed
  top-level `app.title` / `app` object from `ru.json` and `uz.json`.
  Removed `.app-shell__header` and `.app-shell__header-slot` from
  `index.css`. Tabbar and in-page headings (e.g. Analytics title) unchanged.
    
## Addendum — Remove app-shell header on all pages (2026-07-22)

Decision: the shared `app-shell__header` bar (showing `app.title`,
"Семейный бюджет"/"Oila byudjeti") is removed from every page, matching
the behavior Home already has (Task 09 already hides this header on
`/` and shows its own in-content title instead). Analytics/History/
Settings will now look like Home does today: no top stripe, page's own
heading directly below Telegram's native bar.

**Change in `frontend/src/components/AppShell.tsx`:** remove the
entire conditional block:
```jsx
{!isHome ? (
  <header className="app-shell__header">
    <Title level="2" weight="2">
      {t('app.title')}
    </Title>
    <div className="app-shell__header-slot" aria-hidden="true" />
  </header>
) : null}
```
The now-unused `isHome` variable and `Title` import should be removed
too if nothing else in the file uses them — check before deleting.

**i18n:** remove the `app.title` key from `ru.json` and `uz.json`
(top-level `app` object — remove the whole object if `title` was its
only key).

**CSS:** remove `.app-shell__header` / `.app-shell__header-slot` rules
from `index.css` if they're not referenced anywhere else.

**Out of scope:** any change to the Tabbar, to individual page
headings (e.g. "Аналитика" stays exactly as-is — it's a separate,
in-page element, not part of this shared header).