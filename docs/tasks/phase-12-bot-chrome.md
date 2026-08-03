# Phase 12 — Bot chrome outside quick entry

PRD: §18.1, §18.3, §18.4. (§18.2 already in Phase 9.)
Depends on: working quick entry (Phases 1–2) so the instruction texts are true.
Plan: written after this spec is approved — not in this file.

---

## 1. User goal

A new person gets the right `/start` greeting and a single keyboard button to
open the app; existing users receive one release announcement that teaches
message entry — not a changelog.

---

## 2. Acceptance steps I will do by hand

1. `/start` from a fresh account → exact §18.1 text; reply keyboard with the
   **single** launch-app button.
2. Join via invite and `/start` → §18.2 text still correct (regression).
3. Confirm `/menu` does not exist as a command.
4. Trigger release announcement once for an existing user; a newly registered
   user never receives it.
5. No extra reply-keyboard buttons beyond the launch button.

---

## 3. What is NOT in this phase

- Changing quick-entry card texts (§7–§8)
- Voice, photo, prompt caching
- Feature tour / welcome screen in the app (§21)
- Uzbek translations
- Actually sending the announcement to production users on a schedule chosen
  by the implementer — **customer** decides when to fire it (§22); phase ships
  the mechanism and a safe trigger the customer runs

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Solo `/start` | Exact §18.1 multiline Russian text. |
| 2 | Keyboard | Exactly one button — open mini app. BotFather menu button may remain. |
| 3 | `/menu` | Not built. |
| 4 | Release announcement | Exact §18.4 text; once per existing user; never to brand-new users after release. |
| 5 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Bot tests: `/start` copy for new vs invited; keyboard button count; `/menu`
   absent; announcement sent once to flagged existing user and skipped for new.
2. Report before/after; list stubs.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Test bot | customer |
| `MINI_APP_URL` for the keyboard button | customer |
| Decision when to fire announcement in real life | customer (§22) |

---

## 7. When you must stop and ask me

- Rewording `/start` or announcement.
- Adding more keyboard buttons or restoring `/menu`.
- Broadcasting the announcement to production without the customer.
- Confidence below average — say «not sure».
