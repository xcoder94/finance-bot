# Phase 16 Task C — Cascading Rule-Based Prefilter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before the LLM parser on **text** quick entry only, try a pure rule-based prefilter that fully resolves a single expense/income operation when fail-safe rules all hold; otherwise fall through to existing `parser.parse()` unchanged.

**Architecture:** New pure module `backend/app/parsing/prefilter.py` (+ keyword dictionary module). Wired only inside `process_quick_entry_text` before `_get_parser().parse()`. On hit, synthesize a `ParseResponse` with one `ParsedOperation` and skip the parser (zero `daily_model_calls` spend for that path — naturally, because `spend_model_call` must also be skipped when prefilter hit). Voice and receipt paths untouched.

**Tech Stack:** Python, pytest. No network in prefilter.

## Global Constraints

- Worker: `composer-2.5` only.
- Text path only — never call prefilter from voice/receipt handlers.
- Do not emit `MSG_NO_AMOUNT` from prefilter; never touch unparsed counter inside prefilter. Only "resolve" or "fall through".
- On fall-through: existing `parser.parse()` call completely unchanged.
- On hit: must not call parser; must not `spend_model_call` (assert in tests with a parser double that fails if called). Existing post-parse card building should still run — inject as if parser returned one clear op, OR short-circuit into the same clear-op card path. Prefer injecting a synthetic `ParseResponse` and continuing the existing handler from the `countable = ...` line so card shape stays identical — but skip `spend_model_call` when prefilter_hit.
- Reuse `resolve_operation_date` / `strip_date_words` for date/comment; do not reimplement.
- Amount parsing: **no existing utility** — write a small focused one in the prefilter module (or `prefilter_amount.py`). Support integers, spaces/underscores, and Russian «тысяч»/«тыс» (e.g. `25 тысяч` → 25000). Exactly one amount required.
- Do not edit docs/context, AGENTS, PRD, design, tasks. No git push/checkout.
- Do not touch ru.json/uz.json.
- Keyword dictionary: copy **verbatim** RU + UZ keywords from Appendix A in `docs/context/mini-prd-cascade-demo-protected-categories.md` (read only). Omit `income_other` (no keywords).
- Baseline: pytest 428, vitest 206. Frontend likely unchanged (vitest stay 206 OK).

## Category matching rule (binding — acceptance 8.3.2)

Appendix A keywords are keyed by `translation_key`, but the family's **current category names are authoritative**.

For each active family category (expense or income):

1. Always include the category's **current name** (casefold) as a matchable term.
2. Additionally include Appendix A RU+UZ keywords for its `translation_key` **only if** the current name casefold-equals the **seed Russian name** for that key (from `SEED_EXPENSE_CATEGORIES` / `SEED_INCOME_CATEGORIES` in `budget_seed.py`). If the owner renamed the category away from the seed name, stock Appendix A keywords for that key do **not** apply — only the new name can match.

Matching against message text (casefold): a category "matches" if at least one of its matchable terms appears as a whole-word/substring-safe match in the message (prefer whole-word / boundary-aware matching so «еда» does not false-hit inside unrelated words; document the chosen rule). Prefer longer keyword matches when overlapping.

**Subcategories first:** collect all matching categories; if any subcategory matches, drop parent matches that are ancestors of a matching sub (or drop all parent matches when any sub matches — pick one consistent rule and test it). After that, require **exactly one** remaining category. Zero or ≥2 → fall through.

**Wallet:** zero or one wallet-name match against `wallet_names` (casefold substring/whole). ≥2 → fall through. Zero → `wallet_hint=None` (handler uses default wallet as today).

**Multi-op / transfer decline:** if message has transfer/exchange signals (keywords like перевод, обмен, с карты, на карту, exchange, etc. — keep a small explicit list) OR more than one distinct parseable amount OR multi-op connectors with amounts (`и`, `а также`, multiple sentences each with amount) → fall through. Be conservative: doubt → fall through.

**Eligible result:** single `ParsedOperation` with type expense or income (from which list matched), amount int, currency from amount suffix if present else None, category = matched category's **current name**, wallet_hint if matched, comment = remainder after stripping amount/category/date words (then handler still applies `strip_date_words` as today — either leave comment for handler or pre-strip consistently; match existing clear-op behavior).

