# Phase 7 — Personal wallets

PRD: §11 (and Home consequence for `Мои личные`; shared top figures remain
shared-only).
Depends on: Phase 3 (Home), Phase 6 (wallets settings surface).
Plan: written after this spec is approved — not in this file.
Design: Home with `Мои личные` and wallets settings personal section.

---

## 1. User goal

A person creates personal wallets only they can see; their personal spending
stays out of shared Home figures and analytics, and a `Мои личные` block on
Home shows their own totals when they have a personal wallet in the selected
currency.

---

## 2. Acceptance steps I will do by hand

1. As member A, create a personal wallet and record an expense on it.
2. As the owner (different person): Home, analytics, History, wallet list,
   settings — A's personal wallet and its operation appear in **none**.
3. As A: `Мои личные` appears on Home; its figures include that expense; top
   shared block does not.
4. Delete every operation on the personal wallet but keep the wallet — block
   still shown.
5. Delete the personal wallet — block disappears.
6. Only UZS personal wallet; switch Home to USD — `Мои личные` disappears
   (does not show empty/zero under USD).
7. Both Home blocks carry headings and are visually distinguishable.
8. Personal wallet limit 5: create button stays enabled; at limit → exact
   §19.1 personal-wallets text.
9. Quick entry: writer's personal wallets may be used; another member's
   personal names never appear in the parse wallet list (Phase 1 rule still
   holds).

---

## 3. What is NOT in this phase

- Goals (§12), members join conversion (§13) — later
- Change log (§14)
- Notifications (§16)
- Bot chrome, voice, photo, caching
- Putting personal spend into shared analytics «as an option»
- Personal goals (forbidden — §21)
- Uzbek translations

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Visibility | Personal wallet invisible to everyone except holder, **including owner**. |
| 2 | Analytics / digest / shared Home top | Personal ops never included. |
| 3 | `Мои личные` | Shown iff ≥1 personal wallet **in selected currency**; figures for that currency only; headings required on both blocks. |
| 4 | Who creates | Each member creates own personal; only owner creates shared. |
| 5 | Limit | 5 personal per person; §19.1 text exact. |
| 6 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. API tests: member B cannot read A's personal wallet/ops; aggregates exclude
   personal; Home personal block visibility rules by currency.
2. Limit message test for personal wallets.
3. Parse wallet-visibility regression from Phase 1.
4. Report before/after; list stubs.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Two Telegram accounts in one family (owner + member) | customer |
| Phase 6 wallets settings | team |
| Design for `Мои личные` | repo |

---

## 7. When you must stop and ask me

- Showing personal data to the owner «for support».
- Omitting headings on the two Home blocks.
- Including personal spend in shared analytics.
- Confidence below average — say «not sure».
