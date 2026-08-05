# Report — Phase 16: protected categories, demo data, cascade prefilter, support relay

Branch: `mvp2/phase-16-cascade-demo-protected-support`
HEAD: `7c9f5ef`
Date: 2026-08-05
Orchestrator: Cursor Grok 4.5
Workers: composer-2.5 only (all four tasks)

---

## Коротко: что произошло

**Да — все четыре таска уже сделаны.** Ветка от `main`, планы и код закоммичены по очереди A → B → C → D, финальные тесты зелёные.

**«Agent loop» — это не сбой во время тестов.** Это штатный цикл оркестратора:

1. Оркестратор пишет план таска → коммит плана.
2. Запускает воркера `composer-2.5` на реализацию.
3. Воркер пишет код, гоняет тесты, коммитит.
4. Оркестратор проверяет результат и только потом стартует следующий таск.

Тесты (`pytest` / `vitest`) гонялись **после** каждого таска и ещё раз в конце. Они не «зациклились» — просто долго крутились полный бэкенд-сьют (~24 с) плюс фронт.

Baseline на входе (после `git checkout main` + ветка, Postgres поднят): **pytest 412**, **vitest 205**.
Финал: **pytest 461**, **vitest 206**.

---

## Как шли таски

| Таск | План (commit) | Код (commits) | Тесты после |
|------|---------------|---------------|-------------|
| A Protected categories | `07478c3` | `5ad78d6`, `e940254`, `061b1f1` | 422 / 206 |
| B Demo data + clear | `7622c3d` | `a115824` | 428 / 206 |
| C Cascade prefilter | `9bbb718` | `359ecda`, `3ed22fe` | 443 / 206 |
| D Support relay | `3e95c33` | `2b3c8c3`, `7c9f5ef` | 461 / 206 |

---

**TASK A — DESIGN DECISIONS**

- Column: `expense_categories.is_protected` BOOLEAN NOT NULL, `server_default=false`. Alembic `s9b0c1d2e3f4`. No UPDATE/backfill of existing rows.
- Seed: `copy_seed_categories_only` sets `is_protected=True` only for parent `translation_key` in `{food, home, health}`.
- Limit: parent create count excludes `is_protected=True` (max 8 non-protected). Limit message text unchanged.
- API: PATCH/DELETE on protected → HTTP 403. Response includes `is_protected`.
- Frontend: hide swipe-delete / parent danger-delete when protected; limit UI uses `countNonProtectedExpenseParents`. Parent rename UI already absent; API still blocks rename.
- Confirmation: migration did not touch any existing category row values beyond adding the defaulted column.

---

**TASK B — DESIGN DECISIONS**

- Model is `Transaction` (no `operation.py`); column `transactions.is_demo` BOOLEAN NOT NULL default false. Alembic `t0c1d2e3f4a5`.
- `seed_demo_operations` in `budget_seed.py` — previous calendar month, exact breakdown, `card_uzs` / `card_usd`, realistic comments, net UZS +2M / USD +100.
- Hook correction vs prompt §7.1.3: production `copy_seed_data` exists only in `bot/onboarding.py`. Member auto-budget is `membership_lifecycle.py` (`copy_seed_categories_only` + conditional wallets). Demo seeding hooked in **both** places (architect default).
- Detach with personal wallets: if shared card wallets missing, call `copy_seed_wallets_only` then seed (adds 4 shared seed wallets).
- Clear: owner-only `DELETE /api/v1/demo-data` soft-deletes `is_demo=True` via same soft-delete as user deletes. Settings button «Очистка демо данных» (hardcoded, not i18n) only when owner and demo rows remain; no confirm dialog.

---

**TASK C — DESIGN DECISIONS**

- Modules: `cascade_keywords.py` (Appendix A RU+UZ verbatim), `prefilter.py` (`try_prefilter` pure, no network).
- Amount parsing: **new** regex in prefilter (no prior utility to reuse) — plain ints + «тысяч»/«тыс».
- Fail-safe: exactly one category (subs first), exactly one amount, no transfer/multi-op signal, ≤1 wallet match; else fall through. Never emits `MSG_NO_AMOUNT`. Category match: current names authoritative; Appendix A synonyms only while name still equals seed RU name for that `translation_key`.
- Wire: `process_quick_entry_text` only (`prefilter_enabled=True`); voice/receipt untouched. Prefilter runs **before** `can_model_call`; hit skips parser and `spend_model_call`.

