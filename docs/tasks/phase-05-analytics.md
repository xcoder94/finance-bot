# Phase 5 — Analytics

PRD: §17.4, §17.5. Chart colours and «Другое» from §5. Soft-deleted category
appearance in analytics from §15.4 (display side).
Depends on: Phase 3 (shell/menu), Phase 4 (History screen to open from
drill-down).
Plan: written after this spec is approved — not in this file.
Design: Analytics screens in `docs/design/Chontak MVP2.dc.html` one to one,
**except** approved UZS/USD switch on `Графики` (PRD §17.4).

---

## 1. User goal

A person opens Analytics, switches period and currency on charts, drills from
parent to subcategory to filtered History, and reads the tiles and bars under
the donut — without any currency conversion.

---

## 2. Acceptance steps I will do by hand

1. Tabs named exactly `Графики` and `История`. Period filter shared; switching
   tabs does not reset period.
2. `Графики` has UZS/USD switch (approved deviation). Switching to USD recounts
   USD wallets only; no figure equals a UZS amount divided by a rate.
3. `История` lists every operation in its own currency regardless of the
   charts currency switch.
4. Tap a donut sector/legend: chart rebuilds to subcategories; heading = parent
   name + back; total under heading; shares sum to 100% inside the parent.
5. Tap a subcategory: `История` opens filtered by that subcategory and same
   period. Back → subcategory chart; filter cleared. Period never reset.
6. Tap «Другое» — nothing happens.
7. Blocks below donut, order fixed: `Доход и расход, 12 месяцев`; tiles
   `Средний расход в день` and `Самый дорогой день`; `Расход по дням недели`.
   Unit label `млн сум` / `$` per §17.5.
8. Page months: twelve-month block ends with the selected month. Quick paging
   then wait — figures match the month named at the top.
9. Empty month replaces the **whole** tab (donut + blocks together).
10. Personal spending (when Phase 7 exists) never enters analytics — until then
    confirm shared-only with fixtures.
11. Soft-deleted category with past ops still shows its own name and colour in
    analytics, no marker (§15.4) — if delete UI not yet in Phase 6, seed a
    soft-deleted category in DB for the check or defer the hand step until
    Phase 6 and list it under finish-later for this phase exit.

---

## 3. What is NOT in this phase

- Settings categories CRUD (§17.6 / §15.4 picker side) — Phase 6
- Personal wallets product (§11) beyond excluding personal ops from aggregates
- Goals, members, notifications, bot chrome, voice, photo, caching
- Converting UZS↔USD anywhere
- Prototype behaviour of dividing by a fixed rate
- Uzbek translations

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Tab names | `Графики` · `История` |
| 2 | Period filter | Shared by both tabs; never reset by tab switch or drill-down back. |
| 3 | Currency switch | On `Графики` only; filter not conversion; keep even though design omits it. |
| 4 | Ladder | Parent → subcategory → History filter. No third level. «Другое» does not expand. |
| 5 | Colours | Exactly 8 category colours; bound to category; overflow → «Другое» (§5). |
| 6 | Scope | Shared wallets only. |
| 7 | Empty state | Whole tab replaced, not donut alone. |
| 8 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Tests: period retained across tabs; currency filter isolates wallets; drill
   down navigation and filter clear; «Другое» no-op; twelve-month window ends
   at selected month; no conversion helper used in USD mode.
2. Fixture proving personal-flagged ops excluded from aggregates.
3. Visual pass vs design + confirm UZS/USD control present on Графики.
4. Report before/after; list stubs and any deferred §15.4 hand step.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Phase 4 History screen | team |
| Ops across ≥2 months, both currencies, ≥2 parents | team seeds |
| Design file | repo |
| Real Telegram client | customer |

---

## 7. When you must stop and ask me

- Removing the UZS/USD switch from Графики to «match design».
- Copying prototype fixed-rate USD fake conversion.
- PRD and design disagree beyond the approved switch.
- Expanding «Другое» or adding a third chart level.
- Confidence below average — say «not sure».
