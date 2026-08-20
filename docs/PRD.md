# Chontak MVP 2 — Product Requirements

## 0. How to read this document

This document describes the product in user-facing terms: what a person does
and what a person sees. It contains no code, no database schemas, no file
names, and no library names.

**Section order is not a work order.** The customer slices the work into
phases separately. Each capability is written as a self-contained block and may
be built in any sequence, except where a dependency is stated explicitly.

### Language rule — mandatory

Requirements are written in English. **Every string the user sees is quoted
verbatim in Russian and must ship exactly as written.** These strings were
finalised through separate review; do not translate them, do not rephrase them,
do not "improve" them, do not add emoji that are not shown.

Uzbek translations are out of scope for this document. They are produced after
the Russian strings are locked.

### Acceptance model — two levels

**Level 1 — implementer self-check.** Every capability below ends with an
`Acceptance` block. The implementer runs these steps before reporting the work
as done, and reports the observed result of each step. These steps require no
source code reading and no database access.

**Level 2 — customer pass.** Section 22 is a short hands-on checklist for the
customer, covering only what an implementer physically cannot verify: real
Telegram client rendering, real receipt photographs, real voice recordings,
time-based events, and session lifetime beyond one hour.

---

## 1. Product purpose

Chontak is a family budget product inside Telegram: a bot plus a mini
application.

A family tracks money together — income, expenses, transfers between wallets,
and currency exchange. Records are created two ways: by sending plain text to
the bot (primary), or through a form in the mini application. The result is
visible to every family member on one screen and in shared analytics.

What MVP 2 changes: a record is created from ordinary text without picking a
category or wallet by hand; each member gets personal wallets invisible to
everyone else; savings goals appear; family membership becomes fully
manageable.

---

## 2. Glossary

| Term | Meaning |
|---|---|
| **Budget** | The unit of accounting. One person belongs to exactly one budget. |
| **Family** | All members of one budget, 1 to 4 people. |
| **Owner** | The member who controls shared wallets, categories, goals and membership. Exactly one per budget. |
| **Member** | Any other person in the family. There are no intermediate roles. |
| **Shared wallet** | Wallet whose operations every member sees. Created by the owner only. |
| **Personal wallet** | Wallet whose operations only its holder sees. Each member creates their own. |
| **Category** | A parent expense category, or an income category. |
| **Subcategory** | Second level inside a parent expense category. Expenses only. |
| **"Без категории"** | Service category value, used when no category was determined. Not a real category. |
| **"Другое"** | Service roll-up in analytics: everything beyond the 8 chart colours. Never appears on an operation record. |
| **Quick entry** | Creating a record by sending a message to the bot. |
| **Card** | The bot's reply to quick entry: a message showing the created record plus buttons. |
| **Default wallet** | The wallet a quick-entry record lands in when the text names no wallet. Each member has their own. |
| **Model call** | One parse request for one user message, regardless of how many operations result from it. |

---

## 3. Roles and permissions

| Object | Who creates | Who edits and deletes |
|---|---|---|
| Shared wallets | owner | owner |
| Personal wallets | each member, for themselves | the wallet holder |
| Categories and subcategories (shared only) | owner | owner |
| Goals (shared wallets only) | owner | owner |
| Operations on shared wallets | any member | any member |
| Operations on personal wallets | the wallet holder | the wallet holder |
| Members, invitations, ownership transfer | owner | owner |

Rules that follow from the table:

1. Any member edits and deletes any operation on a shared wallet, not only
   their own.
2. **Authorship never changes on edit.** History keeps showing the person who
   created the record.
3. Buttons under a chat card edit that card's own operation only — the card
   arrives in its author's private chat. Editing someone else's operation
   happens in the mini application, in History.
4. A personal wallet is invisible to everyone except its holder, **including
   the budget owner** — no balances, no operations, no analytics rows.
5. The owner cannot leave the budget. Ownership must be transferred first.

---

## 4. Numeric limits

| Limit | Value |
|---|---|
| Members per family, owner included | 4 |
| Shared wallets per family | 10 |
| Personal wallets per person | 5 |
| Parent expense categories | 8 |
| Subcategories inside one parent | 8 |
| Name length: wallet, category, subcategory, goal | 30 characters |
| Quick-entry message length | 500 characters |
| Operation comment length | 200 characters |
| Model calls per day, per family | 50 |
| Unparsed messages per day, per family | 20 |
| Operations per single quick-entry message | 5 |
| Date lookback parsed from text | 31 days |
| Dates in the future | never accepted |

**Categories.** The limit counts all categories, not "beyond the seeded ones".
Deleting frees a slot. The service value "Без категории" occupies no slot. A
deleted category occupies no slot. There is no family-wide subcategory limit —
only 8 inside each parent.

**The create button stays visible and enabled** when a limit is reached. The
limit message appears after the tap, not in place of the button.

**Names.** At least one non-whitespace character. Leading and trailing spaces
are trimmed before the length check. An emoji counts as one character. A name
too long for its space is truncated with an ellipsis anywhere in the product,
never wrapped to a second line.

**Quick-entry message length.** Over 500 characters is a refusal, not a
truncation. The check runs **before any model call**: no counter is spent.

**Comment.** The mini-application form rejects input over 200 characters. On
quick entry the bot truncates its own generated comment and still creates the
record.

**Counters.** Both are per family, both reset at midnight Tashkent time.

- The quota of 50 counts **model calls, not created records**. Five operations
  parsed from one message spend one unit.
- Unparsed (20) is a separate, independent ceiling.
- Manual entry in the mini application is subject to neither counter.

**Both numbers — 50 and 20 — are set by server configuration** and change
without editing source, the same way an external service key does. **A new
value takes effect immediately, including the current day:** raise the limit
and a member who hit the wall in the morning continues writing; lower it and
the wall arrives at once.

### Acceptance

1. Create shared wallets up to 10. The create button stays enabled. Tap it:
   the message from 19.1 appears. Delete one wallet, create again — it works.
2. Repeat for personal wallets at 5, expense categories at 8, subcategories
   inside "Еда" at 8, members at 4. Each shows its own message from 19.1.
3. With 8 expense categories, delete one and create another — creation
   succeeds, confirming a deleted category holds no slot.
4. Enter a 31-character wallet name — rejected. Enter only spaces — rejected.
   Enter 30 characters and open the wallet list — the name is truncated with
   an ellipsis, not wrapped.
5. Send the bot a message longer than 500 characters. The refusal appears and
   neither counter moves.
6. Send one message containing five operations. Five records are created and
   the daily quota drops by 1, not by 5.
7. Change the daily limit in server configuration mid-day and send a message
   immediately: the new value applies the same day.

---

## 5. Global display rules

**Currencies.** UZS and USD. There is no automatic conversion anywhere in the
product: amounts in different currencies are never summed — not on the home
screen, not in analytics, not in the weekly digest. A rate is entered by a
person and only inside an exchange operation.

**Time.** Every daily event — counter reset, evening reminder, weekly digest,
the boundary of "today" — is computed in Tashkent time.

**Colour.** Green and red mean income and expense and nothing else. Transfers
and exchanges use neutral text colour, and the amount carries no minus sign.

**Charts.** Exactly 8 category colours. Categories beyond the eighth roll up
into "Другое". Colour is bound to the category, never assigned by its position
in a list.

**Assigning a colour to a new category.** A new category receives a colour that
is free among active categories and does not match any category deleted within
the last 12 months. If no colour satisfies both conditions, the colour of the
longest-deleted category is reused.

**Theme.** Colours come from the Telegram theme. Light and dark are equal
citizens; the product has no theme switch of its own.

**Words never used in user-facing text:** "ошибка", "сессия", "сервер",
"токен", "запрос".

### Acceptance

1. Record an expense of 100 000 UZS and an expense of 10 USD in the same month.
   Home screen and analytics show them separately by currency; no combined
   figure exists anywhere.
2. Record a transfer. In History it is neutral-coloured with no minus sign,
   while an expense next to it is red.
3. Delete a category and immediately create a new one. Open analytics for a
   month containing both: their colours differ.
4. Switch the Telegram client between light and dark theme. Every screen
   follows; no screen keeps hard-coded light colours.

---

## 6. Application pass (dependency for everything else)

