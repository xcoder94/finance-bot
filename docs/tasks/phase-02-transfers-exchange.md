# Phase 2 — Transfers and exchange via quick entry

PRD: §8.
Depends on: Phase 1 complete (text quick entry, cards, counters, wallets).
Plan: written after this spec is approved — not in this file.

---

## 1. User goal

A person writes about moving money between wallets; the bot creates a transfer
or an exchange correctly, or clearly refuses when a rate is missing — money
never silently vanishes or moves at the wrong scale.

---

## 2. Acceptance steps I will do by hand

On the test bot, family with at least two shared UZS wallets and one USD wallet
(and balances that make the card numbers readable).

1. Send `переложил 500 тысяч с карты на наличные`. Transfer card in §8.2
   layout: both balances labelled, no minus sign, neutral colour, buttons only
   `Изменить` and `Удалить` (no `Кошелёк`).
2. Send `поменял 100 долларов на сумы по 12800`. Exchange card shows rate and
   resulting amount per §8.3.
3. Send `перевел с карты доллара на карту сум 50$`. **No record**; §8.3 refusal
   text; wallet balances unchanged afterwards. This is the §8.4 check — the
   single most important step.
4. Same sentence in Uzbek (`dollar kartasidan so'm kartasiga 50$ o'tkazdim`).
   Same refusal, balances untouched.
5. Send `поменял 100 долларов на сумы 12800` without the marker word `по`.
   Rate is not assumed; §8.3 refusal appears.
6. Confirm an ordinary expense message from Phase 1 still works after this
   phase (no regression).

---

## 3. What is NOT in this phase

- Voice (§9), receipt photo (§10)
- Personal wallets UI / `Мои личные` (§11)
- Goals (§12), members (§13), change log (§14)
- Mini-app redesign (§17), notifications (§16)
- Prompt caching (§20)
- `/start` rewrite, release announcement (§18)
- Manual transfer/exchange form in the mini app (§17.7) — later History/forms
- Uzbek translations
- Choosing or paying for provider accounts

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Same-currency transfer | Create immediately; card layout and Russian strings exactly §8.2. |
| 2 | Transfer card buttons | Exactly `Изменить` · `Удалить`. No `Кошелёк`. |
| 3 | Exchange with rate | Rate recognised **only** with explicit marker words (`по`, `по курсу`); card layout and strings exactly §8.3. |
| 4 | Exchange / cross-currency without rate | No record; exact §8.3 refusal; unparsed counter +1. |
| 5 | Bot-side sanity check (§8.4) | Before any write: if transfer/exchange and currencies differ and no rate → discard parse, send §8.3 refusal, spend unparsed. Independent of the model. |
| 6 | Colour / sign | Transfer and exchange: neutral text colour, amount has no minus sign (§5). |
| 7 | Counters | One model call per message still spends 1 of 50 when the model is called; refusal paths that called the model spend unparsed per §8.3. |
| 8 | Provider / models | `PARSER_*` env vars only; model name never hard-coded. |
| 9 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Pytest: §8.4 sanity check rejects cross-currency without rate before write;
   balances unchanged; unparsed +1.
2. Pytest with stubbed parser: same-currency transfer card fields; exchange
   with rate; refusal without `по`; expense path still creates expense.
3. Fixture for Uzbek cross-currency sentence → same refusal as Russian.
4. Report before/after pytest; list every stub/mock. Live model call optional;
   if skipped, say so under finish-later.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Phase 1 on the branch under test | team |
| Test bot + `BOT_TOKEN` | customer |
| `PARSER_*` credentials | customer |
| Family with ≥2 UZS shared wallets and ≥1 USD wallet | team seeds |
| Readable balances on those wallets | team seeds |

---

## 7. When you must stop and ask me

- Inventing a different refusal text or adding a `Кошелёк` button on transfer cards.
- Silently assuming a rate without the marker words.
- Writing a cross-currency transfer despite §8.4.
- Any new paid API or account.
- Scope beyond §8.
- Confidence below average — say «not sure».
