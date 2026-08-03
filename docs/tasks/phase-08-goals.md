# Phase 8 — Goals

PRD: §12. Achievement message rules in §12.3 (notification delivery shared
with §16.3 — message ships here; digest trailing line may wait for Phase 11).
Depends on: Phase 3 (Цели tab), Phase 6 (shared wallets exist in settings).
Plan: written after this spec is approved — not in this file.
Design: Goals screens one to one with the design file.

---

## 1. User goal

The owner sets a savings goal on a shared wallet; the family sees progress;
when the target is crossed everyone is told, and only the owner can close the
goal — without money moving on close.

---

## 2. Acceptance steps I will do by hand

1. As owner, create a goal on a shared wallet with target and no name → named
   after the wallet.
2. As member, confirm goal creation control is absent.
3. Transfer into the wallet until target crossed. Every member gets achievement
   message; only owner sees `[Закрыть цель]`.
4. Goal stays in `В процессе` at 100%; «Накоплено на … больше» replaces
   «осталось накопить» when over target; at exact 100% that over-line is absent.
5. Drop below target then cross again → second achievement message. No repeat
   while staying above.
6. Owner closes goal → `Достигнутые`, frozen figures, no percentage, no return;
   wallet balances unchanged; wallet free for a new goal.
7. Deadline in the past → label only; date still editable.
8. Wallet with a goal: selectable in quick entry and as default; marked as
   having a goal **only in settings**; progress never on quick-entry cards
   (§12.5).

---

## 3. What is NOT in this phase

- Personal goals (forbidden)
- Weekly digest goal lines (§16.2) — Phase 11
- Members, change log, notifications switches
- Auto-close of goals
- `Оставить` button on achievement card
- Voice, photo, caching, bot chrome
- Uzbek translations

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Model | Optional property of a **shared** wallet; max one active goal per wallet. |
| 2 | Tabs | `В процессе` · `Достигнутые`. |
| 3 | Form | Wallet required; target required; name optional (= wallet name); deadline optional; currency = wallet currency, not selectable. |
| 4 | Progress | balance ÷ target × 100, display capped at 100%. |
| 5 | Close | Owner only; no auto-close; irreversible; no money moves. |
| 6 | Achievement card | Exact §12.3 text; one button owner-only. |
| 7 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Tests: create permissions; progress math and over-target copy; achievement
   fan-out; close freezes and frees wallet; no message while continuously
   above 100%; second crossing sends again.
2. Quick-entry card does not show goal progress.
3. Report before/after; list stubs.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Owner + member accounts | customer |
| Shared wallet for the goal | team |
| Design Goals chips | repo |

---

## 7. When you must stop and ask me

- Auto-closing goals or adding `Оставить`.
- Personal goals.
- Showing goal progress on quick-entry cards.
- Confidence below average — say «not sure».
