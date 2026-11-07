# Task 14 — Frontend: Settings screen

Depends on: Task 13 (`13-api-family-members.md` — done, verified),
Task 07 (frontend shell, `SettingsPage.tsx` already renders role/firstName/language)
PRD reference: §4.7, §8

## Goal

Extend the existing `SettingsPage.tsx` with three new sections:
category management, wallet management (both Owner-only, soft-delete),
and a family-members section. No backend changes — every endpoint
needed already exists (Task 04 wallets/categories, Task 13 members).

Member **actions** (regenerate invite link, delete member) are
explicitly **out of scope** — deferred to Task 15. This task only adds
**display** for members.

## Existing API used (no backend changes)

| Method | Path | Role | Used for |
|---|---|---|---|
| GET | `/api/v1/wallets` | any | Wallets list |
| POST | `/api/v1/wallets` | Owner | Add wallet |
| DELETE | `/api/v1/wallets/{id}` | Owner | Soft-delete wallet |
| GET | `/api/v1/categories/income` | any | Income categories list |
| POST | `/api/v1/categories/income` | Owner | Add income category |
| DELETE | `/api/v1/categories/income/{id}` | Owner | Soft-delete income category |
| GET | `/api/v1/categories/expense` | any | Expense categories list (flat, has `parent_id`) |
| POST | `/api/v1/categories/expense` | Owner | Add top-level or subcategory |
| DELETE | `/api/v1/categories/expense/{id}` | Owner | Soft-delete (cascades to subcategories if top-level) |
| GET | `/api/v1/members` | any | Members list |
| GET | `/api/v1/members/invite-link` | Owner | Current invite link (read-only) |

`PATCH` endpoints for wallets/categories exist but renaming is **not**
part of this task (see "Out of scope").

## Component structure

Split into subcomponents under `frontend/src/components/settings/`,
assembled by `SettingsPage.tsx` (which keeps its existing
role/firstName/language sections untouched):

- `WalletsSection.tsx`
- `IncomeCategoriesSection.tsx`
- `ExpenseCategoriesSection.tsx`
- `MembersSection.tsx`

### Shared list pattern (Wallets + Income categories)

`WalletsSection` and `IncomeCategoriesSection` have an identical data
shape (`{ id, name, transaction_count }` for income categories;
`{ id, name, currency, transaction_count }` for wallets) and identical
interaction pattern: list → "add" row/button → inline or modal form →
submit → optimistic or refetch update; delete via a per-row action with
confirmation.

Extract the shared list/add/delete mechanics into one reusable
component (e.g. `EditableEntityList.tsx` in the same folder), taking
the entity list, field config, and API functions as props.
`WalletsSection` additionally passes a `currency` select field;
`IncomeCategoriesSection` does not.

**Do not** try to force `ExpenseCategoriesSection` into this shared
component — see below.

### Expense categories (separate, not shared)

`ExpenseCategoriesSection` renders the two-level hierarchy: top-level
categories, each expandable/showing its subcategories. Adding a
subcategory requires selecting/being under a parent
(`POST /categories/expense` with `parent_id` set). Deleting a
top-level category must warn that its subcategories will be deleted
too (cascading soft-delete already happens server-side — the UI only
needs to warn before calling `DELETE`, not implement the cascade
itself).

### Members section (display only in this task)

`MembersSection`:
- Fetches `GET /members`, renders the list (name, role).
- Owner only: fetches `GET /members/invite-link`, shows the link as
  text with a "copy" button (`navigator.clipboard.writeText`, no
  backend call).
- **No regenerate button, no delete button** — both deferred to
  Task 15. Do not add disabled placeholder buttons either; simply
  absent from the UI.

## Icons

No icon library is installed in this project (`Tabbar` currently uses
first-letter placeholders, not real icons — see `AppShell.tsx`).
**Do not add a new npm dependency for this.** Use plain Unicode
emoji as lightweight category icons (e.g. a fixed
`name-keyword → emoji` lookup with a generic fallback emoji for
unmatched names). This is an intentional placeholder — a proper
icon system is planned for a later UX/UI audit pass and will likely
replace this.

## Validation

