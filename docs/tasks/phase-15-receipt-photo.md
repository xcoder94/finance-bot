# Phase 15 — Receipt photo (last, isolated)

PRD: §10.
Depends on: Phase 1–2 (card/create path). **Must not be required by any earlier
phase.** Cancelling this phase after the customer's 20-receipt test must leave
Phases 0–14 working.
Plan: written after this spec is approved **and** customer green-lights build
after / alongside the measurement — not in this file.

---

## 1. User goal

A person photographs a receipt and sends it; the bot creates one operation for
the total and replies with an ordinary card — or clearly says it could not read
the receipt.

---

## 2. Acceptance steps I will do by hand

1. Photo of a receipt → typing indicator → ordinary card: total amount, a
   category, default wallet, merchant name as comment.
2. Same photo with caption `с наличных` → cash wallet wins over default.
3. Photo that is not a receipt → exact §10.1 failure text; no record; unparsed
   +1.
4. Receipt dated two months ago → record date is **today**, not receipt date.
5. Three photos as one album → three cards; quota drops by 3.
6. **Release gate (customer only):** 20 real receipts, ≥18 correct **totals**.
   Merchant/category soft. Team does not claim Phase 15 shipped for users
   without this gate.

---

## 3. What is NOT in this phase

- Line-by-line receipt parsing (§10.1 / §21)
- Changing text/voice quick entry behaviour
- Making any earlier phase import this module
- Automatic currency conversion
- Storing the image as an operation attachment (§21)
- Uzbek translations
- Provider account creation (customer)
- Shipping to all users before the 18/20 gate

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Granularity | One receipt = one operation for the total amount. |
| 2 | Category | From merchant name and visible contents. |
| 3 | Wallet | Default; caption overrides when it names a wallet. |
| 4 | Date | From receipt if legible and within 31 days; else today. |
| 5 | Comment | Merchant name. |
| 6 | Album | Each photo = own model call and own card. |
| 7 | UX while running | Standard typing indicator only. |
| 8 | Timeout | 20 seconds per attempt; otherwise §7.12 retry rules. |
| 9 | Counters | 50 quota +1 per photo; unreadable → unparsed +1. |
| 10 | Failure text | Exact §10.1 Russian paragraph for every unread failure. |
| 11 | Isolation | Feature flag or separate handler module so disable/removal does not break text/voice paths. |
| 12 | Provider / model | `PARSER_*` (or image-capable path via same env family) — model name only from env; do not invent a version. If image needs a different env key, stop and ask before adding it. |
| 13 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Tests with stubbed vision/parse: card fields; caption wallet override; non-
   receipt failure text + unparsed; old date → today; album of 3 → 3 calls.
2. Confirm text quick entry tests still pass with photo handler disabled.
3. Live image call only if credentials present; 20-receipt gate is customer's.
4. Report before/after; list stubs; explicitly state feature-flag off path.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Parser credentials that accept images | customer |
| Decision to build after measurement (go/no-go) | customer (§23) |
| 20 real receipts | customer |
| Feature flag / config to disable photo without redeploying text path | team designs inside approved stack |

---

## 7. When you must stop and ask me

- Shipping photo entry without the 18/20 gate.
- Line-item parsing.
- New env keys beyond the agreed `PARSER_*` / `SPEECH_*` set without asking.
- Coupling photo code so disabling it breaks text entry.
- Confidence below average — say «not sure».
