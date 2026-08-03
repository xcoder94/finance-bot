# Phase 11 — Notifications

PRD: §16; Settings row `Уведомления` (§17.6 row 6). Goal achievement event
already defined in §12.3 — ensure it still works; digest trailing line for
unclosed goals ships here.
Depends on: Phase 7 (personal activity counts for evening reminder), Phase 8
(goals for digest / trailing line).
Plan: written after this spec is approved — not in this file.

---

## 1. User goal

If the family recorded nothing all day, everyone gets a calm evening nudge; on
Monday everyone gets the same weekly digest of shared spending; each person can
turn those two messages off independently.

---

## 2. Acceptance steps I will do by hand

1. Record nothing all day. At 21:00 Tashkent every member receives exact §16.1
   text. (Clock wait may sit on my evening checklist — team must prove
   scheduler with time frozen / injected clock in tests.)
2. One personal-wallet operation during the day → no reminder to anyone.
3. Spend in both currencies in a week → Monday digest: two currency blocks,
   UZS first, each with total, money delta, leader.
4. Last week empty in USD → USD comparison line absent; block still present.
5. «Покупки и досуг» as top parent → digest shows its largest subcategory, not
   the parent name.
6. Income during the week → not in digest.
7. Personal spending → not in digest; totals match what other members see.
8. Unclosed achieved goal → trailing line **owner only**.
9. Turn off each switch separately → that message stops, the other continues.
   Settings subtitle lists enabled ones or `Выключены` when both off (§17.6).
10. Goal achievement message has **no** switch and still delivers per §12.3.

---

## 3. What is NOT in this phase

- Three daily reminders (rejected in PRD)
- Per-person breakdown in the digest (§21)
- Income in the digest
- Cross-rate consolidation
- Bot `/start` rewrite / release announcement — Phase 12
- Voice, photo, caching
- Uzbek translations

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Evening reminder | 21:00 Asia/Tashkent; only if **no** family activity that day including personal; exact §16.1 text; all members. |
| 2 | Weekly digest | Monday 10:00 Asia/Tashkent; structure and rules exact §16.2; identical for all members; personal excluded. |
| 3 | Switches | Two independent toggles only; goal achievement has none. |
| 4 | Settings subtitle | Enabled names joined with ` · `; both off → `Выключены`. |
| 5 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Scheduler tests with frozen Tashkent time: reminder yes/no; digest content
   cases (two currencies, missing comparison, Покупки и досуг subcategory,
   income excluded, personal excluded, owner trailing line).
2. Switch off tests.
3. Report before/after; list stubs. Real 21:00 / Monday waits = customer §22.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Phase 7–8 merged | team |
| Multiple members | customer |
| Ability to freeze clock in tests | implementer |

---

## 7. When you must stop and ask me

- Adding a third reminder or digest income lines.
- Including personal spend in digest or reminder logic inverted.
- Putting a switch on goal achievement.
- Confidence below average — say «not sure».