**Problem being solved.** Entry currently depends on the credential snapshot
Telegram issues once at launch. That snapshot never refreshes and the server
rejects snapshots older than one hour, so any session longer than an hour is
refused. Extending the acceptance window postpones the problem instead of
solving it.

**Requirement.** The application issues its own pass at first entry and keeps
the person signed in for the whole time the app is open, and across reopenings,
without depending on the age of the Telegram snapshot.

**Residual failure path.** If entry is still not granted, the application makes
**one silent retry**. Only if that also fails does the person see a screen:

> Не удалось открыть приложение. Закройте его и откройте снова через меню
> бота.
>
> [Попробовать снова]

The button is the primary action, and the sentence gives the fallback path,
because an expired Telegram snapshot is never fixed by tapping again.

This is a **dependency for the rest of MVP 2**: without it no other capability
can be verified by hand for longer than an hour.

### Acceptance

1. Open the mini application, leave it open for more than one hour, then
   interact with it. It responds normally, with no re-entry screen.
2. Close the application, wait more than one hour, reopen it. It opens without
   asking anything.
3. Reach the failure screen deliberately (revoke the pass on the server). The
   silent retry happens first; only after it fails does the screen appear, and
   its text matches the quote above word for word.

---

## 7. Quick entry — text

The primary way to record money. The person writes ordinary text to the bot;
the bot determines type, category, wallet and date on its own, creates the
record immediately, and answers with a card.

**The bot never asks about category.** The single exception to "no follow-up
questions" is an undetermined operation type, described in 7.6.

### 7.1 The card

Shows: amount, type, category, wallet, comment, date, and **the wallet balance
after the operation**. Balance is mandatory. Date is always shown, not only
when it differs from today. The parent category is not shown, only the
subcategory; if no subcategory was determined, the parent stands alone.
Goal progress is not shown on the card.

Layout is compact, without field labels. The operation sign replaces the word:

> ➖ **25 000 сум** · Такси
> такси до работы
> Наличный сум · 1 августа
> Осталось: 1 275 000 сум

### 7.2 Buttons under the card

**«Кошелёк» · «Изменить» · «Удалить».** Changing the wallet is a separate
button because it is the most frequent correction. Deletion asks for no
confirmation.

**Buttons work indefinitely** — a card from last month is still operable. The
only refusal: if the operation was already deleted in the application, the bot
answers that the record no longer exists and does not recreate it.

### 7.3 Wallet selection

**The wallet is taken from the text. If the text names none, the default wallet
is used.** Matching is by meaning, not by exact letters.

Wallet names sent for parsing are limited to: up to 10 shared wallets plus the
personal wallets **of the person writing**. **One member's personal wallets
must never reach another member's parse request** — that would leak what even
the budget owner cannot see.

If no wallet matches, the bot silently uses the default wallet, with no remark
in the card.

### 7.4 Currency mismatch

If the named currency does not match the chosen wallet, **the bot switches the
wallet itself** to a wallet in the named currency. If two wallets qualify, it
picks either — the chosen wallet is written in the card, so the person sees it.

If the family has **no wallet in that currency at all**, no record is created.
The bot replies naming the currency directly and points to settings. There is
no button in this message. **The unparsed counter is spent.**

### 7.5 Multiple operations in one message

**One separate message per operation**, each with its own buttons. Balances in
successive cards accumulate, so the person sees the movement step by step.

More than 5 operations — **refusal in full, with no partial recording**. The
detected count is not named:

> В одном сообщении можно записать не больше 5 операций. Разбейте на
> несколько сообщений.

The unparsed counter is spent.

**The bot recounts operations itself and does not trust the model's count.** If
the parsed result contains more than five operations, the refusal applies even
when the model reported no error. This check is deterministic and survives any
future model replacement.

### 7.6 Undetermined operation type

The only case where the bot asks. Two triggers: the word "подарок" without a
verb ("подарили" is income, "подарил" is expense), and a verbless fragment with
no category to lean on ("12 000", "Азиз 300 тысяч").

**No record is created.** Instead of a card:

> **500 000 сум** · Подарки
> Не понял, это трата или доход?
>
> [Потратил] [Получил]

The amount is shown before the tap, so a misparse can be caught before anything
is written. The category is shown if it was determined.

**Counters:** the quota of 50 is spent **at the moment the button is tapped**;
the unparsed counter is not touched. If the person never answers, nothing is
spent.

**Buttons live indefinitely.** Tapped a day later, the operation date is taken
**from the moment of the original message**, not from the moment of the tap.

After the tap the record is created and the question is replaced by an ordinary
card with ordinary buttons. Category resolution:

- determined from text — that category is used; "Подарки" is resolved by the
  tapped button (income category vs. the subcategory under "События и тои");
- not determined at all — the service value "Без категории":

> ➖ **300 000 сум** · Без категории
> Азиз
> Карта сум · 1 августа
> Осталось: 975 000 сум

### 7.7 Mixed message

Several operations where some parsed fully and some need a type choice. Reply
order: **all cards first, then the questions as a block after them.**

Balances accumulate across cards, so a question standing mid-chain would make
the next card's balance look wrong.

**Cards already sent are not recalculated after a button tap.** Rewriting five
earlier messages for balance consistency is worse than the discrepancy.

There is no special rule for "all five are ambiguous" — five button pairs are
no worse than five cards.

### 7.8 Date from text

The bot reads relative markers and weekday names: "вчера", "позавчера", "в
понедельник", "в прошлую пятницу", "3 дня назад". A weekday without
qualification means **the most recent past one**, never the coming one.

Lookback is capped at 31 days. Dates in the future are never accepted; the date
falls back to today.

**Words about the date never end up in the comment** — "вчера" in a comment on
a record already dated yesterday reads as noise.

### 7.9 Unparsed message

In practice "could not parse" means no amount was found. One universal text:

> Не нашёл сумму в сообщении.
> Напишите так: `такси 25 тысяч` или `продукты 200 тыс с карты`

The second example teaches that a wallet can be named in words. **Remaining
attempts are never mentioned.**

### 7.10 Category format returned as "Parent: Subcategory"

The parser sometimes returns a category as "Родитель: Подкатегория" (for
example "Транспорт: Такси"). The bot accepts this form and **strips the
parent**, using the subcategory. It must not treat such a value as an
undetermined category.

### 7.11 The model did not answer at all

Timeout expired and retries did not help. This is a failure on our side, not a
misunderstood message:

> Не получилось записать — дело не в вашем сообщении. Попробуйте отправить
> его ещё раз через минуту или запишите операцию в приложении.

**The unparsed counter is not spent.** Every other refusal spends it because
the person wrote something the bot did not understand; here the message may
have been perfect and we are the ones who failed.

The four words "дело не в вашем сообщении" are mandatory. Without them the
default behaviour is to assume the wording was wrong and rewrite the phrase.

No button in the message.

**There is no interim "разбираю…" message anywhere in quick entry.** Measured
response time is about one second. The failure text arrives only after all
retries.

### 7.12 Reliability requirements

1. **Every parse call has a timeout: 10 seconds per attempt.** A hung call must
   surface as a failure rather than waiting forever.
2. **Retry on network failure and on service-unavailable responses — up to
   three attempts total.** A malformed-request response is never retried; it is
   not transient.
3. **Exchange sanity check before any record is created** — see 8.3. This runs
   on the bot side and does not depend on the model.
4. **Operation recount by the bot** — see 7.5.

### Acceptance

1. Send `такси 25 тысяч`. A card appears within a few seconds, matching the
   7.1 layout: sign, amount, subcategory, comment, wallet, date, remaining
   balance.
2. Send a message naming a wallet in words (`продукты 200 тыс с карты`). The
   card shows that wallet, not the default one.
3. Send a message naming no wallet. The card shows the default wallet and
   contains no remark about the substitution.
4. Send an amount in a currency for which the family has a wallet, while the
   default wallet is in the other currency. The card shows a wallet in the
   named currency.
5. Delete every USD wallet and send a USD amount. No record is created, the
   reply names the currency, points to settings, and has no button. The
   unparsed counter increases by 1.
6. Send three operations in one message. Three separate cards arrive, each with
   its own buttons, and balances accumulate across them.
7. Send seven operations in one message. Nothing is recorded and the 7.5 text
   appears without naming a number.
