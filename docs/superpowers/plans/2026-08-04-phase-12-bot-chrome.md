# Phase 12 — Bot Chrome Outside Quick Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute. `composer-2.5-fast` is forbidden.

**Goal:** Ship §18.1 `/start` greeting for non-invite users, a single reply-keyboard button that opens the mini app via `MINI_APP_URL`, prove `/menu` is absent, keep §18.2 invite welcome as regression-only, and add a customer-fired one-shot release-announcement script with a per-user delivery marker.

**Architecture:** Solo welcome text lives next to the existing §18.2 helper in `member_texts.py`. Onboarding welcome + reply keyboard are updated in `bot/onboarding.py`; `MINI_APP_URL` becomes optional so a missing value skips the keyboard without crashing startup. Release announcement text + eligibility/send helpers live in `app/services/release_announcement.py`; a manual CLI under `backend/scripts/` fans out once, marks delivery, supports dry-run, and is never wired to startup/scheduler/migrations. Telegram sends are mocked in tests.

**Tech Stack:** Python, FastAPI, Aiogram, Alembic, pytest. No new packages. Backend/bot only — frontend untouched (must stay 205 tests / 37 files).

## Global Constraints

- Spec: `docs/tasks/phase-12-bot-chrome.md` + PRD §18.1, §18.3, §18.4 (+ Acceptance). §18.2 CLOSED in Phase 9 — regression only: do not reword, do not refactor; budget name nominative in « ».
- §18.1 exact four-line text (blank lines as written):
  ```
  Chontak — семейный бюджет.

  Записывайте траты прямо здесь, сообщением:
  `такси 25 тысяч`

  Кошельки, категории и аналитика — в приложении.
  ```
- Example formatting: backticks around `такси 25 тысяч` + `parse_mode="Markdown"` — same as shipped quick-entry / evening-reminder texts. Do not invent a second style.
- Reply keyboard: exactly ONE button, label exactly `Открыть приложение`, `web_app=WebAppInfo(url=MINI_APP_URL)`. No second button. No inline keyboard on this path. BotFather menu button is out of scope.
- If `MINI_APP_URL` is missing/empty: bot starts and works; keyboard is not attached.
- `/menu` must NOT exist — do not create it; remove any handler/command registration if found.
- §18.4 announcement exact text (blank line as written):
  ```
  Теперь трату можно записать прямо здесь, сообщением.
  Напишите, например: `такси 25 тысяч`

  В приложении появились личные кошельки, цели и управление участниками.
  ```
- Announcement delivery: Alembic per-user marker + timestamp; script under `backend/scripts/`; cutoff CLI arg; second run sends nothing to marked users; users created after cutoff never eligible; dry-run reports count and sends nothing; NEVER auto-run (startup/scheduler/lifespan/migration).
- PRD §18.3: announcement carries the keyboard to existing users — attach the same reply keyboard when sending (if URL present).
- Telegram sending mocked in tests (as earlier phases).
- Do **not** touch quick-entry card texts (§7–§8), notifications, digest, goals, members, analytics, or any frontend file. No drive-by refactors.
- Do **not** edit `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/*`, `docs/tasks/*`.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-12-bot-chrome` (already checked out — do not create/switch/merge/rebase).
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Baseline on entry: backend 367 pytest; frontend 205 vitest / 37 files. Numbers may only grow. No existing test deleted or weakened. Frontend must end at 205 / 37.
- User-facing Russian verbatim. Forbidden words: ошибка, сессия, сервер, токен, запрос.
- Confidence below average → write «not sure», do not guess.
- Conversation/report language with customer is Russian; this plan is English (docs/).
- Stop at end of Phase 12 — no Phase 13; do not send the announcement in real life.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/member_texts.py` | Add `welcome_solo()` §18.1; leave `welcome_invited()` untouched |
| `backend/app/config.py` | `MINI_APP_URL: str \| None` — optional, no crash when missing/empty |
| `backend/bot/onboarding.py` | Use `welcome_solo`; button label `Открыть приложение`; optional keyboard; `parse_mode="Markdown"` on welcomes |
| `backend/alembic/versions/r8a9b0c1d2e3_release_announcement.py` | `users.release_announcement_delivered_at` timestamptz nullable |
| `backend/app/models/user.py` | ORM column for delivery marker |
| `backend/app/services/release_announcement.py` | §18.4 text, eligibility query, send+mark helpers |
| `backend/scripts/send_release_announcement.py` | CLI: `--cutoff`, `--dry-run`; never auto-wired |
| `backend/tests/test_phase12_bot_chrome.py` | §18.1 / §18.2 / keyboard / `/menu` / announcement tests |
| `backend/tests/test_onboarding.py` | Update owner-welcome assertion to `welcome_solo()` (existing test must stay meaningful) |

