# Task 03 — Bot Onboarding

Depends on: Task 02 (`02-db-schema.md` — done, verified)
PRD reference: §3, §8, §9

## Goal

Implement the `/start` flow: language selection, automatic Owner creation
on first launch, deep-link invite parsing for Member creation, and
seed-data copy (default categories/wallets) into a newly created Family
Budget.

## Step 0 — Schema addition (follow-up migration)

`family_budgets` needs an `invite_token` column, not present in the
Task 02 migration. Add via a new Alembic migration (do not edit
`a1b2c3d4e5f6`, which is already applied):

- `invite_token` (string, nullable, unique, indexed)

One active invite token per Family Budget. Generated on Owner creation
(`secrets.token_urlsafe(16)`). Regeneration (invalidating the old link)
is a Settings feature — out of scope here, deferred to Task 12.

## Flow

### Entry point: `/start [payload]`

Payload is either empty or `invite_<token>`.

1. Look up `users` by `telegram_id` where `is_deleted = false`.
   - **If found**: user is already registered. Reply "You're already a
     member of a Family Budget" (localized to their stored `language`).
     Do nothing else — no re-registration, no budget switching (PRD §8:
     membership is exclusive, no leave/switch flow in MVP).
2. **If not found** — determine flow by payload:
   - **Invite payload** (`invite_<token>`): look up `family_budgets`
     where `invite_token = <token>` and `is_deleted = false`.
     - Not found → reply "Invite link is invalid or expired." Stop.
     - Found → proceed as **Member flow**, target budget = this one.
   - **No payload / invalid payload**: proceed as **Owner flow**, no
     target budget yet (will be created).
3. Ask for language via inline keyboard: "Русский" / "O'zbekcha"
   (callback_data `lang:ru` / `lang:uz`). Store which flow (Owner vs
   Member + target family_budget_id) in FSM state
   (`aiogram.fsm.state`/`FSMContext`, in-memory storage — matches
   local-first MVP, no Redis) until the callback is answered, since
   creation must wait for language.
4. On language callback:
   - **Owner flow**: create `family_budgets` row (generate
     `invite_token`), then create `users` row
     (`role="owner"`, `family_budget_id=<new>`, `language=<chosen>`).
     Copy seed data (see below) into the new budget's `wallets`,
     `income_categories`, `expense_categories` tables.
   - **Member flow**: create `users` row (`role="member"`,
     `family_budget_id=<target>`, `language=<chosen>`). No seed copy —
     budget already has data from the Owner.
   - Send localized welcome message. Owner's message additionally
     shows the invite link (`t.me/<bot_username>?start=invite_<token>`).

### `/invite` command (Owner only)

Added here as a minimal test aid for this task's own verification, since
the real Settings UI (PRD §4.7) is Task 12. Owner sends `/invite` →
bot replies with `t.me/<bot_username>?start=invite_<token>` using their
stored `family_budgets.invite_token`. Member sending `/invite` → bot
replies "Only the Owner can invite members."

**Open point — confirm before I finalize the prompt**: keep this command
in scope for Task 03, or strip it and test the Member flow by inserting
a token manually via `psql`?

## Seed data (copied verbatim from `02-db-schema.md`)

Hardcoded Python constants in the onboarding handler module (not a DB
template table):

- Income categories: Зарплата, Подработка, Подарки, Прочее
- Expense categories → subcategories:
  - Еда → Продукты, Обед, Вода и напитки, Кафе
  - Развлечения → Playstation, Кино, Подписки
  - Транспорт → Такси, Топливо
  - Дом → Аренда, Коммуналка
  - Прочее → Другое
- Wallets (updated 2026-07-21 — see Changelog): Карта сум (UZS),
  Наличный сум (UZS), Карта USD (USD), Наличный USD (USD)

Copied as real rows tied to the new `family_budget_id`; after copying
they're ordinary editable/soft-deletable rows, same as PRD §5 states.

## Acceptance criteria

- [ ] Migration adds `invite_token` to `family_budgets`, reversible
- [ ] First `/start` (no payload) → language prompt → Owner + new
      Family Budget created, seed data copied (4 wallets, 4 income
      categories, 5 expense categories + subcategories)