8. Send `подарили 500 тысяч`. No record is created; the two-button question
   appears with the amount visible. Wait a day, then tap `[Получил]`: the record
   is created with **yesterday's** date, and the quota of 50 drops only now.
9. Send a message with two clear operations and one ambiguous one. Two cards
   arrive first, the question block after them.
10. Send `вчера такси 25 тысяч`. The date is yesterday and the comment does not
    contain the word "вчера".
11. Send a message naming a date 40 days back. The date is not accepted beyond
    the 31-day cap.
12. Send text with no amount. The 7.9 text appears and says nothing about
    remaining attempts.
13. Create a record, delete it in the mini application, then tap `«Изменить»`
    on its old card. The bot answers that the record no longer exists and does
    not recreate it.
14. Log in as member B and send a message. Confirm the parse request for B
    never contains member A's personal wallet names. *(Verified by the
    implementer against the outgoing request, not by the customer.)*

---

## 8. Transfers and exchange via quick entry

### 8.1 Why this is not optional

A bot that cannot parse transfers records "переложил 500 тысяч с карты на
наличные" as an expense — money vanishes from the budget while never having
left it. Additionally, putting money aside for a goal *is* a transfer.

### 8.2 Transfer — same currency

Both wallets found in the text and their currencies match: the record is
created immediately. The card shows **both balances with wallet labels**,
because two bare numbers cannot be read:

> ↔️ **500 000 сум** · Перевод
> Карта сум → Наличный сум · 1 августа
> Карта сум: 1 200 000 · Наличный сум: 1 775 000

Buttons: **«Изменить» · «Удалить»**. There is no `«Кошелёк»` button here —
what needs changing is specifically the source or the destination, and one
button cannot express that.

### 8.3 Exchange — different currencies

Two wallets in different currencies means an exchange, which requires a rate.

**A rate present in the text — the exchange is created.** A rate is recognised
**only when an explicit marker word is present** ("по", "по курсу"); otherwise
the bot cannot tell which of two numbers is the amount and which is the rate.
The card shows both the rate and the resulting amount, so an error is visible
at once:

> 🔄 **100 $ → 1 280 000 сум** · Обмен
> Курс 12 800 · 1 августа
> Карта USD: 400 $ · Карта сум: 3 080 000 сум

Buttons: **«Изменить» · «Удалить»**.

**No rate in the text — refusal with the direct reason**, never a generic
phrase, otherwise the person assumes the words were not understood, rewrites
the same sentence, and spends a second counter:

> Перевод между кошельками в разных валютах — это обмен, для него нужен курс.
> Сделайте его в приложении.

The unparsed counter is spent: no record was created, but a model call happened.

### 8.4 Mandatory sanity check before writing

This check runs on the bot side, before any record is created, and does not
depend on the model:

> If the parsed operation is a transfer or an exchange, and the currencies of
> the source and destination wallets differ, and no exchange rate is present —
> the parsed result is discarded, no record is created, and the refusal from
> 8.3 is sent. The unparsed counter is spent.

**Why this is mandatory.** Without it the bot silently records a transfer of
50 dollars as a transfer of 50 sums. Nobody is told; the money simply moves
wrong. This is the worst class of failure — the silent one.

### Acceptance

1. Send `переложил 500 тысяч с карты на наличные`. A transfer card appears in
   the 8.2 layout, with both balances labelled, no minus sign, neutral colour,
   and only two buttons.
2. Send `поменял 100 долларов на сумы по 12800`. An exchange card appears
   showing both the rate and the resulting amount.
3. Send `перевел с карты доллара на карту сум 50$`. **No record is created**
   and the 8.3 refusal text appears. Check the wallet balances afterwards: they
   are unchanged. This is the check from 8.4 and it is the single most important
   step in this section.
4. Repeat step 3 with the same sentence written in Uzbek
   (`dollar kartasidan so'm kartasiga 50$ o'tkazdim`). Same result.
5. Send `поменял 100 долларов на сумы 12800` — without the marker word "по".
   The rate is not silently assumed; the refusal from 8.3 appears.

---

## 9. Voice input

**Not a launch condition.** This capability may ship after the release.

The person sends a voice message; the bot transcribes it through an external
service and then treats the resulting text exactly like quick entry — same
parsing, same cards, same buttons, same counters.

**Provider is selected by a test, not by vendor claims:** 20 real voice
messages recorded by the customer, run through 2–3 candidates. **Acceptance
threshold is 18 of 20.**

**While transcription runs — the standard Telegram typing indicator.** Set
immediately, cleared with the reply. There is no "Расшифровываю…" service
message: with several operations in one recording there would be nothing to
replace it with, and it would hang in the chat as litter.

**The transcription is never shown to the person, under any circumstances.**
Showing "here is what I heard" looks honest but provokes an argument with the
bot about words instead of a second recording.

Two failure paths, kept separate:

**Speech not recognised** (noise, too quiet, empty recording) — no text at all:

> Не разобрал голосовое. Попробуйте записать ещё раз или напишите текстом.

**Speech recognised but contains no amount** — this is an ordinary unparsed
message and uses the same text as 7.9:

> Не нашёл сумму в сообщении.
> Напишите так: `такси 25 тысяч` или `продукты 200 тыс с карты`

**Counters:** both failure paths spend the unparsed counter, exactly like text.
Voice costs more in money, but a second ceiling cannot be explained to a person.
There is no separate voice limit.

### Acceptance

1. Send a clear voice message describing one expense. The typing indicator
   appears immediately and is replaced by an ordinary card.
2. Confirm the transcription text appears nowhere in the chat.
3. Send a voice message with a description but no amount — the 7.9 text
   appears.
4. Send silence or noise — the "не разобрал голосовое" text appears.
5. Send a voice message containing three operations. Three cards arrive, and
   the quota of 50 drops by 1, not by 3.

---

## 10. Receipt photo

**Not a launch condition.** Same standing as voice input.

The person sends the bot a photograph of a receipt; the bot creates a record
and replies with an ordinary card with ordinary buttons.

### 10.1 Rules

**One receipt equals one operation for its total amount.** Line-by-line parsing
is out of scope: a receipt may hold twenty lines, the per-message operation
limit is five, and each line would carry its own category. The family needs the
size of the shopping trip, not its contents.

- **Category** is determined from the merchant name and the visible contents.
- **Wallet** is the default wallet.
- **Date** is taken from the receipt when it is legible and within 31 days;
  otherwise today.
- **Comment** is the merchant name.

**A caption sent with the photo is read together with the receipt and takes
priority.** If the caption says "с наличных", that wallet wins over the default
one.

**Several photos.** Telegram delivers an album as separate messages, so each
photo is its own model call and its own card. No special rule is needed.

**While parsing runs — the standard Telegram typing indicator**, same as voice.

**Timeout: 20 seconds per attempt**, double the text timeout, because the image
must be uploaded. Retry rules from 7.12 otherwise apply unchanged.

**Counters.** The quota of 50 is spent per photo. An unreadable photo spends the
unparsed counter.

One failure text covers every case — crumpled receipt, darkness, not a receipt
at all:

> Не разобрал чек. Сфотографируйте его целиком при хорошем свете или запишите
> сумму текстом.

### 10.2 Known unknown — must be measured before this ships

The selected parser was validated on 101 text phrases. **It has never been
measured on images.** Quality on Uzbek thermal-paper receipts, latency, and the
cost of one call with an image attached are all unknown. An image is billed as
input tokens on top of the instructions and the text tail, so the per-call cost
is certainly higher than for text — by how much is not known.

**Acceptance test before release: 20 real receipts photographed by the
customer, threshold 18 of 20 on the total amount.** The amount is the critical
field; merchant and category are soft fields and may miss.

### Acceptance

1. Photograph a receipt and send it. The typing indicator appears, then an
   ordinary card with the total amount, a category, the default wallet, and the
   merchant name as the comment.
2. Send the same photo with the caption `с наличных`. The card shows the cash
   wallet instead of the default one.
3. Send a photo of something that is not a receipt. The 10.1 failure text
   appears, no record is created, and the unparsed counter increases by 1.
4. Send a receipt dated two months ago. The record carries today's date, not
   the receipt date.
5. Send three receipt photos as one album. Three separate cards arrive and the
   quota drops by 3.