Pydantic schemas (`app/schemas/wallets_categories.py`) place **no**
length constraint on `name` (not even `min_length=1` — backend would
currently accept an empty string). This is a known pre-release gap,
same category as the missing `amount`/`rate` upper bound noted
earlier. Frontend must guard: `name` required, trimmed,
1–50 characters, inline validation error if violated, submit button
disabled/no-op on invalid input. Add this gap to the pre-release
backlog (do not fix the backend in this task).

## i18n

Add new keys to `ru.json` / `uz.json`, following the existing
`settings.*` key convention:
- Section headers: `settings.categoriesIncome`, `settings.categoriesExpense`, `settings.wallets`, `settings.members`
- Add/delete UI: `settings.addWallet`, `settings.addCategory`, `settings.addSubcategory`, `settings.delete`, `settings.confirmDelete`, `settings.nameLabel`, `settings.currencyLabel`
- Members: `settings.inviteLink`, `settings.copyLink`, `settings.linkCopied`
- Validation: `settings.nameRequired`, `settings.nameTooLong`
- Errors: reuse existing `home.loadError`-style pattern if applicable, or add `settings.loadError` / `settings.submitError`

## Out of scope for this task

- Renaming wallets/categories (`PATCH` endpoints exist but unused here).
- Regenerating the invite link, deleting a member — Task 15.
- A real icon library / icon picker — later UX/UI audit.
- Any backend change, including the `name` length validation gap noted above.
- Leaving the family, changing own role, changing another member's role.
- `vite.config.ts` / deployment cleanup (unrelated, tracked separately).

## Acceptance criteria

- [x] Wallets: list renders from `GET /wallets`; Owner can add a wallet (name + currency) and delete one (soft-delete, confirmation shown); Member sees the list but no add/delete controls.
- [x] Income categories: same as wallets, without currency.
- [x] Expense categories: top-level + subcategory hierarchy renders correctly; Owner can add a subcategory under a chosen top-level category; deleting a top-level category with subcategories shows a warning before confirming.
- [x] Members: list renders from `GET /members`; Owner sees the current invite link with a working "copy" button; no regenerate/delete controls anywhere.
- [x] Name fields: empty or >50-character input is rejected client-side with an inline error, no request sent.
- [x] Non-Owner (Member role) sees read-only wallets/categories (no add/delete controls) and the members list without the invite link block.
- [x] No TypeScript/build errors; `npm run lint` and `npm run build` pass.

## Verification

Manual, in browser, step by step (one step confirmed before moving to
the next):

1. As Owner: add a wallet, confirm it appears in the list and (separately) in Add Income/Expense/Transfer wallet selects.
2. As Owner: delete that wallet, confirm it disappears from Settings and from the Add-transaction selects.
3. As Owner: add an income category, delete it — same checks.
4. As Owner: add a top-level expense category, add a subcategory under it, confirm both appear correctly nested.
5. As Owner: delete the top-level expense category — confirm the warning appears, confirm both it and its subcategory are gone after confirming.
6. As Owner: open Settings, confirm the invite link shows and "copy" places it on the clipboard (paste somewhere to confirm).
7. Switch to Member (telegram_id 222222): confirm no add/delete controls anywhere in categories/wallets, and no invite-link block in Members.
8. Attempt to submit an empty or 51+ character name — confirm inline validation blocks it, no network request (check Network tab).

## Changelog