- [ ] `/start invite_<valid_token>` from a second, unregistered Telegram
      account → language prompt → Member created under the same
      `family_budget_id`, no seed duplication
- [ ] `/start invite_<invalid_token>` → error reply, no rows created
- [ ] `/start` from an already-registered user → "already a member"
      reply, no new rows, existing row untouched
- [ ] `/invite` from Owner → correct deep-link reply; from Member →
      permission-denied reply
- [ ] `users.language` correctly reflects the button chosen

## Verification

1. Apply the new migration, confirm `invite_token` column exists and
   `alembic downgrade -1` removes it cleanly.
2. Open bot with your real Telegram account, `/start`, pick a language
   → confirm in `psql`: new `family_budgets` row, `users` row with
   `role="owner"`, correct `language`; 4 wallets + 4 income categories
   + 5 expense category groups with subcategories, all with correct
   `family_budget_id`.
3. Send `/invite`, get the link.
4. From a second real Telegram account, open the link → pick a
   language → confirm `users` row with `role="member"`, same
   `family_budget_id`, no duplicate seed rows.
5. Send `/start` again from the Owner account → confirm "already a
   member" reply, no DB changes.
6. Try an invite link with a garbage token → confirm error reply, no
   DB changes.

## Changelog

- **2026-07-21**: Default wallet seed template updated from 3 wallets
  (Основной, Карта Uzcard, USD кошелёк) to 4 wallets (Карта сум,
  Наличный сум, Карта USD, Наличный USD). Updated `SEED_WALLETS` in
  `bot/onboarding.py` and wallet assertions in
  `backend/tests/test_onboarding.py`; income/expense category seed data
  unchanged.
- **2026-07-15**: Task 03 implemented and manually verified end-to-end in
  Telegram (not just unit tests). Added migration
  `c10a50738daf_add_invite_token_to_family_budgets.py` (`invite_token` on
  `family_budgets`, nullable/unique/indexed). Updated `FamilyBudget` model and
  `async_session_factory` in `app/db.py`. Implemented `/start` flow in
  `bot/onboarding.py`: existing-user short-circuit → payload parsing → language
  keyboard → FSM-held state → Owner or Member creation on language callback (all
  inside one atomic transaction via `session.begin()`), seed-data copy on Owner
  only, RU/UZ inline message dict. Added `/invite` command (Owner → deep-link;
  Member/unregistered → permission-denied / not-registered reply). Unit tests in
  `backend/tests/test_onboarding.py`: 17/17 pass (payload parsing, invite-token
  lookup, already-registered soft-delete filter, seed-data counts/parent
  linkage).
- **2026-07-15 (manual verification — all 7 checks passed)**:
  1. Migration `c10a50738daf` applied; `alembic downgrade -1` /
     `alembic upgrade head` cycle verified clean.
  2. Owner flow: `/start` → language keyboard → `family_budgets` +
     `users` (`role=owner`) created together, `invite_token` present.
  3. Seed data copied correctly: 3 wallets, 4 income categories, 5 expense
     top-level categories + 12 subcategories with correct `parent_id` linkage.
  4. `/invite` returns the correct deep-link for the Owner.
  5. Member flow: second real Telegram account via invite link →
     `users` (`role=member`) under the same `family_budget_id`; seed data
     **not** duplicated.
  6. Invalid invite token (garbage payload) from a third, unregistered account
     → correct error reply, zero DB writes.
  7. Repeat `/start` from an already-registered Owner → "already a member"
     reply, no DB changes, `created_at` unchanged.
- **2026-07-15 (deviation — intentional, not a spec conflict)**: the
  `language_callback` handler re-checks `get_active_user_by_telegram_id` a
  second time (in addition to the check in `start_handler`) to guard against a
  race where the user completes registration via another path while the
  language keyboard is still pending. Not explicitly specified in the task file
  but does not conflict with the spec.
- **2026-07-15 (local dev note, not a code bug)**: during verification, stale
  test rows unrelated to this session's code were found in `family_budgets` /
  `users` (from earlier ad-hoc testing) and were cleared via `TRUNCATE` before
  the final clean verification pass.