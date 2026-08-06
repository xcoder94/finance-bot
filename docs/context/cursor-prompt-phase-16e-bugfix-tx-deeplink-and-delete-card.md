# Phase 16e follow-up — `«Удалить»` on a bot card must delete the message, not just strip buttons

Branch: `mvp2/phase-16-cascade-demo-protected-support` (continue on it, no new branch).
Orchestrator: Cursor Grok 4.5. Workers: `composer-2.5` only.

Tasks 1 and 3 from the original phase-16e prompt are done and verified
(see `docs/cursor/reports/phase-16e-bugfix-tx-deeplink-delete-card.md`)
— this is only the remaining item, Task 2, now that the PM has decided
the behavior.

Report at `docs/cursor/reports/phase-16e-bugfix-tx-deeplink-delete-card.md`
— append to it, same format: tests before/after, disabled/mocked list,
files touched.

---

## `«Удалить»` on a bot card removes the buttons but leaves the card text stale

**Root cause, confirmed by reading the code:**
`backend/bot/quick_entry/handlers.py:797-826`,
`handle_quick_entry_delete` — after `soft_delete_transaction` +
commit, it only calls
`await callback.message.edit_reply_markup(reply_markup=None)`. It never
touches the message text, so the card keeps showing its original
amount/category/comment/`Осталось: ...` line — a balance that is no
longer accurate the moment the transaction is deleted, with only the
buttons gone.

**Decided with the PM: delete the bot's own message entirely, not
re-render it.** No "record deleted" text, no recalculated balance card
— on `«Удалить»`, the bot's message disappears from the chat, as if it
was never sent. Telegram can't edit a message to empty text, so this
means an actual delete call (aiogram's `Message.delete()` /
`bot.delete_message`), replacing the current
`callback.message.edit_reply_markup(reply_markup=None)` call in
`handle_quick_entry_delete`. Confirm `callback.answer()` still fires
(or isn't needed once the message is gone — check aiogram's behavior)
so Telegram doesn't show a stuck loading spinner on the button tap.

---

## Constraints, same as every phase-16 round

- Full test run before and after, exact numbers, both backend and
  frontend.
- List everything disabled/stubbed/mocked — say "none" if empty.