6. **Threshold run:** 20 real receipts, at least 18 producing the correct total
   amount. Performed by the customer — see section 22.

---

## 11. Personal wallets

A new visibility model. Until now every wallet was shared.

**Rules.**

- Operations on a shared wallet are visible to every member.
- Operations on a personal wallet are visible **only to its holder**, including
  invisibility to the budget owner.
- **Personal spending does not participate in shared analytics** at all.
- Each member creates their own personal wallets; only the owner creates shared
  ones.
- Limit: 5 personal wallets per person, 10 shared per family.

**Home screen consequence.** The three figures at the top of the home screen —
`Доход`, `Расход`, `Остаток` — are computed from **shared wallets only**.
This figure must be identical for every member: it is the one number the family
says out loud.

**A `Мои личные` block appears at the bottom of the home screen** when the
person has at least **one personal wallet**. Existing operations are not
required — otherwise the money disappears from the screen exactly when it is
not being touched. It carries the same three figures, visually subordinate to
the top block.

**Both blocks must carry headings.** Two visually identical `Остаток` blocks on
one screen read as a product defect.

**Currency switch interaction.** The home screen currency switch (UZS/USD)
applies to both blocks identically. The `Мои личные` block is shown only when
the person has at least one personal wallet **in the selected currency**, and
its figures cover only wallets of that currency.

**Accepted cost:** spending from a personal wallet is reflected in the shared
figures nowhere. A person sees their own personal money in this block, in the
wallet list, and in History.

### Acceptance

1. As member A, create a personal wallet and record an expense on it.
2. As the **owner** (a different person), check the home screen, analytics,
   History, wallet list, and settings. A's personal wallet and its operation
   appear in none of them.
3. As member A, confirm the `Мои личные` block appears on the home screen and
   its figures include that expense, while the top block's figures do not.
4. As member A, delete every operation on the personal wallet but keep the
   wallet. The block is still shown.
5. As member A, delete the personal wallet entirely. The block disappears.
6. With only a UZS personal wallet, switch the home screen to USD. The
   `Мои личные` block disappears rather than showing a sum figure under a USD
   heading.
7. Confirm both home-screen blocks carry headings and are visually
   distinguishable.

---

## 12. Goals

A goal is an **optional property of a shared wallet**, not a separate entity.
Putting money aside is an ordinary transfer. One wallet holds at most one
active goal. **Goals are shared only** — there are no personal goals. There is
no separate goal limit; it is bounded by the shared wallet limit.

### 12.1 The Goals section

Two tabs: `В процессе` and `Достигнутые`.

Form fields: wallet (required), target amount (required), name (optional —
defaults to the wallet name), deadline (optional). **Currency equals the
wallet's currency** and is not selectable.

### 12.2 Progress

Progress = wallet balance ÷ target × 100, computed from the real balance and
**capped at 100% for display**. When setting or editing a deadline, the
earliest allowed date is today — a backdated deadline is rejected. A
deadline that later passes while the goal stays open is a label only, not a
block; the date remains editable at any time.

When the balance exceeds the target, the line "осталось накопить" is replaced:

> Накоплено на 200 000 сум больше

At exactly 100% there is no such line.

### 12.3 Reaching the goal

A message goes **to every member**. The card does not move on its own,
accumulation continues:

> 🎯 Цель «Ремонт» достигнута
> Накоплено 8 200 000 сум из 8 000 000
>
> [Закрыть цель]

**One button, shown to the owner only.** There is no `Оставить` button — a
button that does nothing is a lie.

**Only the owner can close a goal.** There is no auto-close. If nobody
responds, the goal stays active indefinitely. A repeat message is sent only
after the balance falls below 100% and crosses it again.

### 12.4 Closing

The card moves to `Достигнутые`, its figures freeze, the percentage disappears,
no money moves, and the wallet becomes free for a new goal. An entry in
`Достигнутые` does not occupy a wallet slot. **There is no way back.**

### 12.5 Elsewhere in the product

A wallet carrying a goal appears in quick-entry wallet selection like any
other, can be set as the default wallet without restriction, and is marked as
carrying a goal **only in settings**.

Goal progress is never shown on a quick-entry card.

### Acceptance

1. As the owner, create a goal on a shared wallet with a target and no name.
   The goal is named after the wallet.
2. As a member, confirm the goal creation control is absent.
3. Transfer money into the wallet until the target is crossed. Every member
   receives the achievement message; only the owner sees `[Закрыть цель]`.
4. Confirm the goal card stays in `В процессе` and progress displays as 100%,
   with "Накоплено на … больше" replacing "осталось накопить".
5. Transfer money out, dropping below the target, then back above it. A second
   achievement message arrives. Confirm no message arrives while the balance
   stays above the target.
6. Close the goal as the owner. It moves to `Достигнутые`, shows frozen
   figures, no percentage, and no return control. Wallet balances are unchanged.
7. Create a new goal on the same wallet — allowed, since the previous one is
   closed.
8. Attempt to set a deadline before today, on creation and on edit. It is
   rejected; the earliest date accepted is today.
9. Create a goal with a deadline that later passes while the goal is still
   open (balance under target). The card shows a passed-deadline label
   only — it does not block progress, closing, or further edits, and the
   date remains editable at any time.

---

## 13. Members — full lifecycle

Membership management returns to the interface: list, invitation link, link
reissue, removal, self-exit, and ownership transfer.

### 13.1 Invitation link

**One permanent, reusable link per family.** It does not expire. Reissuing it
invalidates the previous link immediately. The natural ceiling is the 4-member
limit, so a separate expiry only produces a refusal at the moment the invited
person finally opens the link.

Refusal texts:

Link no longer valid (reissued):

> Эта ссылка-приглашение больше не действует. Попросите новую у того, кто вас
> пригласил.

Family already full:

> В этом семейном бюджете уже 4 участника — это предел.

Already a member of this family:

> Вы уже участник бюджета «Семья Юсуповых».

### 13.2 Joining while owning a budget

Allowed with explicit confirmation. **Forbidden if the person's own budget has
other members** — that budget would be left without an owner:

> Нельзя присоединиться к другой семье, пока в вашем бюджете есть участники.
> Передайте права владения одному из них или удалите участников, затем
> попробуйте снова.

Confirmation prompt before joining:

> Вы присоединяетесь к бюджету «Семья Юсуповых». Ваши кошельки и операции по
> ним станут вашими личными в этой семье, ваш бюджет закроется.
>
> [Присоединиться] [Отмена]

**Everything the person brings becomes personal.** Wallets from the old budget
become **personal wallets** in the new family; their operations travel with
them. The old budget is closed.

**Why:** family figures for past months must not change because a new person
arrived. A wife who looked at July analytics must see the same July in August.
Merging his wallets into the shared pool would rewrite other people's past and
expose his old spending to everyone.

**Goals on his wallets disappear.** A goal lives only on a shared wallet.

**Categories are rematched by their translation key.** Seeded categories match
automatically; categories he invented himself move to the service value
"Без категории". Personal operations never enter shared analytics, so the loss
is limited to reading History.

**Personal wallet limit is 5; he may bring up to 15.** Excess is deleted by him
before joining:

> В новой семье ваши кошельки станут личными, а личных можно иметь не больше 5.
> Сейчас у вас 12 — удалите лишние и попробуйте снова.

The number is substituted. This check runs **before** the confirmation prompt.

### 13.3 Removal and self-exit — one mechanism

Removal by the owner and voluntary exit are the same operation with two
different notification texts. Exit is a settings button with confirmation and
takes effect immediately. **The owner has no exit button** and must transfer
ownership first.

**The removed person automatically becomes the owner of their own budget.**

- **Personal wallets always follow the person**, together with their operations
  and the categories those operations used.
- **Operations on shared wallets stay in the old family**, together with the
  author's name. Not a single figure changes in the old family.

**What the person sees in the auto-created budget:** if at least one personal
wallet came with them, no wallets are seeded; if none came, the standard four
are seeded. Categories are seeded **always** — duplicates cannot occur because
matching is by translation key.

**Default wallet resolution** (this is the case where a default wallet is left
pointing at something invisible):

- After leaving or removal: the default becomes the oldest personal wallet the
  person brought; if none was brought, it becomes "Карта сум" from the seeded
  four.