---

### Task 1: §18.1 welcome, reply keyboard, optional MINI_APP_URL, `/menu` absence

**Files:**
- Modify: `backend/app/services/member_texts.py`
- Modify: `backend/app/config.py`
- Modify: `backend/bot/onboarding.py`
- Modify: `backend/tests/test_onboarding.py`
- Create: `backend/tests/test_phase12_bot_chrome.py` (start/keyboard/menu portion)

**Interfaces:**
- Produces:
  - `welcome_solo() -> str` — exact §18.1 multiline text with backticks around the example
  - `OPEN_APP_BUTTON_LABEL = "Открыть приложение"`
  - `open_app_keyboard() -> ReplyKeyboardMarkup | None` — one WebApp button when `MINI_APP_URL` is set; `None` when missing/empty
  - `MINI_APP_URL: str | None` in config (optional)
  - Owner welcome after language pick uses `welcome_solo()` + `parse_mode="Markdown"` + `reply_markup=open_app_keyboard()`
  - Invited welcome still `welcome_invited(name)` unchanged; also send with `parse_mode="Markdown"` so backticks render like quick entry
- Consumes: existing `welcome_invited`, onboarding language callback flow
- Does **not** change: invite refusal paths, join confirm, quick-entry texts, `welcome_invited` body

- [ ] **Step 1: Write failing tests** in `backend/tests/test_phase12_bot_chrome.py`

