# Phase 9 — Members full lifecycle

PRD: §13; Settings row `Участники` (§17.6 row 5); invited-person `/start`
(§18.2); members limit message (§19.1).
Depends on: Phase 7 (personal wallets — join converts wallets to personal).
Plan: written after this spec is approved — not in this file.
Design: Members settings screens one to one with the design file.

---

## 1. User goal

The owner invites, removes, and transfers ownership; a member can leave; a
person joining with their own budget brings wallets as personal without
rewriting the family's past figures.

---

## 2. Acceptance steps I will do by hand

1. Owner opens invite link, second person joins, sees §18.2 `/start` text.
2. Reissue link; old link → «больше не действует» text.
3. Family at 4; fifth opens link → «уже 4 участника» text. App limit message
   for members matches §19.1 (no second sentence).
4. Existing member opens link → «Вы уже участник…».
5. From a budget that has other members, open someone else's link → §13.2
   refusal; nothing changes.
6. Solo budget with 2 wallets + ops → confirmation prompt; accept → wallets
   become **personal** in new family; ops travel; old budget gone; others see
   none of it; goals on those wallets disappear.
7. Solo budget with 12 wallets → §13.2 limit text with number 12; blocked until
   deleted down to ≤5.
8. Remove member with one personal wallet + shared ops: removed text §13.3;
   personal wallet+ops in their new budget; shared ops stay in old family under
   their name; old family figures unchanged; new budget **not** seeded with
   four wallets if personal came along.
9. Remove member with **no** personal wallets → new budget gets standard four;
   default `Карта сум`.
10. History/analytics in old family: `Рустам (бывший участник)` label.
11. Member exit button → voluntary-exit text (first line differs only).
12. Owner has **no** exit button.
13. Ownership transfer: recipient confirm; texts to former owner, recipient,
    remaining members; controls move. Refuse → former owner notified, keeps
    ownership.
14. Owner deletes shared wallet that was another's default → that member's next
    quick entry uses oldest shared wallet; **no** message about the change.

---

## 3. What is NOT in this phase

- Change log UI (§14) — Phase 10
- Notifications reminder/digest (§16) — Phase 11
- Full `/start` rewrite for non-invite and release announcement (§18.1/18.3/18.4)
  — Phase 12 (only §18.2 here)
- Voice, photo, caching
- Merging joined wallets into shared pool
- Uzbek translations

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Invite link | One permanent reusable link per family; reissue invalidates previous immediately; no separate expiry. |
| 2 | Join with own budget | Confirmation required; forbidden if own budget has other members; bring wallets as personal; categories rematch by translation key; invented → «Без категории»; goals on brought wallets disappear. |
| 3 | Personal wallet cap on join | Check before confirm; exact §13.2 text with substituted count. |
| 4 | Removal / exit | Same mechanism; different notification first lines; removed person becomes owner of own budget; personal follows; shared ops stay. |
| 5 | Default wallet resolution | Exact rules in §13.3 (leave/remove, join, shared wallet deleted). |
| 6 | Departed label | `Имя (бывший участник)` identical for removal and exit. |
| 7 | Ownership transfer | To active member; recipient confirms; unilateral irreversible; exact texts §13.5. |
| 8 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Automated tests for each refusal text; join conversion; wallet cap; removal
   split of personal vs shared; default wallet reassignment; transfer
   accept/refuse; departed label.
2. Report before/after; list stubs. Multi-account hand steps remain customer's.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| At least three Telegram test accounts | customer |
| Phase 7 personal wallets | team |
| Ability to create solo budgets via `/start` | existing bot |

---

## 7. When you must stop and ask me

- Merging brought wallets into shared.
- Letting the owner exit without transfer.
- Changing departed-member label wording.
- Any irreversible migration of live production families beyond what §13
  describes for join/leave.
- Confidence below average — say «not sure».