- **2026-07-22**: Task 14 implemented across three parts plus incremental wiring steps, per project convention of splitting multi-part frontend tasks.

  **Part 1 — Wallets + Income categories**: `frontend/src/api/wallets.ts`,
  `frontend/src/api/categories.ts` (income helpers), shared
  `frontend/src/components/settings/entityNameValidation.ts` (required,
  trimmed, 1–50 chars), `incomeCategoryIcon.ts` (keyword→emoji lookup,
  `📁` fallback, no new npm dependency), `EditableEntityList.tsx`
  (reusable list/add/delete-with-confirmation, read-only mode for
  Member role), `WalletsSection.tsx`, `IncomeCategoriesSection.tsx`.
  Wired into `SettingsPage.tsx` as an immediate follow-up step (instead
  of waiting for a separate Part 4) so it could be manually verified in
  real Telegram before Part 2 started.

  **Part 2 — Expense categories**: extended `categories.ts` with expense
  helpers; new `ExpenseCategoriesSection.tsx` (intentionally not built
  on `EditableEntityList` — client-side groups the flat API response
  into top-level categories with nested subcategories; add affordance
  per top-level group; cascade-delete warning with `{{count}}`
  interpolation on top-level deletion, matching the server-side
  cascading soft-delete from Task 04); `expenseCategoryIcon.ts` (same
  pattern as income). Wired into `SettingsPage.tsx` immediately after
  implementation, same reasoning as Part 1.

  **Part 3 — Members (display only)**: `frontend/src/api/members.ts`;
  new `MembersSection.tsx` — member list (name with `first_name` →
  `@username` → `—` fallback, role), Owner-only invite link block
  (`GET /members/invite-link`, copy via `navigator.clipboard`, no
  regenerate/delete controls per this task's explicit scope — deferred
  to Task 15). Wired into `SettingsPage.tsx` immediately after
  implementation.

  **Result**: all four sections wired into `SettingsPage.tsx` below the
  pre-existing role/firstName/language content. Final `npm run lint`
  and `npm run build` both pass on the combined state (confirmed after
  the Part 3 wiring step, i.e. on the actual final code, not
  per-part in isolation).

  **i18n**: all `settings.*` keys added across Parts 1–3 verified
  present in both `ru.json` and `uz.json` with no gaps (manual
  line-by-line diff after all three parts landed).

  **Manual verification (real Telegram, not browser — see deviation
  note below)**: Owner add/delete/validation confirmed for wallets,
  income categories, and expense categories (including cascade-delete
  warning); invite-link copy confirmed; Member-role read-only behavior
  confirmed for wallets/categories/members (no add/delete controls, no
  invite-link block) after Part 3 landed.

  **Intentional deviation from the original design mockup (pre-dates
  this chat)**: the mockup showed one shared add-form with a category
  select (including a "+ new category" option) and two text inputs.
  The implemented UI instead gives each top-level expense-category
  group its own "+ Добавить подкатегорию" action, and a single
  "+ Добавить категорию" for new top-level categories. Confirmed
  acceptable — same underlying API/data, isolated to
  `ExpenseCategoriesSection.tsx`; may be revisited in a later UX/UI
  audit pass without affecting the rest of Task 14.

  **Known gap carried forward (not fixed in this task, by design)**:
  `name` fields on `WalletCreate`/`IncomeCategoryCreate`/
  `ExpenseCategoryCreate` have no backend length validation (not even
  `min_length=1`); frontend enforces 1–50 chars as a client-side guard
  only. Added to the pre-release backlog alongside the existing
  amount/rate upper-bound gap.

- **2026-07-22 (deviation — intentional, verification channel)**: manual
  verification for this task was done in the real Telegram client
  instead of a regular browser, because the browser's dev-fallback auth
  (`telegram_id=111111`) was hitting `not_onboarded` (404) at the time —
  unrelated to this task's code, most likely stale/reset local test
  data. Not investigated further since real-Telegram verification is an
  accepted substitute per project convention when the user confirms
  manual testing was done.

- **2026-07-22 (Addendum — Members section removed from UI)**: removed
  `<MembersSection />` and its import from `SettingsPage.tsx` only.
  Family-member management deferred past MVP; `MembersSection.tsx`,
  `frontend/src/api/members.ts`, backend members API/schemas/services,
  and unused `settings.members`/`settings.inviteLink`/`settings.copyLink`/
  `settings.linkCopied` i18n keys left in the codebase for a possible
  v2 return. Wallets and both category sections unchanged.
  
## Addendum — Members section removed from UI (2026-07-22)

Decision: family-member management is deferred past MVP (unclear
demand, may revisit in v2). The "Участники семьи" section is removed
from the rendered Settings screen. `MembersSection.tsx`,
`frontend/src/api/members.ts`, and the entire backend
(`app/api/v1/members.py`, `app/schemas/members.py`,
`app/services/invite.py`) are left untouched in the codebase as a
foundation for a future feature — not deleted, just unused.

**Change:** in `frontend/src/pages/SettingsPage.tsx`, remove the
`<MembersSection />` line and its import. No other change to that
file.

**Out of scope:** deleting any Members-related file, deleting the
`settings.members`/`settings.inviteLink`/`settings.copyLink`/
`settings.linkCopied` i18n keys (leave them, unused, in case the
feature returns), any backend change.