```python
"""Phase 12 — bot chrome outside quick entry."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import uuid
import asyncio

from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.services.member_texts import welcome_invited, welcome_solo
from bot.onboarding import (
    OPEN_APP_BUTTON_LABEL,
    language_callback,
    open_app_keyboard,
    router as onboarding_router,
)
from bot.membership import router as membership_router
from bot.goals import router as goals_router
from bot.quick_entry.handlers import router as quick_entry_router


START_SOLO_TEXT = (
    "Chontak — семейный бюджет.\n"
    "\n"
    "Записывайте траты прямо здесь, сообщением:\n"
    "`такси 25 тысяч`\n"
    "\n"
    "Кошельки, категории и аналитика — в приложении."
)


def test_welcome_solo_exact_18_1() -> None:
    assert welcome_solo() == START_SOLO_TEXT


def test_welcome_invited_18_2_regression_unchanged() -> None:
    text = welcome_invited("Семья Юсуповых")
    assert text == (
        "Вы присоединились к бюджету «Семья Юсуповых».\n"
        "Всё, что вы запишете, увидят остальные участники.\n"
        "\n"
        "Записывайте траты прямо здесь, сообщением:\n"
        "`такси 25 тысяч`\n"
        "\n"
        "Кошельки, цели и аналитика — в приложении."
    )


def test_open_app_button_label_exact() -> None:
    assert OPEN_APP_BUTTON_LABEL == "Открыть приложение"


def test_open_app_keyboard_single_button(monkeypatch) -> None:
    monkeypatch.setattr("bot.onboarding.MINI_APP_URL", "https://example.test/app")
    kb = open_app_keyboard()
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert len(kb.keyboard) == 1
    assert len(kb.keyboard[0]) == 1
    btn = kb.keyboard[0][0]
    assert isinstance(btn, KeyboardButton)
    assert btn.text == "Открыть приложение"
    assert btn.web_app == WebAppInfo(url="https://example.test/app")
    assert kb.resize_keyboard is True
    assert kb.is_persistent is True


def test_open_app_keyboard_absent_when_url_missing(monkeypatch) -> None:
    monkeypatch.setattr("bot.onboarding.MINI_APP_URL", None)
    assert open_app_keyboard() is None


def test_menu_command_not_registered() -> None:
    routers = (
        onboarding_router,
        membership_router,
        goals_router,
        quick_entry_router,
    )
    for r in routers:
        for handler in r.message.handlers:
            for filt in handler.filters:
                callback = getattr(filt, "callback", filt)
                if isinstance(callback, Command):
                    commands = {c.command for c in callback.commands}
                    assert "menu" not in commands


def test_owner_language_callback_sends_18_1_with_markdown_and_keyboard() -> None:
    async def _run() -> None:
        session = SimpleNamespace(
            add=lambda _model: None,
            flush=AsyncMock(),
        )

        class TransactionContext:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *_args: object) -> None:
                return None

        session.begin = lambda: TransactionContext()

        class SessionContext:
            async def __aenter__(self) -> SimpleNamespace:
                return session

            async def __aexit__(self, *_args: object) -> None:
                return None

        message = SimpleNamespace(answer=AsyncMock(), delete=AsyncMock())
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=123),
            message=message,
            data="lang:ru",
            answer=AsyncMock(),
        )
        state = SimpleNamespace(
            get_data=AsyncMock(
                return_value={
                    "flow": "owner",
                    "telegram_id": 123,
                    "first_name": "Test",
                    "username": "tester",
                }
            ),
            clear=AsyncMock(),
        )
        bot = SimpleNamespace(get_me=AsyncMock())
        fake_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Открыть приложение")]],
            resize_keyboard=True,
            is_persistent=True,
        )

        with (
            patch(
                "bot.onboarding.async_session_factory",
                return_value=SessionContext(),
            ),
            patch(
                "bot.onboarding.get_active_user_by_telegram_id",
                new=AsyncMock(return_value=None),
            ),
            patch("bot.onboarding.copy_seed_data", new=AsyncMock()),
            patch("bot.onboarding.assign_default_card_uzs", new=AsyncMock()),
            patch("bot.onboarding.open_app_keyboard", return_value=fake_kb),
        ):
            await language_callback(callback, state, bot)

        message.answer.assert_awaited_once()
        args, kwargs = message.answer.await_args
        assert args[0] == START_SOLO_TEXT
        assert kwargs.get("parse_mode") == "Markdown"
        assert kwargs.get("reply_markup") is fake_kb

    asyncio.run(_run())


def test_invited_language_callback_keeps_18_2_and_uses_markdown() -> None:
    async def _run() -> None:
        session = SimpleNamespace(
            add=lambda _model: None,
            flush=AsyncMock(),
            get=AsyncMock(
                return_value=SimpleNamespace(
                    name="Семья Юсуповых",
                    is_deleted=False,
                )
            ),
        )

        class TransactionContext:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *_args: object) -> None:
                return None

        session.begin = lambda: TransactionContext()

        class SessionContext:
            async def __aenter__(self) -> SimpleNamespace:
                return session

            async def __aexit__(self, *_args: object) -> None:
                return None

        message = SimpleNamespace(answer=AsyncMock(), delete=AsyncMock())
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=456),
            message=message,
            data="lang:ru",
            answer=AsyncMock(),
        )
        state = SimpleNamespace(
            get_data=AsyncMock(
                return_value={
                    "flow": "member",
                    "telegram_id": 456,
                    "family_budget_id": str(uuid.uuid4()),
                    "first_name": "New",
                    "username": "newbie",
                }
            ),
            clear=AsyncMock(),
        )
        bot = SimpleNamespace(get_me=AsyncMock())

        with (
            patch(
                "bot.onboarding.async_session_factory",
                return_value=SessionContext(),
            ),
            patch(
                "bot.onboarding.get_active_user_by_telegram_id",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "bot.onboarding.count_active_members",
                new=AsyncMock(return_value=1),
            ),
            patch("bot.onboarding.assign_default_card_uzs", new=AsyncMock()),
            patch("bot.onboarding.open_app_keyboard", return_value=None),
        ):
            await language_callback(callback, state, bot)

        args, kwargs = message.answer.await_args
        assert args[0] == welcome_invited("Семья Юсуповых")
        assert kwargs.get("parse_mode") == "Markdown"

    asyncio.run(_run())
```

