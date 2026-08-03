# Phase 1 — Quick entry via text

PRD: §7 (Quick entry — text). Supporting rules pulled in only as needed:
§4 (message length, counters, ops-per-message), §15.1–§15.3 (category set for
**new** budgets and service values), §19.2 (chat limit / length refusals used
by §7).
Depends on: Phase 0 complete (application pass not required for bot chat, but
MVP 2 backend baseline and reporting rules are in force).
Plan: written after Phase 0 is approved and done — not in this file.

---

## User goal

A person writes an ordinary message to the bot; the bot creates the money
record(s) immediately and answers with a card (or the one allowed type
question), without asking for a category.

---

## Acceptance steps I will do by hand

Perform on the test bot with an onboarded family that has at least one shared
UZS wallet set as the writer's default wallet, and the new category seed
available (new budget, or a budget already on the MVP 2 category set).

1. Send `такси 25 тысяч`. Within a few seconds a card appears matching PRD §7.1
   layout: sign, amount, subcategory, comment, wallet, date, remaining balance.
2. Send a message that names a wallet in words (`продукты 200 тыс с карты`).
   The card shows that wallet, not the default.
3. Send a message with no wallet named. The card shows the default wallet and
   does not remark on the substitution.
4. Send an amount in a currency that exists in the family while the default
   wallet is the other currency. The card shows a wallet in the named currency.
5. Delete every USD wallet and send a USD amount. No record; reply names the
   currency, points to settings, no button; unparsed counter +1.
6. Send three operations in one message. Three separate cards, each with
   buttons; balances accumulate.
7. Send seven operations in one message. Nothing recorded; §7.5 refusal text
   appears and does **not** name the detected count.
8. Send `подарили 500 тысяч`. No record; two-button question with amount
   visible. (Date-after-wait is in my evening checklist — see below.)
9. Send a message with two clear operations and one ambiguous one. Two cards
   first, then the question block.
10. Send `вчера такси 25 тысяч`. Date is yesterday; comment does not contain
    `вчера`.
11. Send text with no amount. §7.9 text appears; remaining attempts are not
    mentioned.
12. Send a message longer than 500 characters. §19.2 length refusal; neither
    counter moves.
13. After hitting the daily model-call limit (or with the limit set low in
    server config for the test): §19.2 «50» text; manual entry in the app still
    works if the app is available — if Home manual entry is not yet in MVP 2
    shape, verify only that the bot refuses and that the limit config change
    applies the same day (PRD §4).

**Deferred to my evening checklist (PRD §22), not blocking Phase 1 team exit:**

- Tap `[Получил]` a day after `подарили 500 тысяч` → dated from the original
  message day; quota of 50 spent only at tap.
- Card buttons still work on an old card; after deleting the operation in the
  mini app, `«Изменить»` says the record no longer exists and does not recreate
  it (needs History delete from a later phase if not already possible via MVP 1
  UI — if MVP 1 delete exists, use it).

**Implementer-only (PRD §7 acceptance 14):** confirm member B's parse request
never contains member A's personal wallet names. Report the check method.

---

## What is NOT in this phase

- Transfers and exchange parsing (PRD §8) — even if the model returns them,
  Phase 1 must not invent §8 cards; stop and ask if the model returns
  transfer/exchange before Phase 2 (recommended: treat as unparsed / refuse
  with a neutral path only after asking — default: **do not implement §8**).
- Voice (§9), receipt photo (§10)
- Personal wallets product behaviour (§11) — parse may already need to avoid
  leaking personal wallet names of others; creating personal wallets in UI is
  out of scope
- Goals (§12), members lifecycle (§13), change log (§14)
- Mini-app redesign (§17), notifications (§16)
- Prompt caching (§20) — Phase 13
- `/start` rewrite, release announcement (§18) — Phase 12; existing `/start`
  may remain until then
- Uzbek translations
- Choosing or paying for the model provider account (customer)
- Migrating existing families onto the new category set (§15.5 — customer open
  item)

---

## Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Primary channel | Telegram bot private chat with the person (Aiogram). |
| 2 | No category questions | Bot never asks about category. Only undetermined **type** asks (§7.6). |
| 3 | No interim status message | No «разбираю…» or equivalent. Typing indicator is not required for text in §7 (unlike §9/§10). |
| 4 | Card buttons | Exactly three, labels `Кошелёк` · `Изменить` · `Удалить`. Deletion: no confirmation. Buttons work indefinitely. |
| 5 | Default wallet | If text names no wallet → writer's default wallet; no remark on the card. |
| 6 | Wallet list sent to the model | Up to 10 shared wallets of the family **plus** personal wallets of the **writer only**. Never another member's personal wallets. |
| 7 | Wallet match miss | Silent fallback to default wallet. |
| 8 | Currency mismatch with a named currency | Switch to a wallet in that currency (any if two qualify). If **no** family wallet in that currency → no record; currency named in reply; points to settings; no button; unparsed +1. Exact refusal wording: use the Russian string from PRD §7.4 once quoted there — if the PRD names the currency in prose without a full template block, implementer stops and asks for the final Russian sentence rather than inventing it. |
| 9 | Max operations per message | 5. More → full refusal, no partial writes; unparsed +1; text exactly §7.5. Bot recounts operations; does not trust the model count. |
| 10 | Mixed clear + ambiguous | All cards first; questions as a block after. Cards already sent are not rewritten when a later button is tapped. |
| 11 | Type question counters | Quota of 50 spent **on button tap**, not on showing the question. Unparsed not touched if never answered. Operation date = timestamp of the **original message** (Tashkent calendar date). |
| 12 | Type question buttons | `[Потратил]` `[Получил]` — live indefinitely. |
| 13 | «Без категории» | Service value when type chosen by button and no category determined; not a real category slot. |
| 14 | Parent: Subcategory from model | Strip parent; use subcategory (§7.10). |
| 15 | Date rules | Relative markers and weekdays per §7.8; lookback max 31 days; future → today; date words stripped from comment. |
| 16 | Unparsed (no amount) | Exact §7.9 text; unparsed +1. |
| 17 | Model total failure | Exact §7.11 text; unparsed **not** spent. Timeout **10s** per attempt; up to **3** attempts on network / unavailable; never retry malformed request. |
| 18 | Message length | >500 characters → exact §19.2 length text; **before** any model call; neither counter moves. |
| 19 | Daily counters | Model calls 50 / unparsed 20 per family; reset midnight **Asia/Tashkent**; both values from **server configuration**, change applies same day. |
| 20 | New budget category seed | Exactly §15.1 (7 parents, 23 subcategories) and §15.2 (5 income). «События и тои» mandatory. Existing families: **no migration** (§15.5). |
| 21 | Card balance line | Mandatory «Осталось: …» (or transfer layout is out of scope until Phase 2). |
| 22 | Model provider | Use the provider and credentials the customer already configured for parsing; do not open a new vendor account. If none is configured, stop and ask. |
| 23 | Worker model | `composer-2.5` only. |

---

## How the team verifies without me

1. Automated pytest coverage for: length refusal (no model call / counters
   unchanged); >5 operations refusal; bot recount vs model; date parsing
   helpers; wallet visibility filter (member B does not receive member A's
   personal names); counter increment rules; §7.11 does not increment
   unparsed.
2. Integration test with a **stubbed** model response (fixture JSON) proving:
   single expense card fields; multi-op three cards; ambiguous type question
   payload; currency-missing refusal path.
3. One live call against the real model (if credentials present) with
   `такси 25 тысяч` — card created; if credentials absent, report that live
   call as blocked and list it under «disabled / finish later».
4. Report before/after pytest output; list every stub/mock.

Do **not** claim Phase 1 done on stubs alone without stating which PRD
acceptance rows were not executed live.

---

## Preconditions: test bot, data, access

| Need | Who provides | Notes |
|------|--------------|-------|
| Phase 0 merged on the branch under test | team | |
| Test bot + `BOT_TOKEN` | customer | |
| Parsing model API credentials in server config | customer | out of implementer scope to create accounts |
| Daily limit config keys writable locally | customer / local `.env` | so step 13 can lower 50 without code edits |
| Family with shared UZS (and for step 4–5, USD) wallets | team seeds or customer `/start` | new budget preferred for §15 seed |
| Default wallet set for the writer | team or existing settings UI | |
| Second Telegram account (member B) | customer | for wallet-leak check and later phases |
| Asia/Tashkent correctly used in counter reset | implementer verifies in tests | |

---

## When you must stop and ask me

- Model returns transfer/exchange and you are about to invent §8 behaviour.
- PRD §7.4 currency-refusal Russian string is not fully quotable from the PRD
  and must be finalised.
- Any new paid API, speech/vision provider, or new account.
- Migrating old families to the new category set.
- Changing counter numbers or making limits hard-coded instead of config.
- Showing transcription, interim «разбираю…», or asking category questions.
- Confidence below average — say «not sure».
