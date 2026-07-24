# AGENTS.md

## Project

Telegram bot + Mini App for family finance tracking. Full requirements
live in `docs/PRD.md` — read it before starting any task involving
product logic.

## Stack

- Backend: FastAPI + Aiogram, PostgreSQL
- Frontend: React + Vite + TypeScript, TelegramUI
- Frontend linter: Oxlint (not ESLint)
- Telegram SDK: `@tma.js/sdk-react` — do NOT install
  `@telegram-apps/sdk-react`, it is deprecated
- State management: Zustand
- Monorepo: `backend/`, `frontend/`, `shared/`, `docs/`

## Conventions

- Documentation (PRD, roadmap, task files) — English.
- End-user UI strings — Russian/Uzbek via i18n dictionaries
  (`react-i18next`), never hardcoded.
- All monetary amounts are integers, in every currency — no decimals,
  no cents.
- Task files live in `docs/tasks/NN-name.md`, each with explicit
  acceptance criteria and tests where possible — implement against
  those, don't infer scope from the PRD alone.

## Boundaries

Do not change these without explicit discussion first:
- Frontend tooling choices listed above (Oxlint, `@tma.js/sdk-react`,
  Zustand)
- Monorepo folder structure
- Category model: income and expense categories are two separate
  entities, not a shared table with a type field

## Commands

- Backend: not yet defined — venv exists in `backend/`, no
  `requirements.txt` yet
- Frontend: not yet defined — Vite scaffold exists in `frontend/`, no
  `npm install` run yet