- After joining another family: the person's previous default wallet is kept —
  it travelled along as a personal wallet.
- When the owner deletes a shared wallet that was someone's default: that
  person's default moves to the oldest shared wallet in the family, silently,
  with no message.

Notification to a **removed** person — the remover is never named, because the
owner is the only person who could have done it and naming them turns a notice
into an accusation:

> Вы больше не участник семейного бюджета «Семья Каримовых».
>
> Ваши личные кошельки и операции по ним перешли в ваш собственный бюджет —
> вы теперь его владелец.

Notification to a person who **left voluntarily** — only the first line differs,
since they already know they left:

> Вы вышли из бюджета «Семья Каримовых».
>
> Ваши личные кошельки и операции по ним перешли в ваш собственный бюджет —
> вы теперь его владелец.

### 13.4 Departed members in history

**If History contains operations by departed people, authorship is shown
regardless of the current member count.** Departed people are labelled with one
formulation, identical for removal and voluntary exit, so the line never reads
as a judgement of anyone's behaviour:

> Рустам (бывший участник)

The same label appears in the per-person breakdown in analytics.

### 13.5 Ownership transfer

Only to an active member of the same family. The recipient confirms.
The former owner becomes an ordinary member. **Irreversible unilaterally.**

To the recipient:

> Вас предлагают сделать владельцем бюджета «Семья Каримовых».
>
> Владелец распоряжается общими кошельками, категориями и участниками.
> Прежний владелец останется обычным участником.
>
> [Принять] [Отказаться]

To the former owner after acceptance:

> Рустам теперь владелец бюджета «Семья Каримовых». Вы остались участником.

To the former owner after refusal:

> Рустам отказался стать владельцем.

To the remaining members, so they know whom to approach about shared wallets:

> Рустам теперь владелец бюджета «Семья Каримовых».

### Acceptance

1. As the owner, open the invitation link, invite a second person, and confirm
   they receive the invited-person `/start` text from section 18.2.
2. Reissue the link, then open the old link. The "больше не действует" text
   appears.
3. Fill the family to 4 people and open the link as a fifth. The "уже 4
   участника" text appears.
4. Open the link as an existing member. The "Вы уже участник" text appears.
5. From a budget that has other members, open someone else's link. The refusal
   from 13.2 appears and nothing changes.
6. From a solo budget with 2 wallets and operations, open someone else's link.
   The confirmation prompt appears; accept it. In the new family those wallets
   are **personal**, their operations came along, the old budget is gone, and
   the other members see none of it.
7. Repeat step 6 from a solo budget holding 12 wallets. The 13.2 limit text
   appears with the number 12 and joining is blocked until wallets are deleted.
8. Remove a member who has one personal wallet with operations and several
   operations on shared wallets. Verify: the removed person receives the 13.3
   text; their personal wallet and its operations are in their new budget; the
   shared-wallet operations remain in the old family under their name; every
   figure in the old family is unchanged; their new budget was not seeded with
   the standard four wallets.
9. Remove a member who has **no** personal wallets. Their new budget contains
   the standard four seeded wallets, and their default wallet is "Карта сум".
10. In the old family, open History and analytics. The departed person's name
    is shown as `Рустам (бывший участник)` in both.
11. As a member, use the settings exit button. The 13.3 voluntary-exit text
    arrives, differing from step 8 only in the first line.
12. Confirm the owner has no exit button anywhere.
13. Transfer ownership. The recipient sees the confirmation, and after
    acceptance the former owner and every remaining member receive their
    respective texts. Verify the former owner has lost owner-only controls and
    the new owner has gained them.
14. Refuse a transfer as the recipient — the former owner is notified and keeps
    ownership.
15. As the owner, delete a shared wallet that is another member's default. That
    member's next quick-entry message lands in the oldest shared wallet, and no
    message about the change was sent.

---

## 14. Editing others' operations and the change log

### 14.1 The right

Any member edits and deletes any operation on a **shared** wallet. Operations on
personal wallets remain editable only by their holder.

Entry moved into the chat, so mistakes are visible to the whole family the
moment they appear; forbidding correction would turn other people's typos into
the owner's chore. There is nothing to hide — shared operations are already
visible to everyone, including the per-person breakdown in analytics.

**Authorship does not change on edit.**

### 14.2 The `Изменения` block

Opening an operation in History shows a block titled **`Изменения`**: who
created it and when, and what changed afterwards.

**One line per changed field.** Unchanged fields are not mentioned at all. A
single edit touching three fields produces three lines under one date, so it
reads as a list rather than a paragraph:

> **Изменения**
> 1 августа · создал Рустам
> 2 августа · Дилноза: сумма 20 000 → 200 000
> 2 августа · Дилноза: категория Продукты → Такси

**Every edit is logged** — one's own and other people's, on shared wallets and
on personal ones.

**Fields logged:** amount, category, wallet, date, comment. For a transfer or
an exchange: amount, source wallet, destination wallet, rate, date, comment.

**Operation type is not editable at all.** An expense cannot be turned into
income; the record is deleted and created anew instead. Editing the type would
flip two balances at once, and a log line reading "тип: расход → доход" would
not explain what happened to the money.

**Old values are stored as text as of the moment of the edit.** Otherwise a
line would show the current name of a renamed wallet instead of what was
actually there. Long values are truncated with an ellipsis, as everywhere.

**Deletion is not logged** — a deleted operation cannot be opened in History,
so there is nowhere to show the event. **There is no revert to a previous
value.**

The block is absent entirely until the first edit.

### Acceptance

1. As member A, create an operation on a shared wallet. As member B, open it in
   History and edit the amount. The edit succeeds.
2. Confirm History still shows **A** as the author, not B.
3. Open the operation: the `Изменения` block shows a creation line naming A and
   one change line naming B.
4. Edit three fields at once. Three lines appear under one date, and unchanged
   fields are not mentioned.
5. Rename the wallet used in a logged change. The old log line still shows the
   name as it was at the time of the edit.
6. Open an operation that has never been edited — the block is absent entirely,
   not empty.
7. Confirm no control exists to change an operation's type.
8. Delete an operation and confirm it cannot be opened in History at all.
9. As member B, attempt to reach member A's personal-wallet operation. It is
   not visible anywhere.

---

## 15. Category set

### 15.1 Expenses — 7 parents, 23 subcategories

| Parent | Subcategories |
|---|---|
| Еда | Продукты · Кафе и рестораны · Доставка |
| Транспорт | Такси · Топливо · Общественный транспорт · Обслуживание авто |
| Дом | Аренда · Коммунальные услуги · Связь и интернет · Ремонт и обустройство |
| Дети | Садик и школа · Кружки и репетиторы · Детские товары |
| Здоровье | Лекарства и аптека · Врачи и клиники · Стоматология |
| События и тои | Тои и маърака · Подарки |
| Покупки и досуг | Одежда · Развлечения · Подписки · Красота и уход |

**"События и тои" is mandatory and must not be dropped** — it is the category
that differentiates the product from the competitor.

**A subcategory is optional when recording an expense.** A record may carry only
a parent.

### 15.2 Income — 5, flat, no subcategories

Зарплата · Подработка · Подарки · Переводы от родных · Прочее.

### 15.3 Service values

- **"Без категории"** — used when the type was chosen by button but no category
  was present in the text. It is not a real category: it occupies no slot, is
  not created, deleted or renamed, and does not appear in the category picker
  during manual entry. It is visible on the quick-entry card and in History; in
  analytics it falls into the "Другое" roll-up.
- **"Другое"** — the analytics roll-up for everything beyond 8 colours, for both
  parents and subcategories. It never appears on an operation record.

**Name collision, resolved deliberately:** the expense parent is named
"Покупки и досуг", not "Прочее"; the analytics roll-up is named "Другое"; the
word "Прочее" survives only as an income category and collides with nothing.

**"Подарки" collision:** income "Подарки" and the expense subcategory "Подарки"
under "События и тои" are different categories, resolved by the button the
person taps (7.6).

### 15.4 Soft-deleted categories

A deleted category **occupies no slot**. In analytics for past periods it is
shown **like any other: its own name, its own colour, no marker**. The past is
not rewritten — March after a deletion looks exactly as March looked in March.

Three consequences, accepted as a package:

