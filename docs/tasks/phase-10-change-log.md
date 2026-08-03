# Phase 10 — Editing others' operations and the change log

PRD: §14.
Depends on: Phase 4 (History edit forms), Phase 7 (personal ops invisible to
others).
Plan: written after this spec is approved — not in this file.
Design: operation edit sheet with `Изменения` block per design / PRD.

---

## 1. User goal

Any family member can fix a shared-wallet operation in History; authorship
stays with the creator; opening the operation shows who changed which fields.

---

## 2. Acceptance steps I will do by hand

1. Member A creates a shared-wallet operation. Member B edits the amount in
   History — succeeds.
2. History still shows **A** as author, not B.
3. Open the operation: `Изменения` shows creation line naming A and a change
   line naming B.
4. Edit three fields at once → three lines under one date; unchanged fields
   omitted.
5. Rename the wallet used in a logged change → old log line still shows the
   name as of the edit moment.
6. Never-edited operation → block absent entirely (not empty).
7. No control to change operation type.
8. Delete operation → cannot be opened in History; deletion not logged.
9. Member B cannot see member A's personal-wallet operation anywhere.

---

## 3. What is NOT in this phase

- Notifications, bot chrome, voice, photo, caching
- Revert-to-previous-value
- Logging deletion as a visible event
- Editing type in place
- Uzbek translations

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Who edits shared ops | Any member. Personal ops: holder only. |
| 2 | Authorship | Never changes on edit. |
| 3 | Log fields | amount, category, wallet, date, comment; for transfer/exchange also source, destination, rate. |
| 4 | Line format | Exact structure §14.2; one line per changed field; old values stored as text at edit time; truncate with ellipsis. |
| 5 | Block visibility | Absent until first edit. |
| 6 | Type | Not editable. |
| 7 | Deletion | Not logged. No revert. |
| 8 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. API tests for permissions, authorship stability, log line generation for
   single- and multi-field edits, frozen old names after rename, absent block
   when never edited, personal ops hidden.
2. Report before/after; list stubs.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Two members in one family | customer |
| Phase 4 edit sheet | team |
| Personal wallet on A (Phase 7) | team |

---

## 7. When you must stop and ask me

- Changing authorship on edit.
- Adding revert or deletion log UI.
- Allowing type change.
- Confidence below average — say «not sure».
