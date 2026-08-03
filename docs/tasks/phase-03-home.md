# Phase 3 — Mini app Home

PRD: §17.1 (bottom menu), §17.2 (Home). Display rules from §5 as they appear
on Home (currencies never summed, Tashkent month boundary, green/red only for
income/expense).
Depends on: Phase 0 (application pass), Phase 1–2 (operations exist to show).
Plan: written after this spec is approved — not in this file.
Design: `docs/design/Chontak MVP2.dc.html` — Home screen must match one to one.

---

## 1. User goal

A person opens the mini app and on Home sees the family budget name, the month,
shared income/expense/balance, and recent operations — the same money the bot
just recorded.

---

## 2. Acceptance steps I will do by hand

1. Bottom menu has exactly four items: `Главная` · `Аналитика` · `Цели` ·
   `Настройки`. No fifth item, no floating `+`, no centre action button.
2. Home heading is the **budget name**, not «Мои финансы».
3. Top to bottom order matches design and §17.2: budget name, month switch,
   currency switch UZS/USD, three figures (`Доход`, `Расход`, `Остаток`), three
   action buttons (`Доход`, `Расход`, `Перевод`), recent operations block.
4. Record 100 000 UZS and 10 USD expenses in the same month. On Home, figures
   for UZS and USD are separate; switching currency never converts or sums them.
5. After a Phase 1/2 bot record, recent operations show it without reopening
   the app from scratch (pass still valid).
6. Empty month / loading skeleton states match the design (mandatory states).
7. Light and dark Telegram themes: Home follows; no hard-coded light-only
   colours (§5).

**Not blocking this phase:** `Мои личные` block (§11) — Phase 7. Until then
Home shows shared figures only (already correct per §11 for the top block).

**Not blocking:** full History/forms behaviour is Phase 4. In Phase 3 the three
action buttons and the recent-ops heading are on screen per design; they may
keep working MVP 1 handlers only where those still match this PRD. Anything
that does not match is left unwired and listed under finish-later — do not
invent MVP 2 form behaviour here.

---

## 3. What is NOT in this phase

- History screen and forms (§17.3, §17.7) — Phase 4
- Analytics (§17.4–§17.5) — Phase 5
- Settings redesign (§17.6) — Phases 6 / 9 / 11
- Personal wallets / `Мои личные` (§11) — Phase 7
- Goals content (§12) — Phase 8 (menu item may exist but Goals screen content
  is out of scope here)
- Members, notifications, bot chrome, voice, photo, prompt caching
- Currency conversion of any kind
- Uzbek translations

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Bottom menu | Exactly four labels from §17.1. No History tab. No floating `+`. |
| 2 | Home heading | Budget name. |
| 3 | Top figures | Shared wallets only (`Доход`, `Расход`, `Остаток`). Identical for every member. |
| 4 | Currency switch | Filter, never conversion. UZS wallets only vs USD wallets only. |
| 5 | Transfer/exchange colour in recent list | Neutral, no minus (§5). |
| 6 | Design fidelity | One-to-one with design file for Home and its empty/loading states. |
| 7 | Approved PRD↔design deviation | None on Home. (UZS/USD on Analytics Графики is Phase 5.) |
| 8 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Frontend checks / tests: menu has four items; Home renders budget name;
   currency switch does not convert amounts (fixture with UZS+USD ops).
2. Shared-only totals: personal-flagged ops (if DB flag exists from Phase 1)
   do not enter top figures — or document that personal wallets are not
   creatable until Phase 7 and shared-only is vacuously true.
3. Visual pass against design screenshots/chips for Home empty and filled.
4. Report before/after test output; list stubs.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Phases 0–2 on branch | team |
| `MINI_APP_URL` + real Telegram client | customer |
| Onboarded family with shared wallets and a few ops | team / bot |
| Design file openable in browser | repo |

---

## 7. When you must stop and ask me

- PRD and design disagree on Home layout or copy.
- Adding a fifth menu item, History tab, or floating `+`.
- Showing converted or summed multi-currency totals.
- Building `Мои личные` early «while we are here».
- Inventing MVP 2 form/History behaviour inside this phase.
- Confidence below average — say «not sure».