Also update `backend/tests/test_onboarding.py` owner-welcome assertion:

```python
# was: assert answer_args[0] == MESSAGES["welcome_owner"]["ru"]
from app.services.member_texts import welcome_solo
assert answer_args[0] == welcome_solo()
assert answer_kwargs.get("parse_mode") == "Markdown"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_phase12_bot_chrome.py tests/test_onboarding.py -q`
Expected: FAIL — `welcome_solo` missing and/or owner welcome still old text / wrong button label.

- [ ] **Step 3: Implement**

`backend/app/services/member_texts.py` — add (do not modify `welcome_invited`):

```python
def welcome_solo() -> str:
    return (
        "Chontak — семейный бюджет.\n"
        "\n"
        "Записывайте траты прямо здесь, сообщением:\n"
        "`такси 25 тысяч`\n"
        "\n"
        "Кошельки, категории и аналитика — в приложении."
    )
```

`backend/app/config.py` — replace the required MINI_APP_URL block with:

```python
_raw_mini_app_url = (os.environ.get("MINI_APP_URL") or "").strip()
MINI_APP_URL: str | None = _raw_mini_app_url or None
```

`backend/bot/onboarding.py` changes:

1. Import `welcome_solo` from `app.services.member_texts` (already imports `welcome_invited`).
2. Replace `OPEN_APP_BUTTON` dict with:

```python
OPEN_APP_BUTTON_LABEL = "Открыть приложение"
```

3. Replace `open_app_keyboard` with:

```python
def open_app_keyboard() -> ReplyKeyboardMarkup | None:
    if not MINI_APP_URL:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=OPEN_APP_BUTTON_LABEL,
                    web_app=WebAppInfo(url=MINI_APP_URL),
                )
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
```

4. In `language_callback`, after user creation:

```python
    if flow == "owner":
        welcome = welcome_solo()
    else:
        welcome = welcome_invited(member_budget_name)

    await callback.message.answer(
        welcome,
        reply_markup=open_app_keyboard(),
        parse_mode="Markdown",
    )
```

5. Remove unused `MESSAGES["welcome_owner"]` entries if nothing else references them (keep other MESSAGES keys). Do not create `/menu`. Do not touch invite/`start` refusal paths beyond the welcome send kwargs above.

6. Quick-entry `cards.py` still imports `MINI_APP_URL` — leave that file untouched. Optional URL means cards only matter when URL is configured (customer always sets it in prod).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_phase12_bot_chrome.py tests/test_onboarding.py tests/test_phase9_members.py -q`
Expected: PASS for new/changed tests; phase9 invited-text regression still green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/member_texts.py backend/app/config.py backend/bot/onboarding.py backend/tests/test_phase12_bot_chrome.py backend/tests/test_onboarding.py
git commit -m "$(cat <<'EOF'
feat(bot): §18.1 start text and single open-app keyboard

EOF
)"
```

---

### Task 2: Release announcement marker (migration + model)