---

**TASK D — DESIGN DECISIONS**

- Language: reused existing `User.language` (`ru`/`uz`) for Appendix B strings.
- Table: `support_messages` — `forwarded_message_id` (unique), `telegram_user_id`, `family_budget_id`. Alembic `u1d2e3f4a5b6`.
- Config: `SUPPORT_CHAT_ID` optional; entry hidden when unset.
- Confirmed **bot feature**, not mini-app: reply-keyboard button + inline quick options + FSM free text; router before quick_entry. Access: every member.
- Live E2E: not attempted — blocked on PM for real group id.

---

**RAW GIT LOG**

```
7c9f5ef feat(bot): support message relay with quick options and reply routing
2b3c8c3 feat(support): add SUPPORT_CHAT_ID and support_messages table
3e95c33 docs: add phase 16 Task D support relay plan
3ed22fe feat(bot): wire text quick-entry prefilter before LLM parser
359ecda feat(parsing): add rule-based quick-entry prefilter
9bbb718 docs: add phase 16 Task C cascading prefilter plan
a115824 feat(phase16): demo transaction seeding and owner clear control
7622c3d docs: add phase 16 Task B demo data plan
061b1f1 feat(frontend): hide delete for protected expense parents
e940254 feat(categories): protect food/home/health and exclude from parent limit
5ad78d6 feat(categories): add is_protected column for expense categories
07478c3 docs: add phase 16 Task A protected categories plan
97fd2d1 Merge branch 'mvp2/phase-14-voice'
3a164d3 docs: add phase 14 task reports
ae8f662 test(voice): cover SpeechUnavailable without unparsed spend
9d4c2c3 test(voice): assert typing chat_action kwargs
26d0d55 feat(bot): wire voice messages through shared quick-entry pipeline
3c886f1 refactor(quick-entry): extract process_quick_entry_text for voice reuse
db8cb2f feat(speech): add Google speech-to-text client and SPEECH_* config
d4cfe93 docs: add phase 14 voice input implementation plan
635ffc9 Merge branch 'mvp2/phase-13-prompt-caching'
bffeab8 docs: add phase 13 task and final review reports
a3156b2 chore(parsing): add live Gemini cache measurement script
5828c43 feat(parsing): use Gemini cache with full-prompt fallback
367f102 feat(parsing): add Gemini explicit prompt-cache manager
f238c3b feat(parsing): add Google Gemini full-prompt provider branch
373635d feat(parsing): add static cache text and prompt version id
85e6d05 docs: add phase 13 prompt-caching implementation plan
bd67301 Merge branch 'mvp2/phase-12-bot-chrome'
8f11248 docs: phase 13 kickoff handoff and Cursor prompt
1a23dbc fix(bot): add parse_mode to join_accept welcome; add phase 12 handoff notes
2525fa0 docs: add phase 12 task 4 suite gate report
a36b2b7 test(bot): assert announcement keyboard and skip deleted users
60827d6 docs: phase 12 task 3 report
abcfec5 feat(bot): customer-fired release announcement script
e903289 docs: phase 12 task 2 report
438cbea feat(db): per-user release announcement delivery marker
cb3bc4b docs: phase 12 task 1 report
cef55ed feat(bot): §18.1 start text and single open-app keyboard
b9eef42 docs: add phase 12 bot chrome implementation plan
```

---

**RAW GIT STATUS**

```
On branch mvp2/phase-16-cascade-demo-protected-support
Changes not staged for commit:
	modified:   AGENTS.md
	deleted:    docs/context/cursor-prompt-phase-13.md
	modified:   docs/context/handoff.md

Untracked files:
	.claude/
	docs/context/cursor-prompt-phase-14b-voice-unify-then-15.md
	docs/context/cursor-prompt-phase-16-cascade-demo-protected-support.md
	docs/context/mini-prd-cascade-demo-protected-categories.md
	docs/context/report14b&15phase.md
	docs/superpowers/plans/report-13phase.md
```

