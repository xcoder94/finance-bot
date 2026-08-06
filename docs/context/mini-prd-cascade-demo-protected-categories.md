# Mini-PRD — cascade classification, demo data, protected categories, support relay

Status: **closed, 2026-08-05 — all open questions answered by the PM or
resolved with an explicit architect default at the PM's request.** Not yet
built, not yet a phase spec — still lives in `docs/context/` per the
standing rule (never committed) until it's turned into
`docs/tasks/phase-*.md` spec(s) and handed to Cursor. Ready to be turned
into a Cursor prompt on the PM's go-ahead.

Four independent proposals from the PM, 2026-08-05 (the fourth, support
relay, added mid-session once items 1–3 were sized). Every "architect
default" below was chosen by the assistant because the PM explicitly asked
to close the document rather than re-ask each remaining item — these are
not PM-authored decisions and should get one pass of scrutiny whenever the
PM reviews this file, same as the Appendix A/B drafts.

---

## 1. Cascading classification (rule-based prefilter → LLM fallback)

**Goal (PM's framing):** cut model-call cost further, same direction as the
phase-14b Speech-to-Text→Gemini rework — most quick-entry messages are
simple ("такси 25 тысяч") and don't need a full model call if a local
keyword match can resolve them with confidence.

**Current architecture (checked in code, low integration risk):**

- One entry point: `MessageParser.parse()` (`backend/app/parsing/base.py`),
  obtained via `get_parser()` (`backend/app/parsing/factory.py`). It's a
  `Protocol`, single implementation `HttpParser`.
- Called from exactly two places in
  `backend/bot/quick_entry/handlers.py` (text path and voice path).
- `ParseRequest` carries the family's actual wallet and category names
  (`wallet_names`, `expense_category_names`, `income_category_names`) — the
  model already gets a family-specific list, not a hardcoded one.
- `ParseResponse` returns a **list** of operations (up to 5, §4), plus
  `speech_status` / `date_hint` / `receipt_status` — parsing is not
  "detect one category," it resolves amount, currency, wallet, category,
  comment, and (for transfer/exchange) two wallets and a rate, in one call.

A prefilter can sit **in front of** this call as a new gate in the handler
(or a decorator implementing the same `MessageParser` protocol) without
touching `HttpParser`, the parser's own tests, or the phase 14b/15 audio
and image paths. The existing model call stays the fallback, unchanged.
This matches the PM's own risk framing — the exposure is a new code path
added before the existing one, not a rewrite of it.

**What's genuinely open (PM must decide, not guessable from PRD/code):**

1. **Scope of what the prefilter is allowed to resolve.** Category only, or
   a full operation (amount + wallet + category + comment)? Full-operation
   resolution is where the cost saving actually is, but it's also where
   silent misclassification risk concentrates.
2. **Which message shapes are eligible.** Single expense/income with an
   unambiguous keyword and a parseable number is the plausible safe case.
   Transfers, exchanges, multi-operation messages (up to 5 ops, §4),
   relative dates ("вчера") — does the prefilter attempt these at all, or
   does detecting more than one operation / a transfer keyword always force
   the LLM path? Recommend the latter as the safer default, but it's the
   PM's call.
3. **Keyword source and ownership.** Matching against a family's *actual*
   category names (owner may have renamed or added categories, §15) is
   already required by the current architecture — a generic hardcoded
   keyword list would silently stop matching a renamed category. Does the
   dictionary need Russian synonym/slang coverage beyond the literal
   category and subcategory names (e.g. "такси" vs "таксишка")? Who
   authors and maintains that list? (Uzbek stays out of scope per AGENTS.md
   regardless.)
4. **Confidence / fail-safe rule.** On any doubt, must fall through to the
   LLM rather than guess — never a wrong silent classification. Needs an
   explicit, testable threshold, not "good enough."
5. **Counters.** `daily_model_calls` currently counts every model call
   (§4). A prefilter hit spends zero model calls by construction — does
   that need a customer-visible framing, or is it purely an internal cost
   win with no counter/text change? (Leaning: no visible change, but
   confirming avoids a silent behavior drift in a counter the PRD defines.)
6. **`MSG_NO_AMOUNT` / unparsed-counter semantics** must stay identical
   regardless of which path (prefilter or LLM) produced the "no amount"
   outcome — this is an existing PRD-defined text/counter pair, not new.

**PM answers, 2026-08-05:**

- **Text only.** The prefilter applies to typed quick-entry messages only.
  Voice (phase 14b) and receipt photos (phase 15) always go straight to
  Gemini — there is no local model to run audio/image through, and none is
  planned.
- **No local model** — confirms the prefilter is pure rule-based matching
  (keywords/regex against the family's actual category and wallet names),
  not a lightweight ML classifier.
- **Dictionary: Russian and Uzbek**, drafted by the architect (me), PM
  reviews and confirms before it ships. Draft below in
  [Appendix A](#appendix-a-cascade-keyword-dictionary-draft-v1). Uzbek here
  is keyword *recognition* in free-text user input, not UI localization —
  does not conflict with AGENTS.md's "Uzbek translations out of scope"
  (that rule is about `ru.json`/`uz.json` interface strings).

**Closed with architect defaults, 2026-08-05 (PM asked to close with my
recommendation rather than re-ask):**

1. **Scope: full operation** (amount + wallet + category + comment), not
   category-only — that's where the actual cost saving is, and the text
   path already resolves amount/date by regex today
   (`resolve_operation_date`/`strip_date_words`), so full-operation
   rule-based resolution isn't a new kind of risk for this codebase, just
   a new place it's applied.
2. **Eligible shapes: single-operation expense/income only.** Any
   transfer/exchange keyword, or any signal of more than one operation in
   the message (multiple amounts, "и"/"а также" separators, etc.), routes
   straight to the LLM — never attempted by the prefilter. This is the
   large majority of real quick-entry traffic ("такси 25 тысяч",
   "продукты 150000") and the case cheapest to get right.
3. **Fail-safe rule:** the prefilter only resolves a message when *all*
   of the following hold, otherwise it falls through to Gemini unchanged:
   - exactly one category (parent or, if present, subcategory) matches a
     keyword from Appendix A against the family's *current* category
     names — zero matches or matches in more than one category both fail
     through;
   - exactly one parseable amount is found via the existing amount-regex
     used on the text path;
   - no transfer/exchange/multi-op signal (see point 2);
   - no ambiguous wallet mention (zero or one wallet-name match — more
     than one fails through).
   Any doubt anywhere in this chain is a fall-through, never a guess.
4. **Counters/`MSG_NO_AMOUNT`: no change.** A prefilter hit spends zero
   `daily_model_calls` by construction (no model call happened). The
   unparsed-message counter and `MSG_NO_AMOUNT` text apply identically
   regardless of which path produced the "no amount" outcome — this is
   existing PRD-defined behavior (§4, §7.9), not something this feature
   redefines.

---

## 2. Demo data fill + clear-demo-data control

**Goal (PM's framing):** populate the mini app with realistic data so
someone unfamiliar with it (PM, and/or the customer — see Q1 below) can see
what it actually looks like across screens, then wipe it with one control.

**Relevant existing constraints (AGENTS.md, not new):**

- The design's mandatory states — empty month, loading skeleton,
  failed-entry screen, limit messages, owner view, member view — must all
  still be reachable and correct. Demo data that fills every screen with
  rows makes the **empty-month state** unreachable unless clearing demo
  data (or a second toggle) is how that state gets exercised.
- **No dead controls**: a "clear demo data" button must actually do
  something meaningful, and if this whole feature is not customer-facing
  (see Q4), it must not ship as a control real customers can see at all —
  per AGENTS.md, an out-of-scope control isn't drawn, not drawn-disabled.

**PM answers, 2026-08-05:**

- **Audience: real customers**, not a dev tool. Purpose is retention —
  prevent a new user from opening the app, seeing every screen empty, and
  never coming back. This is a real onboarding feature, in scope for
  production, not internal-only.
- **Previous month only, never the current month.** This is the key
  mechanic: demo data sits in a month the user isn't actively adding real
  operations to, so it can't visually mix with what they enter themselves,
  and Analytics' month view shows it as a distinct, already-closed period.
- **Content:** roughly **$500 and 8,000,000 UZS**, distributed across
  expense categories, weighted mainly toward **Еда, Дом, Транспорт**.
- **Clear control:** Settings screen, button **"Очистка демо данных"**.
  Tap wipes it, nothing else asked.

**Why previous-month-only also solves the data-safety question:** a
brand-new budget's previous month has zero real operations by
construction — the family didn't exist yet. Seeding it can never
overwrite or mix with real history. This only holds for a *new* budget
seeded once; it does not license reseeding an existing family's already-
active previous month later.

**PM answers, 2026-08-05 (second round):**

- **Trigger: automatic at `/start`**, every new budget. The very first
  screen a new user opens already has a populated previous month.
- **Clear control: owner only** — consistent with every other structural
  owner-only control in the product (categories, wallets, members).

**Closed with architect defaults, 2026-08-05:**

1. **Marking demo rows: an `is_demo` boolean on the operation**, default
   `False`, set `True` only on rows the seeding function itself creates.
   "Clear" deletes exactly the rows in that family where `is_demo` is
   `True` — never a date-range delete. A real operation that happens to
   land in the same calendar month (an edit, or a relative-date quick
   entry within the 31-day lookback, §4) is untouched by construction,
   since it was never marked. This is the specific storage shape Cursor
   should build, not just a constraint on one — small enough a decision
   that re-asking would cost more than it's worth.
2. **Exact operation breakdown: the draft below is now final**, not
   pending — PM asked to close with defaults.

**PM answer, 2026-08-05 (third round): add income, so a remaining balance
shows too.** $600 and 9,000,000 UZS income, on top of the ~$500 /
~8,000,000 UZS expense figures already given — net remainder: **+$100,
+~2,000,000 UZS** for the demo month.

**Final breakdown:**

Expenses:

| Category | Amount | Notes |
|---|---|---|
| Еда → Продукты | 2,200,000 UZS | 4 operations across the month |
| Еда → Кафе и рестораны | 600,000 UZS | 2 operations |
| Дом → Коммунальные услуги | 900,000 UZS | 1 operation |
| Дом → Связь и интернет | 250,000 UZS | 1 operation |
| Транспорт → Такси | 700,000 UZS | 3 operations |
| Транспорт → Топливо | 900,000 UZS | 2 operations |
| Здоровье → Лекарства и аптека | 450,000 UZS | 1 operation |
| Покупки и досуг → Одежда | 1,000,000 UZS | 1 operation |
| **UZS expense subtotal** | **7,000,000 UZS** | leaves ~1,000,000 headroom under the ~8,000,000 target for rounding |
| Покупки и досуг → Развлечения | $150 | 2 operations, USD wallet |
| Дом → Ремонт и обустройство | $350 | 1 operation, USD wallet |
| **USD expense subtotal** | **$500** | |

Income:

| Category | Amount | Notes |
|---|---|---|
| Зарплата | 8,000,000 UZS | 1 operation, early in the month — the plausible salary date |
| Подработка | 1,000,000 UZS | 1 operation |
| **UZS income subtotal** | **9,000,000 UZS** | |
| Переводы от родных | $600 | 1 operation, USD wallet — plausible in-context (remittance) |
| **USD income subtotal** | **$600** | |

**Net for the demo month: UZS +2,000,000, USD +$100** — the previous
month's balance shows a real, positive remainder, not just a pile of
expenses.

All dated across the previous calendar month, default shared wallets
("Карта сум" for UZS, a USD wallet for USD), each with a short realistic
comment (e.g. "продукты", "такси", "зарплата") rather than a "demo" label
in the comment text itself — flagging as demo happens via the internal
marker (open item 1), not visible wording, so the data reads as genuine
to the user per the retention goal.

---

## 3. Protected (non-deletable) categories — hypothesis check

Full analysis already given to the PM in conversation; summarized here for
the record before the open questions.

**PM asked to see the current category tree before picking which ones
become protected. Full tree, expense side only (income out of scope per
the original wording "3-4 категории расходов"):**

```
Еда
├─ Продукты
├─ Кафе и рестораны
└─ Доставка

Транспорт
├─ Такси
├─ Топливо
├─ Общественный транспорт
└─ Обслуживание авто

Дом
├─ Аренда
├─ Коммунальные услуги
├─ Связь и интернет
└─ Ремонт и обустройство

Дети
├─ Садик и школа
├─ Кружки и репетиторы
└─ Детские товары

Здоровье
├─ Лекарства и аптека
├─ Врачи и клиники
└─ Стоматология

События и тои   ← §15.1: "mandatory and must not be dropped" (seed-time
│                  wording, ambiguous on deletion — see below)
├─ Тои и маърака
└─ Подарки

Покупки и досуг
├─ Одежда
├─ Развлечения
├─ Подписки
└─ Красота и уход
```

PM picks which parents (and optionally which specific subcategories, if
protection should go deeper than the parent) become permanent.

**PM's final pick, 2026-08-05: Еда, Дом, Здоровье.** Parent-level only —
their subcategories stay freely deletable and renamable by the owner, same
as today. "События и тои" and "Транспорт" are **not** protected — the
§15.1 "must not be dropped" wording for "События и тои" stays the
pre-existing seed-time-only ambiguity noted above; this proposal doesn't
touch or resolve it.

**Current behavior (PRD + code, confirmed):**

- Categories are per-family rows (`family_budget_id`), copied once from a
  fixed template (`backend/app/services/budget_seed.py`) at `/start`, never
  reseeded when members join, leave, or get removed into a fresh budget of
  their own (PRD §13.3, §15.5). **"Duplication at registration" cannot
  happen today** — that part of the PM's framing describes already-true
  behavior, not a gap.
- Deletion is soft-delete, identical for every category, no exceptions
  (PRD §15.4): frees a slot, past analytics/History keep showing it
  unchanged, no restore.
- Rights (PRD §3): owner creates and deletes categories, no per-category
  carve-out.
- One existing wrinkle: "События и тои" is marked "mandatory and must not
  be dropped" (§15.1) — read in context, that's a **seed-time** mandate
  (must be included when a new budget is created), not a stated
  deletion-time lock. §15.4's deletion rules make no exception for it.
  This is a pre-existing PRD ambiguity, not something introduced by this
  proposal — flagging it here because protected categories would force a
  real answer to it.

**What making 3–4 categories permanently protected actually changes:**
this is a new product rule, not present in the PRD today. Technically cheap
(a flag or a match against `translation_key`, which already exists and is
already used for cross-budget matching) — the open items are product
decisions, not feasibility.

**PM answers, 2026-08-05:**

- **Protection covers both deletion and renaming.** Name and existence of
  a protected category are fully frozen — this is the first place the
  product separates "delete" from "rename" as owner powers.
- **Limit §4 raised, not held at 8.** A family always keeps a full 8 free
  slots for its own categories, on top of however many are protected —
  protected categories don't eat into the 8. The PRD's numeric-limits
  table and the limit message (§4, "Больше 8 категорий расходов создать
  нельзя...") need updating to reflect `8 + protected count` once the
  final protected list is set.
- **Exact list:** tree shown, PM to confirm which parents (below the tree
  in this doc) — not yet answered.

**Resolved:**

1. **Exact list: Еда, Дом, Здоровье** — parents only, subcategories stay
   fully editable.
2. **Expense only** — income categories (§15.2) untouched, confirmed by
   omission when the PM picked the list.
3. **Subcategories under a protected parent stay unprotected** — a
   subcategory of Еда/Дом/Здоровье can still be deleted or renamed by the
   owner; only the three parent rows themselves are frozen.

**Closed with architect default, 2026-08-05:**

4. **Existing families (§15.5 no-migration): protection applies going
   forward only.** A family created before this ships keeps its current,
   fully-editable "Еда"/"Дом"/"Здоровье" (which may already be renamed or
   even deleted). This mirrors the exact precedent §15.5 already sets for
   the new-category-set rollout: old budgets are left alone, new rules
   apply to newly seeded budgets only.
5. **UI (not a decision, a consequence of AGENTS.md).** Per "no dead
   controls": the delete *and* rename
   controls must not render at all for a protected category (not disabled
   buttons showing an error) — consistent with how the PRD handles the
   deleted-category case (§15.4: not offered anywhere it could be picked).

---

## 4. Support message relay ("написать в поддержку")

**PM's framing, 2026-08-05:** every user can send a message that reaches
the PM in one channel; the PM answers from there and the reply reaches the
right user back through the bot. Explicit condition: build it only if it's
small — smaller than items 1–3 combined. Otherwise skip.

**Sizing verdict: smaller than items 1–3 combined — proceeding to open
questions, not deferring.**

Reasoning, compared piece by piece against the batch above:

- Items 1–3 combined already require: a new keyword-matching gate plus a
  bilingual dictionary (item 1), a new seeding function + `is_demo` flag +
  migration + settings control (item 2), a new `is_protected` flag +
  migration + a §4 limit-number change propagated through the PRD's numeric
  table and its limit message (item 3) — three separate subsystems, each
  with its own schema change and test surface.
- This feature is one bounded subsystem: one new config value (admin chat
  id, same pattern as `PARSER_API_KEY` in `config.py`), one small mapping
  table (forwarded-message-id → sender's telegram id / family), and two
  bot handlers — outbound (user → admin chat) and inbound (admin's reply →
  original user). The bot already has a working FSM pattern for
  multi-step text capture (`OnboardingStates` in
  `backend/bot/onboarding.py`) to model off of for "user is now typing a
  support message."
- Reply routing is mechanical: match on Telegram's native
  `reply_to_message.message_id` against the stored mapping row, no thread
  UI, no state machine on the admin side — the PM just uses Telegram's
  normal reply gesture in the one channel.

**PM answers, 2026-08-05 (second round):**

- **Who can use it: every member**, not owner-only.
- **Input format: both** — a menu of ready-made quick messages for common
  topics, plus a "write your own" option that opens free-text input.
  Drafted below (Appendix B), RU + UZ, PM reviews at the end.
- **Admin destination: not the PM's personal Telegram.** Explicit
  constraints given: shouldn't clutter the PM's own account; replies must
  land precisely with the right sender; users must never see each other's
  messages. **Recommendation, satisfies all three:** a dedicated, closed
  Telegram group with the bot added as a member/admin and the PM as the
  only human member (room for more staff later). The bot posts each
  incoming support message into that group with the sender identified;
  the PM replies using Telegram's native reply-to-message gesture; the
  bot matches the reply against the stored mapping and DMs the original
  user privately. Users are never members of that group, so isolation
  between users is structural, not a rule the code has to enforce.
  Creating the actual group and handing me its numeric chat id is
  server-configuration territory (PM's task, outside my scope per
  AGENTS.md) — the code just reads the id from an env var, same pattern
  as `PARSER_API_KEY`.
- **Uzbek strings for this feature: PM wants the standing AGENTS.md rule
  itself updated**, not a one-off exception — see the note right after
  this list; I'm not editing `AGENTS.md` myself (it says "edited by me
  only"), proposing exact wording for the PM to paste in instead.

**AGENTS.md updated, 2026-08-05 — PM explicitly granted edit rights for
this one rule.** Applied the narrower wording (full `uz.json` interface
localization stays gated behind the PM's say-so, after Russian locks;
short self-contained new-feature strings like these may be drafted in
Uzbek by the assistant for review) in both places the old rule appeared:
the "User-facing text" section and the "Outside your scope" list. This
was a scoped, explicitly authorized exception to "AGENTS.md is edited by
me only" — not a standing change to who edits the file going forward.

**Closed with architect defaults, 2026-08-05:**

1. **Identifying the sender to the PM:** family name + the sender's name +
   Telegram username (when set), formatted as a header line above the
   message text in the admin group — e.g. "Семья Каримовых — Дилноза
   (@dilnoza_uz)". If the sender has no username, the header falls back to
   just family name + person's name (a Telegram id alone isn't something
   the PM could act on manually).
2. **Rate limit: none for MVP.** Family size is capped at 4 (§4) and this
   is a low-volume, trusted-user product — no abuse guard for the first
   version.

## Next step

All four are decided (PM answers + architect defaults, both marked
inline). Waiting on the PM's go-ahead to turn this into `docs/tasks/
phase-*.md` spec(s) and a Cursor prompt — and to fold the §4 numeric-limit
change (item 3) and the new demo-data/support-relay behavior into
`PRD.md` itself, since AGENTS.md treats the PRD as the sole source of
product meaning and bot text.

---

## Appendix A — cascade keyword dictionary, draft v1

**Draft only — needs PM review before Cursor sees it.** Russian first
(matches the actual category/subcategory names, §15.1/§15.2), Uzbek
(Latin script, common spoken forms) second. Not exhaustive slang coverage
— a first pass to react to, not a finished list. Each row keys off the
same `translation_key` already used in `budget_seed.py` for cross-budget
matching, so the dictionary stays attached to the category identity even
if an owner renames the category itself.

### Expenses

| Parent → sub | translation_key | RU keywords | UZ keywords |
|---|---|---|---|
| Еда | `food` | еда | ovqat |
| ↳ Продукты | `groceries` | продукты, магазин, супермаркет | oziq-ovqat, market, do'kon |
| ↳ Кафе и рестораны | `cafes_restaurants` | кафе, ресторан, кофе, обед | kafe, restoran, taomxona |
| ↳ Доставка | `delivery` | доставка, яндекс еда, uzum tezkor | yetkazib berish |
| Транспорт | `transport` | транспорт | transport |
| ↳ Такси | `taxi` | такси, яндекс такси, болт | taksi |
| ↳ Топливо | `fuel` | бензин, заправка, топливо, газ (авто) | benzin, yoqilg'i |
| ↳ Общественный транспорт | `public_transport` | автобус, метро, маршрутка, проезд | avtobus, metro |
| ↳ Обслуживание авто | `car_maintenance` | сто, автосервис, шиномонтаж, мойка | avto servis, moyka |
| Дом | `home` | дом | uy |
| ↳ Аренда | `rent` | аренда, съём квартиры | ijara |
| ↳ Коммунальные услуги | `utilities` | коммуналка, свет, вода, электричество | kommunal, svet, suv |
| ↳ Связь и интернет | `telecom_internet` | интернет, связь, симкарта | internet, aloqa |
| ↳ Ремонт и обустройство | `repairs_furnishing` | ремонт, мебель, стройматериалы | ta'mir, mebel |
| Дети | `children` | дети | bolalar |
| ↳ Садик и школа | `kindergarten_school` | садик, школа, детский сад | bog'cha, maktab |
| ↳ Кружки и репетиторы | `clubs_tutoring` | кружок, репетитор | to'garak, repetitor |
| ↳ Детские товары | `kids_goods` | игрушки, детская одежда, подгузники | bolalar buyumlari |
| Здоровье | `health` | здоровье | salomatlik |
| ↳ Лекарства и аптека | `pharmacy` | лекарства, аптека, таблетки | dori, apteka |
| ↳ Врачи и клиники | `doctors_clinics` | врач, клиника, больница, анализы | shifokor, klinika |
| ↳ Стоматология | `dentistry` | стоматолог, зубы, дантист | stomatolog, tish |
| События и тои | `events_celebrations` | той, мероприятие | to'y, tadbir |
| ↳ Тои и маърака | `toi_celebrations` | той, маърака, свадьба, юбилей | to'y, marosim |
| ↳ Подарки | `event_gifts` | подарок на той, цветы | sovg'a |
| Покупки и досуг | `shopping_leisure` | покупки | xarid |
| ↳ Одежда | `clothing` | одежда, обувь, кроссовки | kiyim, poyabzal |
| ↳ Развлечения | `entertainment` | кино, боулинг, развлечения | kino, ko'ngilochar |
| ↳ Подписки | `subscriptions` | подписка, netflix, spotify | obuna |
| ↳ Красота и уход | `beauty_care` | салон красоты, парикмахерская, косметика | go'zallik saloni |

### Income

| Category | translation_key | RU keywords | UZ keywords |
|---|---|---|---|
| Зарплата | `salary` | зарплата, зп, аванс, оклад | maosh, ish haqi |
| Подработка | `side_job` | подработка, фриланс, шабашка | qo'shimcha ish |
| Подарки | `gifts` | подарили, подарок получил | sovg'a oldim |
| Переводы от родных | `family_transfers` | перевод от родителей, от родных, от мамы, от папы | qarindoshdan pul |
| Прочее | `income_other` | *(no reliable keyword — deliberately absent, always falls to LLM)* | — |

**Note on "Прочее" (both income and — via "Покупки и досуг" naming
collision, §15.3 — nothing on the expense side is named "Прочее"):** a
catch-all category has no distinguishing keyword by definition. Any
message that doesn't match another row's keywords is exactly the case the
prefilter should decline, not a case it should resolve to "Прочее" itself.

---

## Appendix B — support relay strings, draft v1

**Draft only — PM reviews at the end, per their instruction.** Avoids the
forbidden words (`ошибка`, `сессия`, `сервер`, `токен`, `запрос`) per
AGENTS.md's user-facing-text rule, which applies here too even though this
whole feature is new. UZ column depends on the AGENTS.md wording decision
above.

| Purpose | RU | UZ |
|---|---|---|
| Entry point (settings button) | Написать в поддержку | Qo'llab-quvvatlashga yozish |
| Quick option 1 | Голосовое сообщение не распознаётся | Ovozli xabar tanilmayapti |
| Quick option 2 | Фото чека не распознаётся | Chek fotosurati tanilmayapti |
| Quick option 3 | Вопрос по категориям или кошелькам | Kategoriyalar yoki hamyonlar bo'yicha savol |
| Quick option 4 | Не приходят уведомления | Bildirishnomalar kelmayapti |
| "Write your own" option | Свой вопрос | Boshqa savol |
| Free-text prompt (after tapping "Свой вопрос") | Напишите ваш вопрос одним сообщением. | Savolingizni bitta xabarda yozing. |
| Confirmation (after any send — quick or free) | Сообщение отправлено. Мы ответим вам здесь же. | Xabar yuborildi. Javobni shu yerda kutib turing. |

Quick options are a first guess at common topics (voice, receipt photo,
categories/wallets, notifications) based on what the product actually
does — not from any existing spec, since none exists for this feature.
PM may want different topics, a different count, or different wording
entirely.
