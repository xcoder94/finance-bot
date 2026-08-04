# Phase 14 — Task 4: Full suite verification + live-credentials gate

**Branch:** `mvp2/phase-14-voice`  
**Date:** 2026-08-04

## SPEECH_* credentials

```
provider False
key False
model False
```

**Live acceptance:** BLOCKED — all three `SPEECH_*` values are absent. Steps 1–5 of live acceptance must not be run or faked.

## Backend: `pytest -q`

```
........................................................................ [ 17%]
........................................................................ [ 35%]
........................................................................ [ 52%]
........................................................................ [ 70%]
........................................................................ [ 87%]
...................................................                      [100%]
=============================== warnings summary ===============================
venv/lib/python3.14/site-packages/fastapi/testclient.py:1
  /home/xon/Documents/finance-bot/backend/venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
411 passed, 1 warning in 23.42s
```

## Frontend: `npx vitest run --reporter=dot`

```
npm warn Unknown env config "devdir". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.

 RUN  v4.1.10 /home/xon/Documents/finance-bot/frontend

·············································································································································································································

 Test Files  37 passed (37)
      Tests  205 passed (205)
   Start at  18:25:07
   Duration  2.37s (transform 1.83s, setup 0ms, import 4.30s, tests 768ms, environment 7ms)
```

## Frontend diff check

```
$ git diff --name-only | grep '^frontend/' || true
(empty)

$ git diff --name-only HEAD | grep frontend || true
(empty)
```

No frontend file changes in working tree or vs HEAD.

## Commit

No commit made — all suites passed without fixes.

## git log --oneline -20

```
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
```

## git status

```
On branch mvp2/phase-14-voice
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   docs/context/handoff.md

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	docs/context/cursor-prompt-phase-14.md
	docs/superpowers/plans/phase14-task1-report.md
	docs/superpowers/plans/phase14-task2-report.md
	docs/superpowers/plans/phase14-task3-report.md
	docs/superpowers/plans/report-13phase.md

no changes added to commit (use "git add" and/or "git commit -a")
```

## Stubbed / disabled / mocked

None.
