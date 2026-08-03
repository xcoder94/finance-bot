# Chontak — family budget in Telegram

Bot plus mini app. Continuation of an existing project, now MVP 2.
MVP 2 differs substantially from the first version — do not rely on how
things were done before.

## Sources of truth

- `docs/PRD.md` — what the product does. If something is not in it,
  do not invent it — ask me.
- `docs/design/Chontak MVP2.dc.html` — how the mini app looks. Open it
  in a browser; the chips at the top switch screens.
- The bot has NO design file. Bot cards, buttons and texts come from the
  PRD alone.
- `docs/tasks/*.md` — the spec for the current phase.

## Mini app design — must match one to one

Same elements, same top-to-bottom order, same spacing, sizes and type
weights, same colours in light and dark theme. Do not improve, simplify
or add anything of your own.

The design also shows states, and they are mandatory: empty month,
loading skeleton, failed-entry screen, limit messages, owner view,
member view.

## When the PRD and the design disagree

The PRD is the source of MEANING. The design is the source of APPEARANCE.

If the disagreement is only about looks — placement, order, spacing, size,
the wording on a control, which screen an element sits on — the design
wins. Follow it and do not ask.

If the design would break product behaviour described in the PRD — a rule,
a limit, a calculation, who may do what, what happens after an action —
the PRD wins. Follow it and note the deviation in your report.

Stop and ask me only when both documents describe the same behaviour
differently, or when neither describes it at all. Never build both variants.

One deviation is already approved and recorded in the PRD: the `Графики`
tab of Analytics carries a UZS/USD switch that the design does not show
(PRD 17.4). Keep it. Do not "restore" the screen to the design here.

The prototype fakes its USD state by dividing UZS amounts by a fixed rate.
Nothing in this product converts currency. Never copy that behaviour.

## Stack — fixed, not up for discussion

Backend: Python, FastAPI, Aiogram, Alembic, pytest.
Frontend: React, Vite, TypeScript, TelegramUI, Zustand, Oxlint,
react-i18next (`ru.json`, `uz.json`).
Telegram SDK: `@tma.js/sdk-react`. `@telegram-apps/sdk-react` is
deprecated — never suggest it.
Database: PostgreSQL. Layout: `backend/`, `frontend/`, `shared/`, `docs/`.

Replacing any item, adding a framework, switching state library or
linter — ask me first.

Never assume a package version or library feature exists because you
remember it. Check the installed version or current documentation.

## Orchestration and worker models

**Orchestrator:** Cursor Grok 4.5. Reads this file, makes decisions,
breaks work into tasks, launches workers.

**Workers:** Composer 2.5 only. Write the name letter for letter:
`composer-2.5`. Do not use `composer-2.5-fast`.

**How workers are launched:** Orchestrator sends the task spec and
requests a worker by name. If the requested model is unavailable,
orchestrator stops and tells me. Silently substituting another model
is forbidden.

**What workers do:** Implement one task from the plan. Report output,
test results, and a list of everything disabled or mocked. No explanations,
no narration.

## Reporting to me

I do not read code. Your words are not evidence; program output is.
Every report includes the test run before the change and after it, and a
separate list of everything disabled, stubbed, mocked or marked "finish
later". If that list is empty, say so.

## User-facing text

- Every string the user sees is quoted verbatim in Russian in the PRD.
  Carry it over character for character — no rephrasing, no shortening,
  no emoji that are not there.
- Uzbek translations are out of scope.
- Words that never appear in user-facing text:
  ошибка, сессия, сервер, токен, запрос.
- Interface labels are localised; category names and comments entered by
  the user are never auto-translated.
- Documents in `docs/` are in English. Conversation with me is in Russian.

## Outside your scope

Keys and provider accounts, domains, hosting, TLS, deployment, restarts,
backups, bot registration, server configuration values, Uzbek
translations, slicing the PRD into phases. Do not do these and do not
offer to do them for me.

## Editing this file

`AGENTS.md` is edited by me only. Do not add sections, rewrite wording or
"improve" rules here. If a rule is missing or blocks you, say so in your
report and stop.

## When to ask me and when to decide yourself

Decide yourself, without asking:
- Which library or package inside the approved stack.
- Names of variables, functions, files; folder structure inside a module.
- The order of small steps inside one task from the plan.
- Wording of error messages and log text.
- Small refactoring of code you wrote in this same phase.

Stop and ask:
- The task needs a new external service, a paid API or a new account.
- The task goes beyond the phase spec, even if convenient to do now.
- You found a simpler way, but it changes the approved plan.
- A decision is hard to undo: deleting data, an irreversible migration,
  publishing anything outward.
- Two solutions give a different result for the user, not merely
  different code — that choice is mine.
- Your confidence is lower than average for the task — say "not sure"
  instead of choosing silently.

Default rule: if the answer is not in this file, the PRD, the phase spec
or the plan — stop and ask, do not guess.

## No dead controls

Every button, link and field on a finished screen must perform its
action. A control that does nothing, shows nothing or leads nowhere is a
defect, not groundwork for later.

If the feature belongs to a later phase, the control is not drawn at all
— not drawn disabled. A disabled placeholder is allowed only when the
PRD describes it explicitly.
