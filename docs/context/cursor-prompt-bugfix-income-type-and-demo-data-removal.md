git checkout main && git checkout -b fix/income-type-and-demo-data-removal

Worker model: composer-2.5 (exactly that string — not composer-2.5-fast).

Three unrelated fixes bundled in one branch. Do them as three separate
commits, in this order. Full backend + frontend test suites before you
start and after each commit.

---

## Task 1 — Bare income messages get classified as expense

**Symptom (confirmed via prod-adjacent logs on 2026-08-06):** message
`Kirim 500.000 som` ("kirim" = Uzbek for income/incoming) was sent
straight to the Gemini parser (confirmed via `httpx` log line at
09:21:11, real `200 OK` from `generativelanguage.googleapis.com`, not a
cache hit, not the rule-based prefilter). Gemini returned
`type: "expense", category: null` for a message that unambiguously
states income. Resulting transaction: `➖ 500 000 сум`, wallet balance
went to `-500 000`.

Root cause: `IMMUTABLE_PARSER_INSTRUCTIONS` in
`backend/app/parsing/prompt.py` gives the model a JSON schema and
transfer/exchange/date/receipt rules, but no rule at all for resolving
`type: income` vs `type: expense` from bare direction words when there
is no category match. The model guessed wrong on a message with no
category signal (no "зарплата", no wallet keyword, nothing but the
direction word itself).

**Fix:** add an explicit rule to `IMMUTABLE_PARSER_INSTRUCTIONS`
covering common unambiguous direction words in Russian and Uzbek, so a
bare income statement is never defaulted to expense — e.g. kirim,
приход, доход, получил(а), заработал(а) → income even with no category
match; chiqim, расход, потратил(а), заплатил(а) → expense. Exact
wording is your call — this is a system-prompt change, not a code
branch, so there's no single "right" phrasing, just make the direction
unambiguous to the model. Keep it inside the *immutable* (cached) block,
not the per-message payload.

**Test:** add coverage (wherever `prompt.py` / the parser integration
already has tests) for at least:
- `Kirim 500000 som` — no category words, no thousand-word — must
  resolve to `income`.
- `kirim 500 ming` — Uzbek "thousand" spelling — same.
- One negative-control expense case with equally bare phrasing (e.g.
  `Chiqim 500000 som`) to confirm you didn't just flip a default.

**Out of scope, do not touch:** `_PLAIN_AMOUNT_RE` in
`backend/app/parsing/prefilter.py:44` not accepting `.` as a thousands
separator. That's a separate, already-diagnosed bug (dot in `500.000`
splits it into two amounts, which is *why* this message skipped the
prefilter and went to the LLM at all). Leave it — it'll get its own
task.

---

## Task 2 — One-off cleanup of already-seeded demo transactions

Every existing family budget that already has `is_demo=True`
transactions needs them cleared now, not just ones where the owner
happened to click "clear demo data" in the mini app.

Use the existing mechanism as-is —
`app.services.demo_data.clear_demo_transactions` (soft-delete only,
sets `is_deleted=True`, already the exact function the mini-app button
calls) — do not write a new deletion path. Write a small one-off script
(or a management command if the project already has a pattern for
those — check first) that iterates every `family_budget_id` with at
least one non-deleted `is_demo=True` transaction and calls
`clear_demo_transactions` on it, in one commit at the end.

Run it against the local/dev database only. Report exactly how many
transactions were cleared and across how many family budgets. Do **not**
run this against any production database — flag it back to me/PM if you
find one configured and stop.

---

## Task 3 — Stop seeding demo data for new users; remove the feature

This function is not mentioned anywhere in `docs/PRD.md` (confirmed —
grepped for "демо"/"demo", zero hits), so there's no PRD behaviour to
preserve or reconcile here. We're cutting it, not gating it.

**Stop seeding.** Two call sites currently create fake demo transactions
for what is, from the user's point of view, a brand-new budget:

- `backend/bot/onboarding.py:277` — `seed_demo_operations(...)` right
  after a new family budget is created on first `/start`.
- `backend/app/services/membership_lifecycle.py:215` —
  `seed_demo_operations(...)` when a removed/departing member is split
  into their own fresh budget.

Remove both calls. Leave `copy_seed_categories_only` /
`copy_seed_wallets_only` alone at both sites — those seed real starter
categories and wallets (food, taxi, "Наличный сум", etc.), not fake
transaction history, and are still needed.

**Remove the now-dead machinery**, since this is a full removal per
AGENTS.md's "no dead controls" — don't leave an unreachable button or
an API route nothing calls:

- Backend: `seed_demo_operations`, `_seed_demo_month`,
  `DEMO_EXPENSE_SPECS`, `DEMO_INCOME_SPECS`, and any now-unused private
  helpers in `backend/app/services/budget_seed.py`; all of
  `backend/app/services/demo_data.py`; the `GET /api/v1/demo-data/status`
  and `DELETE /api/v1/demo-data` routes in
  `backend/app/api/v1/demo_data.py` (and their router registration).
- Frontend: in `frontend/src/pages/SettingsPage.tsx`, remove
  `hasDemoData`, `clearingDemo`, `loadDemoStatus`, `handleClearDemo`,
  `showClearDemo`, and the JSX block gated on `showClearDemo`; remove
  `frontend/src/api/demoData.ts` and its import.
- Delete or update any tests that reference the removed functions,
  routes, or UI.

**Do not silently touch the schema.** The `is_demo` column on
`Transaction` may end up unused after this. Don't drop it or write a
migration for it — just tell me in your report whether anything else
still reads it, so the PM can decide separately (dropping a column is a
migration, which is a "stop and ask" item, not part of this task).

---

## Report format

Usual format (RAW GIT LOG, RAW GIT STATUS, RAW BACKEND TESTS, RAW
FRONTEND TESTS, ACCEPTANCE, EXTRA, DEFERRED STUBBED OR DISABLED, MODEL
ROSTER, QUESTIONS), plus explicitly answer:

1. Exact wording you added to `IMMUTABLE_PARSER_INSTRUCTIONS` for the
   income/expense direction rule.
2. Cleanup script result: transaction count and family-budget count
   cleared, confirmed local/dev only.
3. Whether anything besides the removed code still references
   `is_demo` (model column, other queries, migrations) — don't decide
   for me, just report it.
