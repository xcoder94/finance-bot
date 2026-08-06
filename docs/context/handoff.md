# Handoff — income/demo-data fix merged to main (unpushed); Android mini-app mystery solved (dev-server, not React)

Last updated: 2026-08-06 (end of session — this file was fully rewritten,
not appended to; everything before this point in the file's history is
superseded).

## Read this first — current branch state

**Checked out: `main`, 3 commits ahead of `origin/main`. NOT pushed.**

```
b5da2f7 Remove demo transaction seeding and clear-demo feature.
54867b5 Add one-off script to clear seeded demo transactions across budgets.
87aca28 fix(parser): classify bare kirim/chiqim messages by direction word
```

These are the same three commits from `fix/income-type-and-demo-data-removal`,
fast-forward-merged into `main` this session (main hadn't diverged, so no
merge commit). The branch itself still exists locally, fully merged —
routine cleanup (delete it), not done, low priority.

Backend on `main`: 3 failed / 512 passed (same 3 pre-existing
`test_cascade_fallback_log.py` failures, unrelated, already broken before
this branch). Frontend: 244/244. Re-ran both suites fresh on `main` after
the merge — same numbers as on the branch, nothing regressed.

## What happened this session, in order

1. **Verified the income/expense fix against the real Gemini API** (the
   thing flagged as unverified at the end of last session — no test had
   ever called the actual model). Wrote a throwaway script
   (not committed, was in scratchpad) that calls `app.parsing.factory.get_parser()`
   directly — the real `HttpParser` with `provider="google"` — bypassing
   Telegram entirely. Sent the exact reported message `Kirim 500.000 som`
   plus 3 variants (`kirim`/`chiqim`, with/without dot). Result: **fix
   confirmed** — `Kirim 500.000 som` now returns `type='income'`,
   amount 500000, category "Зарплата". Expense-direction messages still
   classify correctly. This is real evidence, not a report claim.

2. **Re-ran the demo cleanup script.** Queried DB first: 23 non-deleted
   `is_demo=True` transactions remained in family budget
   `dd462eda-1c18-48d6-855b-8d427baaad2f` (the ones the stale process
   reseeded between the cleanup commit and last session's 10:54 restart —
   see previous handoff for that story). Ran
   `backend/scripts/clear_seeded_demo_transactions.py` — cleared all 23,
   confirmed 0 remain via a follow-up query.

3. **Merged `fix/income-type-and-demo-data-removal` into `main`.**
   `main` had not diverged (merge-base == main HEAD == `9eb378b`), so it
   was a clean fast-forward. Re-ran both test suites on `main`
   post-merge — same results as above. **Did not push to `origin`** —
   that's a separate call, deliberately left for the PM.

4. **PM reported, via manual testing, a new/different bug shape** than
   last session's theory: an **old Android phone opens the mini app fine
   through the production bot** (deployed on the server) but **AI doesn't
   respond there**; the same phone, on the same wifi, testing the
   **local** dev setup, has it backwards — **AI works, mini app doesn't
   open**. PM's hypothesis: maybe a React version downgrade (19→18/17)
   would help old phones open the app.