1. **Colour is bound to a category permanently** and never assigned by list
   position. Assignment rules for new categories are in section 5.
2. A deleted category **appears nowhere it could be picked** — not in the
   operation form, not in filters. Only where already-recorded data is shown:
   analytics, History, the operation card.
3. **There is no restore.** A category with the same name is a new entity with a
   new colour, and old operations do not attach to it. There is no restore
   control in the interface.

### 15.5 Existing families — no migration

Families that already exist **stay on the old category set.** The new set is
seeded to new budgets only. Operations are not moved and no mapping table is
written.

**"Прочее" is not auto-renamed to "Покупки и досуг"**, not even as a special
case: the category may have been renamed by hand, and if it was not, it holds
operations that genuinely are miscellaneous.

**Seeding missing categories on top of the old set is rejected on arithmetic:**
the family would exceed 8 parents on day one.

**Accepted cost:** existing families never see the new categories, and the
special handling of "Покупки и досуг" in the weekly digest does not fire for
them, since they have no such category.

> **Open item for the customer, not the implementer.** This decision holds while
> the number of live families is small. If that number grows materially before
> release, the decision is re-examined.

### Acceptance

1. Create a new budget through `/start`. It is seeded with exactly 7 parent
   expense categories and 23 subcategories matching 15.1, and exactly 5 income
   categories matching 15.2.
2. Confirm "События и тои" is present with both its subcategories.
3. Record an expense choosing only a parent, no subcategory. The record is
   created and History shows the parent name.
4. Take an existing budget created before this release. Its category set is
   unchanged, "Прочее" is still named "Прочее", and no new categories appeared.
5. Delete a category that has operations in a past month. Open analytics for
   that month: the category is still shown with its own name and colour and no
   marker.
6. Open the operation form and a History filter: the deleted category is offered
   in neither.
7. Confirm no restore control exists anywhere.
8. Create a category with the same name as the deleted one. It is a separate
   entity with a different colour, and the old operations did not attach to it.

---

## 16. Notifications

Three messages, two switches.

### 16.1 Evening reminder

Sent **only if the family recorded nothing that day**, at 21:00 Tashkent time,
evaluated per family.

**Records on personal wallets count as activity.** If anyone recorded anything,
even to a personal wallet, the family stays silent. Otherwise a person who has
just been keeping records receives "сегодня не было ни одной записи" — a direct
falsehood addressed to them. Nothing leaks: the others see the bot's silence,
not someone else's operation.

**Accepted cost:** three people record nothing, the fourth buys coffee with a
personal card, and nobody receives the reminder.

> Сегодня не было ни одной записи.
> Напишите трату одной строкой — например, `продукты 150 тысяч`

No question, no reproach. Sent to every member, not only the owner.

### 16.2 Weekly digest

Monday, 10:00 Tashkent time.

- **Expenses — one line per currency** in which spending occurred. Cross-rate
  consolidation does not exist in this product.
- **Top category of the week** — separate per currency line. Level is the
  parent; **if "Покупки и досуг" wins, its largest subcategory is shown
  instead**, because the parent name carries no information.
- **Comparison with last week** — separate per currency line, **in money, not
  in percent** (percentages lie on small bases). If last week was empty in that
  currency, the comparison line is omitted.
- **Goal** — exactly one: the goal that received the most this week. If nothing
  was set aside, or there are no goals, the line is omitted. There is no
  invitation to create a goal.
- **Income is not included.**
- **Personal spending is not included** — the digest is the one text all four
  people read, and it must be identical for everyone.

Order: currency blocks (UZS first), each holding total, delta, leader. The goal
is a separate block at the end.

> **Итоги недели**
>
> Расходы: 2 350 000 сум
> На 300 000 сум больше, чем на прошлой неделе
> Больше всего — Еда, 940 000 сум
>
> Расходы: 120 $
> На 40 $ меньше, чем на прошлой неделе
> Больше всего — Дом, 90 $
>
> Цель «Ремонт»: отложили 500 000 сум, накоплено 3 500 000 из 8 000 000

As the last line, unclosed achieved goals, **to the owner only**, one line each:

> Цель «Ремонт» достигнута — можно закрыть в разделе «Цели»

### 16.3 Goal achievement

Event-driven, to every member. Text and button rules in 12.3.

### 16.4 Switches

