# Phase 16 Task D — Support Message Relay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let every family member send a support message (quick options or free text) to a configured Telegram support chat; PM replies via Telegram reply-to; bot DMs the original user. Entry point hidden when `SUPPORT_CHAT_ID` unset.

**Architecture:** New bot module `backend/bot/support/` (or `support.py`) with FSM for free-text, outbound relay + mapping table, inbound reply handler scoped to support chat. Config `SUPPORT_CHAT_ID` (optional). Entry is a **bot reply-keyboard button** (not mini-app), using Appendix B strings; language from `User.language` (`ru`/`uz`).

**Tech Stack:** Aiogram FSM, SQLAlchemy, Alembic, pytest.

## Global Constraints

- Worker: `composer-2.5` only.
- This is a **bot** feature, not mini-app (confirmed: Appendix B + existing chrome = reply keyboard). Do not add mini-app Settings control for support.
- Access: **every member**, not owner-only.
- When `SUPPORT_CHAT_ID` unset: entry point **not rendered at all**.
- Verbatim Appendix B RU/UZ strings (see below). Forbidden words: ошибка, сессия, сервер, токен, запрос.
- No rate limit.
- Live E2E against a real group: **do not attempt** — report as pending PM for real chat id. Stub/mock Telegram sends in tests.
- Do not edit docs/context, AGENTS, PRD, design, tasks. No push/checkout.
- Do not touch ru.json/uz.json.
- Alembic `down_revision = "t0c1d2e3f4a5"`.
- Baseline: pytest 443, vitest 206. Frontend likely unchanged.
- **Router order:** include support router **before** `quick_entry_router` so button text / FSM free-text / support-chat messages are not eaten by quick entry.
- Reuse `User.language` for RU vs UZ Appendix B strings (mechanism exists).

## Appendix B strings (verbatim)

| Purpose | RU | UZ |
|---|---|---|
| Entry point | Написать в поддержку | Qo'llab-quvvatlashga yozish |
| Quick 1 | Голосовое сообщение не распознаётся | Ovozli xabar tanilmayapti |
| Quick 2 | Фото чека не распознаётся | Chek fotosurati tanilmayapti |
| Quick 3 | Вопрос по категориям или кошелькам | Kategoriyalar yoki hamyonlar bo'yicha savol |
| Quick 4 | Не приходят уведомления | Bildirishnomalar kelmayapti |
| Write own | Свой вопрос | Boshqa savol |
| Free-text prompt | Напишите ваш вопрос одним сообщением. | Savolingizni bitta xabarda yozing. |
| Confirmation | Сообщение отправлено. Мы ответим вам здесь же. | Xabar yuborildi. Javobni shu yerda kutib turing. |

Header format for support chat: `{family_name} — {person_name}` or `{family_name} — {person_name} (@{username})` when username set. Example style: `Семья Каримовых — Дилноза (@dilnoza_uz)`.

---

### Task 1: Config + mapping table + model

**Files:**
- Modify: `backend/app/config.py` — `SUPPORT_CHAT_ID = os.environ.get("SUPPORT_CHAT_ID") or None` (keep as string; parse int where Telegram API needs it)
- Create: `backend/app/models/support_message.py`
- Create: Alembic `u1d2e3f4a5b6_support_messages.py`
- Register model in models package `__init__` if the project does that
- Test: schema column existence test in `backend/tests/test_phase16_support.py`

Table `support_messages`:
- `id` UUID PK (mixin)
- `forwarded_message_id` Integer NOT NULL — Telegram `message_id` returned after posting to support chat (index)
- `telegram_user_id` BigInteger/Integer NOT NULL — original sender's Telegram id
- `family_budget_id` UUID FK NOT NULL
- timestamps optional via mixin

Unique index on `forwarded_message_id` helpful for lookup.

- [ ] Implement + migrate + commit: `feat(support): add SUPPORT_CHAT_ID and support_messages table`

---

### Task 2: Bot support module (outbound + inbound + keyboard)

**Files:**
- Create: `backend/bot/support.py` (or package) with:
  - `SupportStates(StatesGroup): awaiting_free_text`
  - Strings dict keyed by language
  - `support_entry_label(language) -> str`
  - `build_main_reply_keyboard(language) -> ReplyKeyboardMarkup | None` — consolidate with `open_app_keyboard`: rows for Open App (if MINI_APP_URL) and Support (if SUPPORT_CHAT_ID), using correct language for support label. Return None if both absent.
  - Prefer updating `open_app_keyboard()` in onboarding to accept optional language and include support button when configured — **or** replace call sites to use a shared builder in `bot/support.py` / `bot/keyboards.py`. Update all call sites that currently use `open_app_keyboard()` (onboarding, membership, release_announcement). Update phase12 tests that assert single-button keyboard.
  - Handlers:
    1. Text equals entry label (and SUPPORT_CHAT_ID set): show inline keyboard with 4 quick options + «Свой вопрос» (localized).
    2. Callback quick option: relay that option's exact text; confirm; store mapping.
    3. Callback «Свой вопрос»: set FSM state; send free-text prompt.
    4. Message in FSM state: relay user text; clear state; confirm; store mapping.
    5. Message in support chat with `reply_to_message`: lookup `forwarded_message_id`; if found, DM original user the reply text unchanged; if not found, silent no-op.
  - Ignore messages in support chat without reply_to; ignore unrelated chats for inbound relay.

**Outbound message body:**
```
{header}\n\n{message_text}
```

**Relay helper** (mockable):
```python
async def relay_to_support(bot, *, header: str, text: str) -> int:
    # returns message_id
    msg = await bot.send_message(chat_id=int(SUPPORT_CHAT_ID), text=f"{header}\n\n{text}")
    return msg.message_id
```

**Header builder:** family budget name + user first_name (+ `@username` if `message.from_user.username`).

**Registration:** `backend/bot/main.py` — `dp.include_router(support_router)` **before** `quick_entry_router`.

**Quick entry coexistence:** support router must filter entry-label text and FSM state so those messages never reach quick entry. Support-chat id filter on inbound handler.

- [ ] Tests with mocked Bot send_message / answer:
  1. SUPPORT unset → keyboard has no support button / entry handler no-ops or button absent
  2. SUPPORT set → entry shows 4 + own option
  3. Quick option → outbound called with exact text + header; mapping row; user gets confirmation
  4. Own question → prompt → next message relayed same way
  5. Reply-to matching mapping → exactly one DM with unchanged text
  6. Reply-to no mapping → no send, no exception
  7. Message without reply_to in support chat → no relay
  8. Non-support chat → inbound handler not triggered
- [ ] Commit: `feat(bot): support message relay with quick options and reply routing`

---

### Task 3: Verify Task D

- [ ] Full pytest ≥ 443; vitest ≥ 206
- [ ] Report `/home/xon/Documents/finance-bot/.superpowers/sdd/task-d-report.md`: language reuse, table shape, bot-not-mini-app confirmation, live E2E blocked-on-PM, acceptance 9.3 checklist.