5. **Investigated the React-downgrade hypothesis — found it's not React,
   found and confirmed the real cause.**
   - Web research first (per PM's explicit "search, don't answer from
     memory" instruction): React 17/18/19's actual differences are
     concurrent rendering (18) and Actions/useOptimistic/less boilerplate
     (19) — nothing about minimum device/browser support changed
     meaningfully across versions. Explained this to PM in plain language
     with a cashier metaphor.
   - **The real, confirmed cause: dev-server vs. production build.**
     `frontend/index.html:11` uses `<script type="module">` — native ES
     modules. No `@vitejs/plugin-legacy` installed, no `browserslist`
     config anywhere in the project. In dev mode (`npm run dev`, port
     5173, tunneled via a rotating `trycloudflare.com` quick-tunnel
     hostname), Vite serves ~2900 raw untranspiled module files straight
     to the browser — nothing is "translated" for old engines. A
     production build (`vite build`) at least bundles/minifies (though
     still no down-leveling, since no legacy plugin is installed).
   - **The PM's own manual re-test proved it, independent of React
     version**: production and local both run the *exact same* React 19
     from the *same* `package.json`. Production (served as a build) opens
     on the old phone; local (served as raw dev-server ESM over the
     rotating tunnel) doesn't. Since the React version is identical in
     both, the version cannot be the differentiator — this alone falsifies
     the downgrade hypothesis regardless of the dev-server theory.
   - **Built `frontend/dist/` this session** (`npm run build` —
     `tsc -b && vite build`, clean, no errors; `dist/` is gitignored,
     nothing to commit). Told PM to run `npm run preview` (port 4173) and
     manually repoint `cloudflared` at it — restarts/tunnel reconfig are
     outside this assistant's scope per `AGENTS.md`, PM did this part
     themselves.
   - **PM re-tested on the old Android phone against the `preview` build
     — it opened.** Hypothesis fully confirmed by direct evidence, not
     just theory: the failure was dev-server delivery (raw ES modules +
     ephemeral tunnel domain), not React, not the phone's WebView being
     fundamentally broken (proven since production already worked on it).

6. **PM asked about day-to-day dev workflow implications** — does every
   save now require a manual `npm run build` + `npm run preview` +
   re-tunnel cycle? Answered: no. Recommended workflow, not yet acted on:
   - Normal feature/bugfix dev: keep using `npm run dev` (port 5173, HMR)
     exactly as before — nothing changes, fast iteration on
     desktop/iPhone is unaffected.
   - Only when specifically testing old/weak-device compatibility: run
     `vite build --watch` in one terminal (auto-rebuilds `dist/` on save)
     + `npm run preview` in another (started once, left running, serves
     whatever's currently in `dist/` — no restart needed per rebuild) +
     point the tunnel at port 4173 once. After that, the only manual step
     per save is refreshing the mini app on the test phone.
   - Offered to add a `"build:watch": "vite build --watch"` convenience
     script to `frontend/package.json`. **PM has not answered yet — asked
     to be reminded of this question in a future session.** Do not assume
     an answer either way; ask again.

## Two separate, unrelated bugs are now on the table — do not conflate them

- **Bug A (mini app not opening on old Android) — SOLVED this session**,
  root-caused and fixed by testing/serving via a production-style build
  instead of the dev server. Nothing left to build; only the open
  `build:watch` convenience-script question above remains.
- **Bug B (production bot's AI not responding)** — **not solved, not new**.
  Matches a previously diagnosed, still-unresolved issue from an earlier
  session: Gemini's "User location is not supported" block, seen only in
  production (server IP/account-country mismatch), never reproduced
  locally (local testing this session again went through Gemini
  successfully every time — see item 1 above, real `200 OK`s throughout).
  Outside this assistant's scope (keys/provider accounts/server config)
  — waiting on the PM/hosting contact to try one of the previously
  discussed remediation paths. Nothing to build here from this side.

## Uncommitted working-tree state right now (by design, not oversight)

- **`AGENTS.md`** — modified, never committed, PM-only file per its own
  rule. Do not stage it, ever.
- **`docs/context/*`** — never committed (standing PM rule). Carried over
  unchanged from before, still open, still not deleted:
  - `cascade-keyword-review.md` — status still unclear, still stale. Ask
    the PM directly; standing policy is to delete once done+verified.
  - `cursor-prompt-phase-16e-bugfix-tx-deeplink-and-delete-card.md` and
    `cursor-prompt-phase-16g-cascade-fallback-log.md` — both fully
    executed and verified, still not deleted. Offer again next session.
  - `mini-prd-cascade-demo-protected-categories.md` — status unknown,
    untouched.
  - `deploy-mvp2-vs-mvp1-notes.md` — written for the PM to paste into the
    separate deploy chat. Still there; deploy status unknown.
  - `cursor-prompt-bugfix-income-type-and-demo-data-removal.md` and
    `report-income-type-and-demo-data-removal.md` — task spec and report
    for the now-merged fix, from last session. Still there, untouched.
- **`docs/bugs_screens/`** — still untracked, still an open call whether
  to commit. Unchanged this session.
- **`docs/app.log`** — still sitting there untracked, still contains the
  production Google API key in plaintext (from several sessions ago). Not
  touched this session. Still worth flagging key rotation once production
  Bug B (above) is sorted.
- **`.claude/`** — local tool config, never committed.
- **`frontend/dist/`** — new this session, from the production build test.
  Gitignored (`frontend/.gitignore:11`), nothing to commit, nothing to
  clean up.

## Open questions / next steps for a fresh session

1. **`build:watch` convenience script** — PM said they'll ask about this
   later. Remind them if it doesn't come up; don't assume an answer.
2. **Push `main` to `origin`** — 3 commits sitting locally ahead of
   `origin/main`, never pushed. PM decision, not yet made.
3. **Delete the now-fully-merged `fix/income-type-and-demo-data-removal`
   branch** — routine cleanup, not done.
4. **Bug B — production Gemini location block** — still open, still
   needs the PM/hosting contact. See above.
5. **`is_demo` column** — not dropped, per the original task spec (schema
   changes are a "stop and ask"). Still present on `Transaction`, now
   written only by nothing in product code (the seeding feature is fully
   removed) and read only by the one-off cleanup script. PM decision
   needed on whether to drop it later.
6. **Prefilter dot-as-thousands-separator bug**
   (`app/parsing/prefilter.py:44`, `_PLAIN_AMOUNT_RE`) — still diagnosed,
   still not fixed. Small regex change (accept `.` alongside space/`_`),
   ready whenever the PM says go.
7. Everything already open before this session, still open, untouched:
   - `uz.json` still has 2 keys in Russian
     (`settings.membersScreen.sincePrefix`, `home.personalTitle`).
   - `docs/bugs_screens/` — commit or not, still open.
   - Several other `mvp2/phase-*` branches still exist locally, all fully
     merged into `main` — routine cleanup, not done.
   - Customer's 18-of-20 voice-recognition gate and 20-receipt accuracy
     gate (PRD §23) — neither run yet; timing of the phase-12 release
     announcement — still open, still the customer's call.
   - Deploy itself (migrations, restarts, env vars on the real server) is
     still outside this session's scope.

## Immediate next step

Nothing blocked on the assistant. Whenever a fresh session starts: check
whether the PM wants `main` pushed to `origin`, and remind them about the
open `build:watch` script question if they haven't brought it up.