**Files:**
- Create: `backend/alembic/versions/r8a9b0c1d2e3_release_announcement.py`
- Modify: `backend/app/models/user.py`
- Test: extend `backend/tests/test_phase12_bot_chrome.py` with a model/column smoke via existing DB fixtures (or assert column on mapped User)

**Interfaces:**
- Produces: `User.release_announcement_delivered_at: datetime | None` (timezone-aware), Alembic revision `r8a9b0c1d2e3` revises `q7f8a9b0c1d2`
- Consumes: nothing from Task 1 beyond clean HEAD

- [ ] **Step 1: Write failing test**

```python
from datetime import datetime, timezone
from app.models.user import User

def test_user_has_release_announcement_delivered_at_column() -> None:
    col = User.__table__.c.release_announcement_delivered_at
    assert col.nullable is True
    # column accepts datetime | None at ORM level
    assert "release_announcement_delivered_at" in User.__mapper__.columns
```

- [ ] **Step 2: Run test — expect FAIL** (attribute/column missing)

Run: `cd backend && source venv/bin/activate && pytest tests/test_phase12_bot_chrome.py::test_user_has_release_announcement_delivered_at_column -q`

- [ ] **Step 3: Implement migration + model**

Migration `backend/alembic/versions/r8a9b0c1d2e3_release_announcement.py`:

```python
"""release announcement delivery marker on users

Revision ID: r8a9b0c1d2e3
Revises: q7f8a9b0c1d2
Create Date: 2026-08-04 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "q7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "release_announcement_delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "release_announcement_delivered_at")
```

In `backend/app/models/user.py` add import for `DateTime` and:

```python
    release_announcement_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

(Need `from datetime import datetime` at top of user.py.)

- [ ] **Step 4: Apply migration locally and run test**

Run: `cd backend && source venv/bin/activate && alembic upgrade head && pytest tests/test_phase12_bot_chrome.py::test_user_has_release_announcement_delivered_at_column -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/r8a9b0c1d2e3_release_announcement.py backend/app/models/user.py backend/tests/test_phase12_bot_chrome.py
git commit -m "$(cat <<'EOF'
feat(db): per-user release announcement delivery marker

EOF
)"
```

---

### Task 3: Release announcement service + CLI script + delivery tests

**Files:**
- Create: `backend/app/services/release_announcement.py`
- Create: `backend/scripts/send_release_announcement.py`
- Modify: `backend/tests/test_phase12_bot_chrome.py` (announcement cases)

**Interfaces:**
- Produces:
  - `RELEASE_ANNOUNCEMENT_TEXT: str` — exact §18.4
  - `async def eligible_users(session, cutoff: datetime) -> Sequence[User]`
  - `async def send_release_announcements(session, bot, cutoff: datetime, *, dry_run: bool = False, now: datetime | None = None) -> int` — returns would-send / sent count; on real send: `bot.send_message(..., parse_mode="Markdown", reply_markup=open_app_keyboard())`, then set `release_announcement_delivered_at = now` and commit per user (or flush+commit batch — prefer mark immediately after each successful send so a mid-run crash does not re-send)
  - CLI: `python scripts/send_release_announcement.py --cutoff ISO8601 [--dry-run]`
- Consumes: `User.created_at`, `User.release_announcement_delivered_at`, `open_app_keyboard` from onboarding, `BOT_TOKEN` / `async_session_factory` for the script
- Must NOT be imported/called from `bot/main.py`, notification scheduler, lifespan, or migrations

Eligibility (all required):
1. `User.is_deleted.is_(False)`
2. `User.created_at < cutoff`
3. `User.release_announcement_delivered_at.is_(None)`

- [ ] **Step 1: Write failing tests** (append to `test_phase12_bot_chrome.py`)

```python
import socket
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.release_announcement import (
    RELEASE_ANNOUNCEMENT_TEXT,
    send_release_announcements,
)
from tests.test_wallets_categories import api_client, create_user_with_budget