---

### Task 1: Dictionary + pure prefilter + unit tests

**Files:**
- Create: `backend/app/parsing/cascade_keywords.py` — dict `translation_key -> list[str]` (RU+UZ from Appendix A, verbatim)
- Create: `backend/app/parsing/prefilter.py` — `try_prefilter(request: ParseRequest, *, expense_categories: list[tuple[str, str | None]], income_categories: list[tuple[str, str | None]]) -> ParsedOperation | None`
  - Need current names **and** translation_keys to apply the seed-name gate. `ParseRequest` today only has names. **Either** extend the prefilter call to accept category records (name, translation_key, parent_id) from the handler, **or** extend ParseRequest — prefer **not** changing ParseRequest/HttpParser contract: pass extra category metadata only into `try_prefilter` from the handler.
- Create: `backend/tests/test_phase16_prefilter.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class PrefilterCategory:
    name: str
    translation_key: str | None
    parent_id: object | None  # None = parent/top-level; for income always None


def try_prefilter(
    text: str,
    *,
    wallet_names: list[str],
    expense_categories: list[PrefilterCategory],
    income_categories: list[PrefilterCategory],
    seed_name_by_key: dict[str, str],  # translation_key -> seed RU name
) -> ParsedOperation | None:
    """Return one fully resolved op, or None to fall through."""
```

Handler builds `seed_name_by_key` from budget_seed constants (or prefilter imports seed maps itself — OK if it keeps coupling local).

- [ ] Unit tests: «такси 25 тысяч» → expense taxi amount 25000; two amounts → None; transfer keyword → None; ambiguous two categories → None; renamed food (name Питание, key food) + message «еда 10000» → None; renamed food + «питание 10000» → match Питание; no amount → None (fall through, not error).
- [ ] Implement.
- [ ] Commit: `feat(parsing): add rule-based quick-entry prefilter`

---

### Task 2: Wire into `process_quick_entry_text` only

**Files:**
- Modify: `backend/bot/quick_entry/handlers.py`
- Modify/create tests: `backend/tests/test_phase16_prefilter_handlers.py` (or extend `test_quick_entry_flow.py`)

**Wire sketch:**

```python
# After building wallet list + category lists (need translation_key + parent_id):
prefilter_op = try_prefilter(
    text,
    wallet_names=[w.name for w in wallets],
    expense_categories=...,
    income_categories=...,
)
if prefilter_op is not None:
    response = ParseResponse(operations=[prefilter_op])
    prefilter_hit = True
else:
    prefilter_hit = False
    parser = _get_parser()
    try:
        response = await parser.parse(parse_request)
    except ...
# later:
if not ambiguous_only and not prefilter_hit:
    spend_model_call(budget)
    await session.commit()
```

Load expense categories with name, translation_key, parent_id (extend existing `_list_expense_category_names` helper or add `_list_expense_categories_for_prefilter`). Same for income.

**Important:** `can_model_call` gate currently runs **before** parse. Spec says prefilter spends zero model calls. A prefilter hit should still be allowed when the daily model limit is exhausted — otherwise the cost-saving path is blocked by the model counter. **Implement:** run prefilter **before** the `can_model_call` check (after user/budget/default_wallet checks). If prefilter hits, skip the model-limit check and skip parser. If prefilter misses, then apply `can_model_call` as today before calling parser. This is a small reorder required by the feature's purpose; note it in the report.

- [ ] Integration tests with parser mock that `raise`s/`pytest.fail`s if called on «такси 25 тысяч»; assert no `spend_model_call` / daily_model_calls unchanged; fall-through cases assert parse called; voice tests still pass untouched.
- [ ] Commit: `feat(bot): wire text quick-entry prefilter before LLM parser`

---

### Task 3: Verify Task C

- [ ] Full `./venv/bin/pytest -q` ≥ 428
- [ ] `npx vitest run --reporter=dot` ≥ 206
- [ ] Report `/home/xon/Documents/finance-bot/.superpowers/sdd/task-c-report.md`: structure, amount util new vs reused, fail-safe walkthrough, acceptance 8.3 checklist.