(Note: `docs/cursor/reports/` this file may appear untracked until committed. Pre-existing dirty `AGENTS.md` / `docs/context/*` left unstaged on purpose — never committed per rules.)

---

**RAW BACKEND TESTS**

```
........................................................................ [ 15%]
........................................................................ [ 31%]
........................................................................ [ 46%]
........................................................................ [ 62%]
........................................................................ [ 78%]
........................................................................ [ 93%]
.............................                                            [100%]
=============================== warnings summary ===============================
venv/lib/python3.14/site-packages/fastapi/testclient.py:1
  /home/xon/Documents/finance-bot/backend/venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
461 passed, 1 warning in 23.90s
```

---

**RAW FRONTEND TESTS**

```
npm warn Unknown env config "devdir". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.

 RUN  v4.1.10 /home/xon/Documents/finance-bot/frontend

··············································································································································································································

 Test Files  37 passed (37)
      Tests  206 passed (206)
   Start at  09:07:59
   Duration  1.85s (transform 1.20s, setup 0ms, import 3.05s, tests 638ms, environment 6ms)
```

---

**ACCEPTANCE — TASK A**

1. New budget: «Еда»/«Дом»/«Здоровье» — no delete control in UI; API delete/rename rejected — done
2. Other four parents + all subcategories (incl. under protected) still deletable/renamable — done
3. 8 non-protected parents then 9th → existing limit message — done
4. Pre-migration / default-false «Еда» still editable — done
5. `is_protected` NOT NULL, defaults False — done

**ACCEPTANCE — TASK B**

1. `/start` new budget → previous month seeded, current empty — done
2. Settings «Очистка демо данных» owner only — done
3. Clear removes only `is_demo`; real ops untouched — done
4. Button disappears after clear — done
5. Removed-member auto-budget also gets demo (assumption confirmed: hooked in membership_lifecycle) — done
6. Empty-month state still reachable — done

**ACCEPTANCE — TASK C**

1. «такси 25 тысяч» resolves without parser call; card path works — done
2. Renamed category: stock Appendix A keywords for food do not match; current names authoritative — done
3. Two amounts / transfer / ambiguous → fall through to parser — done
4. Voice and receipt paths untouched — done
5. `daily_model_calls` not incremented on prefilter hit — done
6. Existing text quick-entry tests still pass — done

**ACCEPTANCE — TASK D**

1. `SUPPORT_CHAT_ID` unset → entry absent — done
2. Set → four quick options + «Свой вопрос» — done
3. Quick option → outbound + header + mapping + confirmation — done (stubbed Telegram)
4. «Свой вопрос» → free text → same relay — done
5. Reply-to with mapping → one DM, text unchanged — done
6. Reply-to without mapping → silent no-op — done
7. Other chat / no reply_to → no relay — done
8. Live E2E — **not done**: pending PM for real `SUPPORT_CHAT_ID`

---

**EXTRA**

Nothing beyond the four-task spec (no PRD.md edits, no phase 17).

---

**DEFERRED STUBBED OR DISABLED**

- Task D live end-to-end against a real Telegram support group: **blocked-on-PM** (needs real `SUPPORT_CHAT_ID`). Stubbed/mocked Telegram sends in unit tests only — not skipped silently.
- Task B/C/D unit tests mock Telegram bot / parser doubles where appropriate; no production feature flags disabled.

---

**MODEL ROSTER**

- Orchestrator (branch, plans, verification, this report): Cursor Grok 4.5
- Task A explore: composer-2.5
- Task A implement: composer-2.5
- Task B explore: composer-2.5
- Task B implement: composer-2.5
- Task C explore: composer-2.5
- Task C implement: composer-2.5
- Task D explore: composer-2.5
- Task D implement: composer-2.5

---

**QUESTIONS**

1. Task B: on member detach **with** personal wallets, we also seed the four shared wallets (`copy_seed_wallets_only`) so demo can land on «Карта сум»/«Карта USD». Wallet count becomes personal+4. Confirm this is acceptable, or should demo skip when only personal wallets exist?
2. Task C: prefilter hit strips amount/category terms from comment (often empty comment on simple «такси 25 тысяч»), whereas LLM path sometimes keeps a remainder — intentional for the rule path; say if card comment must match LLM shape exactly.