ANNOUNCEMENT_TEXT = (
    "Теперь трату можно записать прямо здесь, сообщением.\n"
    "Напишите, например: `такси 25 тысяч`\n"
    "\n"
    "В приложении появились личные кошельки, цели и управление участниками."
)


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def test_release_announcement_text_exact_18_4() -> None:
    assert RELEASE_ANNOUNCEMENT_TEXT == ANNOUNCEMENT_TEXT


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_announcement_sent_once_then_skipped(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    tid = _tid()
    user, _budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    await session.refresh(user)

    cutoff = datetime.now(timezone.utc) + timedelta(hours=1)
    bot = AsyncMock()

    sent1 = await send_release_announcements(session, bot, cutoff, dry_run=False)
    assert sent1 == 1
    assert bot.send_message.await_count == 1
    call = bot.send_message.await_args
    assert call.args[0] == tid
    assert call.args[1] == ANNOUNCEMENT_TEXT
    assert call.kwargs.get("parse_mode") == "Markdown"
    await session.refresh(user)
    assert user.release_announcement_delivered_at is not None

    bot.reset_mock()
    sent2 = await send_release_announcements(session, bot, cutoff, dry_run=False)
    assert sent2 == 0
    bot.send_message.assert_not_awaited()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_user_created_after_cutoff_never_eligible(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    tid = _tid()
    user, _budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    await session.refresh(user)

    cutoff = user.created_at - timedelta(seconds=1)
    bot = AsyncMock()
    sent = await send_release_announcements(session, bot, cutoff, dry_run=False)
    assert sent == 0
    bot.send_message.assert_not_awaited()
    await session.refresh(user)
    assert user.release_announcement_delivered_at is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_dry_run_sends_nothing(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    tid = _tid()
    user, _budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    await session.refresh(user)

    cutoff = datetime.now(timezone.utc) + timedelta(hours=1)
    bot = AsyncMock()
    count = await send_release_announcements(session, bot, cutoff, dry_run=True)
    assert count == 1
    bot.send_message.assert_not_awaited()
    await session.refresh(user)
    assert user.release_announcement_delivered_at is None


def test_script_not_wired_into_bot_main() -> None:
    import bot.main as bot_main
    src = inspect.getsource(bot_main)
    assert "release_announcement" not in src
    assert "send_release_announcement" not in src
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && source venv/bin/activate && pytest tests/test_phase12_bot_chrome.py -q`
Expected: FAIL on missing `release_announcement` module / helpers.

- [ ] **Step 3: Implement service**

`backend/app/services/release_announcement.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Sequence

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from bot.onboarding import open_app_keyboard

RELEASE_ANNOUNCEMENT_TEXT = (
    "Теперь трату можно записать прямо здесь, сообщением.\n"
    "Напишите, например: `такси 25 тысяч`\n"
    "\n"
    "В приложении появились личные кошельки, цели и управление участниками."
)


async def eligible_users(
    session: AsyncSession, cutoff: datetime
) -> Sequence[User]:
    stmt = (
        select(User)
        .where(
            User.is_deleted.is_(False),
            User.created_at < cutoff,
            User.release_announcement_delivered_at.is_(None),
        )
        .order_by(User.created_at.asc())
    )
    return list(await session.scalars(stmt))


async def send_release_announcements(
    session: AsyncSession,
    bot: Bot,
    cutoff: datetime,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> int:
    users = await eligible_users(session, cutoff)
    if dry_run:
        return len(users)

    delivered_at = now or datetime.now(timezone.utc)
    markup = open_app_keyboard()
    sent = 0
    for user in users:
        kwargs: dict = {"parse_mode": "Markdown"}
        if markup is not None:
            kwargs["reply_markup"] = markup
        await bot.send_message(
            user.telegram_id,
            RELEASE_ANNOUNCEMENT_TEXT,
            **kwargs,
        )
        user.release_announcement_delivered_at = delivered_at
        await session.commit()
        sent += 1
    return sent
```

`backend/scripts/send_release_announcement.py`:

```python
"""Send the MVP2 release announcement once to eligible existing users.

Customer-fired only. Never imported by bot startup, scheduler, or migrations.

Run from backend/:
    python scripts/send_release_announcement.py --cutoff 2026-08-04T12:00:00+00:00
    python scripts/send_release_announcement.py --cutoff 2026-08-04T12:00:00+00:00 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from aiogram import Bot

from app.config import BOT_TOKEN
from app.db import async_session_factory, dispose_engine
from app.services.release_announcement import send_release_announcements


def parse_cutoff(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise SystemExit("--cutoff must include a timezone offset (ISO-8601)")
    return dt


async def run(cutoff: datetime, dry_run: bool) -> int:
    bot = Bot(token=BOT_TOKEN)
    try:
        async with async_session_factory() as session:
            return await send_release_announcements(
                session, bot, cutoff, dry_run=dry_run
            )
    finally:
        await bot.session.close()
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cutoff",
        required=True,
        help="ISO-8601 timestamp; only users created BEFORE this receive the message.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many users would receive it; send nothing.",
    )
    args = parser.parse_args()
    cutoff = parse_cutoff(args.cutoff.strip())
    count = asyncio.run(run(cutoff, args.dry_run))
    if args.dry_run:
        print(f"dry-run: {count} user(s) would receive the announcement")
    else:
        print(f"sent: {count} user(s)")


if __name__ == "__main__":
    main()
```

Confirm `dispose_engine` exists in `app.db`; if the name differs, use the same cleanup pattern as `scripts/revoke_app_pass.py` (that script only calls `dispose_engine` if present — match whatever `app.db` exports).

- [ ] **Step 4: Run tests**

Run: `cd backend && source venv/bin/activate && pytest tests/test_phase12_bot_chrome.py -q`
Expected: all PASS.

Then full backend: `pytest -q` — count ≥ 367.
Frontend must remain unchanged: `cd frontend && npx vitest run --reporter=dot` → 205 / 37.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/release_announcement.py backend/scripts/send_release_announcement.py backend/tests/test_phase12_bot_chrome.py
git commit -m "$(cat <<'EOF'
feat(bot): customer-fired release announcement script

EOF
)"
```

---

### Task 4: Full-suite gate + task reports

**Files:**
- Create: `docs/superpowers/plans/phase12-task1-report.md` … `phase12-task3-report.md` (short implementer reports as produced during SDD)
- No product code in this task unless a suite failure needs a minimal fix inside phase scope

- [ ] **Step 1: Run full suites**

```bash
cd backend && source venv/bin/activate && pytest -q
cd frontend && npx vitest run --reporter=dot
```

Expected: backend ≥ 367 passed; frontend exactly `Test Files  37 passed (37)` and `Tests  205 passed (205)`.

- [ ] **Step 2: Confirm git clean and stop**

```bash
git status --short
git log --oneline -5
```

`git status --short` must be empty. Do not start Phase 13. Do not send the announcement.

- [ ] **Step 3: Commit any remaining report files** if uncommitted

```bash
git add docs/superpowers/plans/phase12-task*-report.md
git commit -m "$(cat <<'EOF'
docs: add phase 12 task reports

EOF
)"
```

---

## Self-review (plan author)

1. **Spec coverage:** §18.1 text → Task 1; keyboard one button + optional URL → Task 1; `/menu` absent → Task 1 test; §18.2 regression → Task 1; §18.4 text + once/marker/cutoff/dry-run/no-auto → Tasks 2–3; acceptance items 1–5 covered by tests.
2. **Placeholders:** none — concrete paths and code.
3. **Type consistency:** `send_release_announcements(..., dry_run, now)` used in tests and script; `open_app_keyboard()` returns `ReplyKeyboardMarkup | None` everywhere.
4. **MINI_APP_URL optional:** config change is required for hard rule 5.2; quick-entry cards left untouched per scope (URL present in real env).
