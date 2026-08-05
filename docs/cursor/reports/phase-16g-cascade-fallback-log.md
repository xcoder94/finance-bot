# Report — Phase 16g: cascade fallback logging (data collection only)

Branch: `mvp2/phase-16-cascade-demo-protected-support` (continued; no new branch)  
Date: 2026-08-05  
Orchestrator: Cursor Grok 4.5  
Workers: `composer-2.5` only

---

## Tests

| Moment | Backend (`pytest -q`) | Frontend (`npx vitest run`) |
|--------|------------------------|-----------------------------|
| Baseline (before changes) | **502 passed**, 1 warning | **42 files / 244 passed** |
| Final (after changes) | **515 passed**, 1 warning | **42 files / 244 passed** |

Delta: **+13** backend tests (prefilter reason coverage + handler cascade log). Frontend unchanged.

Disabled / stubbed / mocked: **none**.

(Test-only: `session.flush` monkeypatch to simulate log-write failure; `StubParser` as in existing handler tests — not product stubs.)

---

## What shipped

### 1. Table + model + migration

- New append-only table `cascade_fallback_log`:
  - `id` (UUID PK), `family_budget_id` (FK), `telegram_user_id` (bigint),
    `text` (raw message), `reason`, `created_at` (timestamptz, default now())
- Model: `backend/app/models/cascade_fallback_log.py` (`CascadeFallbackLog`)
- Registered in `backend/app/models/__init__.py`
- Alembic: `backend/alembic/versions/v2e3f4a5b6c7_cascade_fallback_log.py`
  (`down_revision=u1d2e3f4a5b6`)

No update/delete path from the bot. No retention job. No dashboard / admin UI.

### 2. `try_prefilter` reports None-reason

`backend/app/parsing/prefilter.py` now returns:

```python
@dataclass(frozen=True)
class PrefilterResult:
    operation: ParsedOperation | None
    reason: PrefilterReason | None  # set iff operation is None
```

Reason codes (unchanged parse decisions):

| Reason | When |
|--------|------|
| `transfer_signal` | wallet-transfer / exchange phrase |
| `multi_operation` | >1 amount or multi-op connector |
| `amount_not_singular` | 0 or >1 amount (incl. empty/whitespace text) |
| `no_category_match` | zero category keyword matches |
| `category_ambiguous` | more than one category matched |
| `wallet_ambiguous` | more than one wallet name matched |
| `prefilter_disabled` | handler only — `prefilter_enabled=False` |

Existing prefilter tests updated for `.operation` / `.reason`; outcomes unchanged.

### 3. Handler insert (text quick-entry only)

In `process_quick_entry_text` (`backend/bot/quick_entry/handlers.py`):

- When `prefilter_hit` is False, insert one `CascadeFallbackLog` row **before**
  `can_model_call` (throttled messages are captured too).
- Full raw `text`, not an extracted keyword; no dedup at write time.
- Best-effort: wrapped in `async with session.begin_nested():` + try/except so a
  logging failure cannot poison the outer session or block the user reply
  (same spirit as phase-16d error logging).
- Voice and receipt-photo paths untouched.
- `CASCADE_KEYWORDS` untouched. User-facing behaviour / LLM fallback unchanged.

### Orchestrator review fix

Worker initially flushed the log on the outer session. A failed `flush` would
leave SQLAlchemy needing a rollback and could block the reply path. Fixed to
use a nested savepoint; the failure test now raises on `flush` when a
`CascadeFallbackLog` is pending.

---

## New / extended tests

- `backend/tests/test_cascade_fallback_log.py`
  - miss logs even when model daily limit exhausted
  - hit writes no log row
  - logging failure does not block reply
  - `prefilter_disabled` when flag off
- `backend/tests/test_phase16_prefilter.py`
  - return shape updates
  - `TestPrefilterReasons` — each None-reason

---

## Files touched (this phase)

| Path | Change |
|------|--------|
| `backend/app/models/cascade_fallback_log.py` | **created** |
| `backend/alembic/versions/v2e3f4a5b6c7_cascade_fallback_log.py` | **created** |
| `backend/tests/test_cascade_fallback_log.py` | **created** |
| `backend/app/models/__init__.py` | register model |
| `backend/app/parsing/prefilter.py` | `PrefilterResult` + reasons |
| `backend/bot/quick_entry/handlers.py` | best-effort log insert |
| `backend/tests/test_phase16_prefilter.py` | shape + reason tests |

No `docs/PRD.md` edits for this round. No commit (not requested).

---

## Notes for deploy / review

1. Apply Alembic revision `v2e3f4a5b6c7` before relying on the log in a given environment (worker applied it locally for DB-backed tests).
2. Periodic PM review of the table (group by normalized text + reason) remains an on-demand assistant query — not built in this phase.