Two independent toggles in settings: the evening reminder and the weekly digest.
The goal achievement message has no switch. Three identical daily reminders (the
competitor's pattern) are rejected.

### Acceptance

1. Record nothing all day. At 21:00 Tashkent time every member receives the
   16.1 text.
2. Record one operation to a **personal** wallet during the day. No reminder
   arrives to anyone that evening.
3. Spend in both currencies during a week, then check Monday's digest: two
   currency blocks, UZS first, each with total, money delta, and leader.
4. Make last week empty in USD — the USD comparison line is absent while the
   block itself is present.
5. Arrange for "Покупки и досуг" to be the top category — the digest shows its
   largest subcategory instead of the parent name.
6. Record income during the week — it does not appear in the digest.
7. Record personal spending during the week — it does not appear in the digest,
   and the totals match what other members see.
8. Leave an achieved goal unclosed — only the owner sees the trailing line.
9. Turn off each switch separately and confirm the corresponding message stops
   arriving while the other continues.

---

## 17. Mini application

### 17.1 Bottom menu

**`Главная` · `Аналитика` · `Цели` · `Настройки`.** Four items, no fifth. There
is no separate History tab — Goals took its place. There is no centre action
button and no floating "+".

### 17.2 Home

Top to bottom: budget name, month switch, currency switch UZS/USD, three
figures (`Доход`, `Расход`, `Остаток`), three action buttons (`Доход`,
`Расход`, `Перевод`), recent operations block.

**The heading is the budget name**, not "Мои финансы" — the budget is a family
one and its name already appears in bot texts.

Figures and the `Мои личные` block behave as specified in section 11.

### 17.3 History

No menu tab. **Two entrances into the same screen:**

- the heading of the recent operations block on Home is a link;
- the second tab inside `Аналитика`.

**Back returns where the person came from.** Opened from Home — back goes Home,
not to the charts tab.

**Entered from the chart drill-down** (17.5 step 3): back returns to the charts
tab at the **second level** — the subcategory chart of the same parent — and the
History filter is cleared. Manual tab switching does the same. The period filter
is never reset by any of these transitions.

### 17.4 Analytics — two tabs

Tab names are **`Графики` and `История`**. The tab is not called "Аналитика":
a tab of the same name inside a section of the same name does not read.

**The period filter is shared by both tabs.** Switching tabs does not reset it.

**Currency switch UZS/USD.** The `Графики` tab carries a currency switch,
identical in appearance to the one on Home. The design does not show this
control on this screen; it is an approved deviation, not an invention.

It is a filter, never a conversion. `UZS` counts operations on UZS wallets
only, `USD` on USD wallets only. No amount is converted anywhere, in line
with section 5. The prototype renders its USD state by dividing UZS figures
by a fixed rate — that is a prototype shortcut and must not be reproduced.

The switch governs the `Графики` tab only. `История` always lists every
operation, each in its own currency, and is never filtered by it.

### 17.5 Charts tab
**Expense chart — a two-step ladder.**
1. **Parent categories** — donut, legend, up to 8 colours plus "Другое".
2. **Tapping a sector or a legend row** rebuilds the same chart into the
   subcategories of that parent. The heading becomes the category name with a
   back control, the category total sits under it, and shares are computed
   **inside the category**, not against all expenses.
3. **Tapping a subcategory** opens the `История` tab, filtered by that
   subcategory and the same period.

**Boundaries:** the service "Другое" does not expand — tapping it does nothing.
Nothing exists below the second level.

**Accepted cost:** reaching History for a whole parent category in one gesture
is not possible — only through a subcategory.

**Three further blocks sit below the donut, in this order.**
1. `Доход и расход, 12 месяцев` — twelve pairs of bars, income and expense,
   one pair per month. The block obeys the month switch: it ends with the
   selected month and reaches eleven months back. Selecting March 2026 shows
   April 2025 through March 2026. Unit label on the right: `млн сум` in UZS,
   `$` in USD with no scaling — thousands of dollars are shown as they are.
2. Two tiles side by side. `Средний расход в день` — the expense of the
   selected month divided by the days already elapsed in it: the full length
   for a finished month, the 1st through today (Tashkent) for the current one.
   The caption reads `сум · 31 день`, and the number changes with the month
   in correct Russian plural — `1 день`, `3 дня`, `31 день`.
   `Самый дорогой день` — the weekday whose average expense is highest,
   shown as `Сб`, with the caption `в среднем 512 000 сум` carrying that
   weekday's own average.
3. `Расход по дням недели` — seven bars, Monday through Sunday, the average
   expense of each weekday within the selected month.

All three cover shared wallets only. Personal wallets never enter analytics,
per section 11.

The three blocks appear and disappear together with the donut: the empty-month
state replaces the whole tab, not the donut alone.

**A month's figures are never shown under another month's heading.** Paging
quickly through months must not leave the screen displaying data that belongs
to a month other than the selected one, at any moment.

### 17.6 Settings — a table of contents

**Was:** every entity in one endless list on a single screen. That is the
problem this redesign exists to solve.

**Now:** a contents screen listing sections, one per entity. A row shows an
icon, a name, and a short subtitle. Tapping opens that entity's own screen.

Sections in this order, ordered by frequency of use:

| # | Section | Subtitle |
|---|---|---|
| 1 | `Кошельки` | `4 общих · 2 личных` |
| 2 | `Кошелёк по умолчанию` | name of the selected wallet |
| 3 | `Категории доходов` | `5 категорий` |
| 4 | `Категории расходов` | `7 родительских · 23 подкатегории` |
| 5 | `Участники` | `2 из 4` |
| 6 | `Уведомления` | enabled ones listed: `Напоминание вечером · Итоги недели`; both off: `Выключены` |
| 7 | `Язык` | `Русский` or `Oʻzbekcha` |

`Язык` sits last: it is touched once in a lifetime.

Inside `Кошельки`, shared and personal are explicitly separated. Inside
`Участники` live the list, the invitation link, ownership transfer, and exit.
`Уведомления` holds the two independent switches from 16.4.

**The delete control does not sit in a list row.** Today `Удалить` appears in
every row, and a mistyped tap costs a deleted category together with its
analytics breakdown. Deletion moves behind a swipe or onto the entity's own
screen.

### 17.7 Forms

All forms are modal bottom sheets.

**Income and expense form**, top to bottom: amount (currency shown as a label,
taken from the wallet, not separately selectable); category (a row that opens a
picker — for expenses shows `Родитель · Подкатегория`, subcategory optional);
wallet (a row that opens a picker, prefilled with the default wallet); date
(today by default); comment (up to 200 characters); `Сохранить`.

The **category picker** is its own screen: a list of parents, expandable into
subcategories, with the option to stop at the parent.

**Transfer and exchange — one form, two states.** Fields: `Откуда`, `Куда`,
`Сумма`, `Дата`, `Комментарий`.

- Currencies match — there is no rate field at all.
- Currencies differ — a `Курс` field appears, and under it a result line
  (`100 $ → 1 280 000 сум`). The result line is mandatory: without it an error
  in the rate is invisible.

**Editing a record from History** — the same form plus two differences: a
secondary-styled `Удалить` button at the bottom (not in a row), and the
`Изменения` block below the fields, per section 14.2.

**Entity forms in settings:** wallet (name 30 characters, currency UZS/USD);
expense category (name 30 characters — when creating a subcategory the parent
is already fixed by the screen it was opened from); a subcategory screen inside
each parent with list, add and delete; one shared delete-confirmation sheet for
all entities.

### 17.8 Design rules

- Colours come from the Telegram theme; light and dark are equal.
- Sum amounts of 7–9 digits are the governing typographic constraint.
- Green and red mean only income and expense.
- Exactly 8 category colours; colour is bound to the category permanently.
- Long names truncate with an ellipsis, never wrap.
- No glass effects, neumorphism, neon gradients, mascots, or emoji used as
  icons.
- Density beats whitespace: the balance is visible without scrolling.

**Mandatory states for every screen:** empty lists, loading skeletons, the
failed-entry screen, limit messages, and a maximum-length category name.

### Acceptance

1. Confirm the bottom menu has exactly four items and no floating button.
2. Confirm the Home heading is the budget name.
3. Open History from the Home block heading, then press back — Home appears, not
   the charts tab.
4. In `Аналитика`, set a period on `Графики`, switch to `История` — the period
   is retained.
5. Tap a chart sector: the chart rebuilds into subcategories, the heading shows
   the category name with a back control, the category total appears, and the
   shares add up to 100% within the category.
6. Tap a subcategory: `История` opens filtered by that subcategory and the same
   period. Press back: the subcategory chart appears again and the filter is
   cleared.
7. Tap "Другое" on the chart — nothing happens.
8. On `Графики`, switch the currency to `USD`: the donut, the twelve-month
   block and both tiles recount on USD wallets only, and no figure equals a
   UZS figure divided by a rate. Switch to `История` — operations of both
   currencies are listed there regardless of the switch.
9. Page back three months and read the twelve-month block: it ends with the
   month named at the top, not with the current month.
10. Page quickly through six months back and forth, then stop and wait two
    seconds. The figures on screen belong to the month named at the top.
11. Open `Настройки`: seven rows in the order of 17.6, each with the subtitle
   specified. Turn both notification switches off and confirm the subtitle
   reads `Выключены`.
12. Confirm no list row contains a delete control; deletion is reached by swipe
   or from the entity screen, and asks for confirmation.
13. Open the expense form: currency is shown as a label and cannot be picked
    separately; the wallet is prefilled with the default wallet; a record can be
    saved with a parent category and no subcategory.
14. Open the transfer form with two same-currency wallets — no rate field. Switch
    the destination to a different currency — the rate field and the result line
    appear.
15. Create a category with a 30-character name and view it on the settings
    screen, the chart legend, and a History row: truncated with an ellipsis in
    all three, never wrapped.
16. Open every screen with no data at all: each shows an empty state, not a
    blank area.
---

## 18. Bot texts outside quick entry

### 18.1 `/start` — new text

The greeting opens with entry, not with the application: the person will open
the app anyway because the button is in plain sight, whereas entry by message
loses the competition for attention if it comes second.

> Chontak — семейный бюджет.
>
> Записывайте траты прямо здесь, сообщением:
> `такси 25 тысяч`
>
> Кошельки, категории и аналитика — в приложении.

### 18.2 `/start` for a person arriving by invitation link

A different text: the first thing they must learn is which family they landed
in.

> Вы присоединились к бюджету «Семья Юсуповых».
> Всё, что вы запишете, увидят остальные участники.
>
> Записывайте траты прямо здесь, сообщением:
> `такси 25 тысяч`
>
> Кошельки, цели и аналитика — в приложении.

**The two texts cannot be merged.** The visibility line is false for a solo user
— they have no other members, and would conclude someone is watching them. The
inviter's name is not included, and personal wallets are not explained here.

### 18.3 Persistent keyboard in the bot chat

**One button — launch the application.** The BotFather menu button stays as
well; the duplication is deliberate, because people do not find the menu.

No further buttons. The reply keyboard pushes the input field down, and in
MVP 2 the input field is the product's main instrument.

**The `/menu` command is not built.** It existed for people who registered
before the keyboard appeared, and the release announcement carries the keyboard
to every existing user.

### 18.4 Release announcement to existing families

Sent **once to every existing user** at release, including those who never open
the application. New users do not receive it — `/start` tells them the same
thing.

Content is **one working instruction, not a changelog**:

> Теперь трату можно записать прямо здесь, сообщением.
> Напишите, например: `такси 25 тысяч`
>
> В приложении появились личные кошельки, цели и управление участниками.

### Acceptance

1. Send `/start` from a fresh account. The 18.1 text arrives verbatim and the
   keyboard with the single launch button appears.
2. Join via invitation link and send `/start`. The 18.2 text arrives, differing
   only in the first two lines.
3. Confirm `/menu` does not exist as a command.
4. Trigger the release announcement and confirm it arrives once to an existing
   user and never to a newly registered one.

---

## 19. Limit messages

### 19.1 In the application

One template: **the limit as a number, plus what to do.** The number is
mandatory — without it the person cannot tell a product limit from a
malfunction and taps the button again.

> Больше 10 общих кошельков создать нельзя. Удалите ненужный — место
> освободится.

> Больше 5 личных кошельков создать нельзя. Удалите ненужный — место
> освободится.

> Больше 8 категорий расходов создать нельзя. Удалите ненужную — место
> освободится.

> В категории «Еда» уже 8 подкатегорий — это предел. Удалите ненужную, чтобы
> добавить новую.

Members are the **only case without the second sentence** — "удалите участника"
in a hint reads as advice to throw a person out, and the owner knows where the
control is:

> В семейном бюджете уже 4 участника — это предел.

### 19.2 In the chat

Daily model-call limit:

> Сегодня записано 50 операций — это дневной предел на семью. Новые записи
> можно вносить с полуночи.

**This limit applies to quick entry only.** Manual entry in the application is
unrestricted because it makes no model call and costs nothing. **The
application is deliberately not mentioned here** — pointing at it would be
publishing the workaround.

Daily unparsed limit:

> Сегодня не удалось разобрать 20 сообщений — это дневной предел. Записи
> можно добавить в приложении.

Here pointing at the application is **mandatory** — the person recorded nothing
and would otherwise be left with no way out.

Message length:

> Сообщение слишком длинное — максимум 500 символов. Разбейте на несколько.

### Acceptance

1. Reach each limit in turn and compare the message to the text above,
   character for character.
2. After hitting the 50 limit, record an operation manually in the application —
   it succeeds.
3. Confirm the 50-limit message does not mention the application, and the
   20-limit message does.

---

## 20. Prompt caching — removed

**The parsing prompt is NOT cached on the provider side.** Every call sends
the static instructions in full as `systemInstruction`. Nothing in the
product may create, extend or reference a Google `cachedContent` resource.

This section previously mandated one permanent explicit cache and estimated
its cost at about $1.73 per month. **That estimate was wrong by more than an
order of magnitude**, and the mistake was paid for in real money: the August
2026 bill shows $18.14 of a $20.53 total consumed by the SKU
`Generate content cached content storage token hours` — 18,142,224 token
hours at $1 per million. Storage is billed **per hour of existence,
regardless of traffic**; a cache that no one queries costs exactly as much as
a busy one.

The cause was structural, not accidental. Gemini enforces a minimum cache
size (~4096 tokens); the static instructions are about 1,100 tokens, so the
implementation padded them with roughly 68,000 tokens of inert filler purely
to clear the minimum. The installation then paid to store that filler around
the clock, with a 7-day TTL extended on every successful call — a cache that
never expired.

**The arithmetic that settles it**, derived from the same bill: cached input
tokens cost $0.025 per million against $0.25 per million for ordinary input,
so caching saves about $0.00018 per parse. A minimum-size cache costs about
$3.00 per month to store. Break-even is roughly **17,000 parses per month —
about 560 messages per day**. At the volume of a family budget bot, caching
costs several times more than it saves.

**Two requirements survive, unchanged and still mandatory:**

1. **The static part is fixed text.** Value substitution is allowed only in
   the variable tail. Assembling the prompt on the fly and conditional
   fragments ("if the family has a foreign-currency wallet, add a paragraph")
   are forbidden.
2. **The static part contains no family data** — no wallet names, no date, no
   message text, no person's name.

### Acceptance

1. No request to the provider carries a `cachedContent` field, for text,
   audio and receipt-image turns alike.
2. No request is ever made to the provider's cache endpoint
   (`/cachedContents`).
3. The static instructions carry no filler: no ballast text, and the static
   part stays under 8,000 characters.
4. Confirm no family-specific value (wallet name, date, member name, message
   text) appears in the static part.

**If caching is ever reconsidered**, redo the break-even calculation against
the then-current prices and the then-current message volume, and set a
billing budget alert before switching it on. Do not reintroduce it on the
strength of a remembered price.

---

## 21. What the product does NOT have

Stated plainly so that no one builds it.

**Money and payments**
- No paid plans, no prices, no payment buttons, no in-product purchases. MVP 2
  is entirely free.
- No referral programme, no prize draws.

**Automation**
- No bank integration, no automatic transaction import, no SMS parsing.
- **No automatic currency conversion anywhere.** A rate is entered by a person,
  inside an exchange operation only.
- No offline mode.

**Accounting features**
- No debts and no loans.
- No budget limits or spending caps per category.
- No receipt line-item breakdown — one receipt equals one operation (10.1).
- No PDF or Excel export, no reports beyond the in-app analytics.
- No recurring or scheduled operations.
- No attachments stored on an operation.

**Structure**
- No third level of categories — parent and subcategory only.
- No personal goals; goals exist only on shared wallets.
- No intermediate roles between owner and member.
- No multi-budget membership — one person belongs to exactly one budget.
- No restoring a deleted category, and no reverting an edited field.
- No reopening a closed goal.
- No changing an operation's type by editing.

**Interface**
- No separate History tab in the bottom menu.
- No floating "+" button and no centre action button.
- No product-level theme switch — the Telegram theme governs.
- No onboarding tour, no feature list on `/start`, no welcome screen in the app.
- No `/menu` command.
- No interim "разбираю…" message during parsing.
- No transcription shown for voice input.
- No per-person breakdown in the weekly digest (it exists in analytics only).

**Languages**
- Russian and Uzbek only. Uzbek strings are produced after the Russian ones are
  locked and are out of scope for this document.

---

## 22. Out of the implementer's scope

These are the customer's responsibility and must not be assumed, invented, or
blocked on.

**Keys, accounts and money**
- Provider accounts and API keys for the parsing model and the speech service.
- Billing, quotas and cost monitoring.
- Re-verifying model prices before release and quarterly afterwards — prices
  changed twice in one half-year.

**Infrastructure**
- Domain, hosting, TLS certificates, deployment and restarts.
- Server configuration values, including the 50 and 20 daily limits.
- Backups and their restoration.
- The bot registration and its menu button.

**Product decisions**
- Choice of speech provider, made by the 18-of-20 test (section 9).
- The go/no-go on receipt photo, made by the 20-receipt test (section 10.2).
- Whether existing families are migrated to the new category set (15.5).
- Final wording of any user-facing text, and all Uzbek translations.
- Slicing this document into phases and setting their order.

**Customer's own acceptance pass**

Roughly twenty actions, one evening, covering what cannot be verified by an
implementer:

1. Open the app, leave it open two hours, use it — it still works.
2. Close it, reopen the next day — it opens without asking anything.
3. Send `такси 25 тысяч` — a card arrives in about a second and reads correctly
   on your phone.
4. Send a five-operation message — five cards, balances stepping correctly.
5. Send `перевел с карты доллара на карту сум 50$` — refused, balances untouched.
6. Send the same sentence in Uzbek — refused identically.
7. Send `подарили 500 тысяч`, wait a day, tap `[Получил]` — dated yesterday.
8. Send a voice message describing a real expense — a card arrives, no
   transcription shown.
9. **Photograph 20 real receipts and send them — at least 18 must produce the
   correct total.** This is the release gate for section 10.
10. Create a personal wallet, spend from it, then check from another family
    member's phone that it is invisible.
11. Create a goal, cross it, receive the message, close it.
12. Invite a person by link, then reissue the link and try the old one.
13. Remove that person and confirm from their phone that they now own a budget
    holding their personal wallet.
14. Check History in the old family — they appear as `Рустам (бывший участник)`.
15. Transfer ownership and confirm the controls moved.
16. Edit another member's operation and confirm the `Изменения` block reads
    correctly.
17. Record nothing for one day and wait for 21:00 — the reminder arrives.
18. Wait for Monday 10:00 — the digest arrives, currency blocks separate, no
    personal spending in it.
19. Switch your phone between light and dark theme and walk every screen.
20. Set a category name to 30 characters and check it truncates everywhere.

---

## 23. Open items — do not guess

Items where data is deliberately absent. The implementer must ask rather than
assume.

| Item | Who decides | Blocking |
|---|---|---|
| Speech provider for voice input | customer, by the 18-of-20 test | section 9 only |
| Whether receipt photo ships in this release | customer, by the 20-receipt test | section 10 only |
| Migration of existing families to the new category set | customer, if family count grows before release | section 15.5 only |
| Uzbek translations of all user-facing strings | customer, after Russian strings lock | none — Russian ships first |
