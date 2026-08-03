# Phase 4 — History and manual forms

PRD: §17.3 (History), §17.7 (forms). Transfer neutrality from §5 as seen in
History.
Depends on: Phase 3 (Home entry into History).
Plan: written after this spec is approved — not in this file.
Design: History and form sheets must match `docs/design/Chontak MVP2.dc.html`.

---

## 1. User goal

A person opens History from Home or Analytics, adds or edits their own
operations through the forms, and always returns to where they came from.

---

## 2. Acceptance steps I will do by hand

1. Open History from the recent-operations heading on Home. Press back → Home,
   not the charts tab.
2. (If Analytics tabs exist from Phase 5 concurrently — otherwise defer this
   bullet to after Phase 5 merge): open History as the second Analytics tab;
   back / tab behaviour per §17.3.
3. Income/expense form top to bottom: amount (currency label from wallet, not
   separately selectable); category row; wallet row prefilled with default;
   date (today); comment ≤200 characters; `Сохранить`.
4. Expense can be saved with parent only, no subcategory.
5. Category picker: parents expandable to subcategories; can stop at parent.
   «Без категории» does not appear in the picker (§15.3).
6. Transfer/exchange form: same currency → no rate field. Different currencies
   → `Курс` field and result line `100 $ → …` appear.
7. Edit own operation from History: same form + secondary `Удалить` at bottom.
   (`Изменения` block for edits — Phase 10; may be absent until then.)
8. Comment over 200 characters rejected in the form.
9. Empty History state matches design, not a blank area.
10. Transfer in the list: neutral colour, no minus; expense next to it is red.

**Deferred to Phase 10:** editing someone else's shared operation; `Изменения`
block content.

**Deferred to Phase 5:** entry from chart drill-down and filter clearing rules
that mention charts — implement the History screen API so Phase 5 can attach.

---

## 3. What is NOT in this phase

- Analytics charts ladder (§17.4–§17.5) — Phase 5
- Settings entity screens (§17.6) — Phase 6+
- Personal wallet visibility rules beyond not listing others' personal ops if
  already enforced — full §11 UI in Phase 7
- Change log UI (§14) — Phase 10
- Goals, members, notifications, bot chrome, voice, photo, caching
- Changing operation type via edit (forbidden forever — §14 / §21)
- Uzbek translations

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | History has no bottom-menu tab | Two entrances only: Home recent heading; Analytics `История` tab (tab wiring may complete in Phase 5). |
| 2 | Back stack | Returns to the place History was opened from (§17.3). |
| 3 | Forms | Modal bottom sheets; field order and labels per §17.7 and design. |
| 4 | Transfer/exchange one form | Rate field only when currencies differ; result line mandatory then. |
| 5 | Delete on edit | Secondary-styled `Удалить` at bottom of edit sheet, not in a list row. |
| 6 | Type not editable | No control to change expense↔income↔transfer. |
| 7 | Manual entry counters | Manual entry does not spend model-call or unparsed counters (§4). |
| 8 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Automated API/UI tests: create income/expense/transfer via form endpoints;
   comment >200 rejected; parent-only expense; transfer without rate when
   same currency; with rate when different.
2. Navigation test: open History from Home mock → back target is Home.
3. Visual check of empty and filled History vs design.
4. Report before/after; list stubs. Note if Analytics entrance is unfinished
   pending Phase 5.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Phase 3 Home with recent-ops link target | team |
| Seeded categories and wallets | team |
| Design chips for History and forms | repo |
| Real Telegram client for hand pass | customer |

---

## 7. When you must stop and ask me

- PRD and design disagree on form field order or History layout.
- Adding a History item to the bottom menu or a floating `+`.
- Building `Изменения` early without Phase 10.
- Allowing operation type change on edit.
- Confidence below average — say «not sure».
