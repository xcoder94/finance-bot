# Phase 14b — Voice → Gemini audio (drop Speech-to-Text) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute. `composer-2.5-fast` is forbidden.

**Goal:** Rework voice quick entry so one Gemini call receives the OGG audio and returns structured operations directly — deleting Google Speech-to-Text entirely — while preserving every product behaviour from PRD §9 / phase-14 acceptance.

**Architecture:** Extend `ParseRequest` / `ParseResponse` additively with optional binary audio + speech/date signals. `HttpParser._post_google` attaches an `inlineData` audio part when present (Google-only). Voice handler downloads bytes → builds `ParseRequest` with audio → one `parser.parse` → branches on `speech_status` for §9 vs §7.9 vs cards. Delete `app/speech/*` and all `SPEECH_*` config. Text path keeps `text`-only requests and existing empty-`operations` → `MSG_NO_AMOUNT` behaviour unchanged.

**Tech Stack:** Python, httpx, Aiogram 3, pytest. No new packages. Backend only — frontend untouched (must stay 205 tests / 37 files).

## Global Constraints

- Spec: user Task A brief + `docs/tasks/phase-14-voice.md` product behaviour (mechanism changes) + PRD §9 + PRD §7.9 only.
- Audio-carrying path is Google-only. Model only from `PARSER_MODEL`. No `SPEECH_*` left anywhere. No hard-coded model id.
- Typing: `send_chat_action(..., action="typing")` immediately; no interim «Расшифровываю…».
- No speech-derived free text in any bot reply / button / callback — automated assertion required (harder without a transcript variable).
- Failure not recognised (exact): `Не разобрал голосовое. Попробуйте записать ещё раз или напишите текстом.`
- Failure no amount: existing `MSG_NO_AMOUNT` unchanged.
- Counters: same helpers; N ops in one voice → exactly 1 model call.
- Text path request/response contract additive only — all existing text-path tests must keep passing.
- Delete `backend/app/speech/*` entirely; remove `SPEECH_*` from `config.py`; remove speech overrides/imports from handlers.
- Explicit cache: changing `IMMUTABLE_PARSER_INSTRUCTIONS` changes `prompt_version()` → existing `google_cache.py` invalidates/rebuilds. No second invalidation mechanism. First live call after change may pay one cache-miss rebuild — expected.
- Phase 15 untouched until Task A fully committed + tested + reported.
- Branch: `mvp2/phase-14b-and-15` (already checked out). Do not create/switch/merge/rebase.
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Never edit / commit: `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/**`, `docs/tasks/*.md`, `docs/context/**`.
- Worker: `composer-2.5` only.
- Uzbek out of scope. Banned user-facing words: ошибка, сессия, сервер, токен, запрос.
- Confidence below average → write «not sure».
- Baseline on entry (orchestrator-measured): frontend **205 passed / 37 files**. Backend full suite requires PostgreSQL on `localhost:5432` — if unavailable, run with stub env bootstrap and report skipped DB tests; last known green on this codebase after phase 14 merge was **403 passed, 1 warning**. Test counts must only grow or stay equal except named Speech-to-Text tests removed and replaced (see Test removals below).

## Design decisions (section 7 — locked before coding)

### 1. Distinguishing «no speech» from «speech, no amount»

**Signal:** additive optional top-level field on the model JSON and `ParseResponse`:

```text
speech_status: "recognized" | "not_recognized" | null
```

- Text requests: field absent/null; ignored. Empty `operations` → `MSG_NO_AMOUNT` unconditionally (unchanged).
- Audio requests: model MUST set `speech_status`.
  - `"not_recognized"` → bot replies `MSG_VOICE_NOT_RECOGNIZED`, `spend_unparsed`, **no** card path. (`operations` should be `[]`; ignore any ops if present.)
  - `"recognized"` + empty countable ops → `MSG_NO_AMOUNT`, `spend_unparsed` (same as text).
  - `"recognized"` + ops → cards / existing pipeline.
  - Missing/invalid `speech_status` on an audio-carrying response → treat as `ParserMalformed` → `MSG_MODEL_FAIL`, **no** unparsed spend (our side failed).

Exact schema fragment in `IMMUTABLE_PARSER_INSTRUCTIONS`:

```text
{"operations":[...],"speech_status":"recognized|not_recognized"|null,"date_hint":"YYYY-MM-DD"|null}
```

Rules added to instructions:
- Text-only user turns: `speech_status` must be null; `date_hint` null unless the text contains a relative/absolute date you resolve.
- Audio-carrying turns: set `speech_status` to `not_recognized` when there is no intelligible speech (silence, noise, empty); otherwise `recognized`. Never invent operations when `not_recognized`.

### 2. Date words and comment cleanup without a transcript

**Date:** additive optional top-level `date_hint: str | None` on `ParseResponse` — ISO `YYYY-MM-DD` or null.

- Mutable payload for every request includes `"today": "<Asia/Tashkent YYYY-MM-DD>"` so the model can resolve «вчера» / weekdays / «N дней назад» against a known today.
- Bot applies `_finalize_date` rules (future → today; lookback > 31 days → today) via a small helper `apply_date_hint(date_hint: str | None, today: date) -> date` in `quick_entry_dates.py`. If `date_hint` is null/invalid → today.
- Text path: prefer existing `resolve_operation_date(text)` when `date_hint` is null (preserves current behaviour). If model also returns `date_hint` on text, still prefer `resolve_operation_date(text)` for text so text behaviour does not change. Voice path: use `apply_date_hint(response.date_hint, today)` only (no transcript to pattern-match).

**Comment cleanup:** instruct the model: never put relative date words in `comment`. Additionally, for any op, call `strip_date_words(op.comment, op.comment or "")` so markers that leaked into the comment are stripped using the comment itself as the scan source (works without a transcript). Text path keeps `strip_date_words(op.comment, text)` as today.

**Rate markers without transcript:** when `ParseRequest.audio_mime_type` is set, `effective_rate(op, source_text)` is bypassed — use `op.rate` if it is a positive int, else `None`. The immutable instructions already require rate only when a marker word was present; for audio the model is the gate. Text path unchanged (`effective_rate(op, text)`).

**No free-text leak:** `ParseResponse` MUST NOT carry a transcript field. `comment` / category / wallet hints are structured fields used on cards (same as text). Automated test plants a unique secret string only inside stubbed structured fields that must not appear *as a raw transcript dump*; specifically: plant `SECRET_AUDIO_LEAK` as a fake value that the stub would put in a forbidden channel — assert no reply contains a base64 audio blob, and assert that a stubbed `comment` equal to a secret marker only appears if it is the intended merchant/comment (same as text). Stronger rule for this rework: assert reply texts never contain the raw base64 of the uploaded audio and never contain a dedicated `transcript` / `speech_text` key value. Plant `SECRET_TRANSCRIPT`-style string as `ParseRequest` text for voice (`text=""` for voice) so there is no transcript variable; assert replies never include a planted `audio_base64` substring.

### 3. Provider gating

Before calling the parser on voice:

```python
from app.config import PARSER_PROVIDER, PARSER_API_KEY
if (PARSER_PROVIDER or "").lower() != "google" or not PARSER_API_KEY:
    await message.answer(MSG_MODEL_FAIL)
    return
```

Also: `HttpParser.parse` — if `request.audio_base64` is set and `self._provider != "google"`, raise `ParserUnavailable("audio requires google parser")`. No silent text-only fallback. Maps to `MSG_MODEL_FAIL`, no unparsed spend.

### 4. Explicit cache

Confirmed: `prompt_version()` hashes `IMMUTABLE_PARSER_INSTRUCTIONS + STATIC_CACHE_BALLAST`. Editing instructions auto-invalidates. Do not add a second invalidation path. Note in live-verification report that the first post-change call may rebuild the cache once.

## Binary content contract (also the Phase 15 reuse point)

```python
@dataclass(frozen=True)
class ParseRequest:
    text: str
    wallet_names: list[str]
    expense_category_names: list[str]
    income_category_names: list[str]
    audio_base64: str | None = None
    audio_mime_type: str | None = None  # e.g. "audio/ogg"
    # Phase 15 will add image_base64 / image_mime_type the same way — do not add them in Task A.

@dataclass(frozen=True)
class ParseResponse:
    operations: list[ParsedOperation]
    speech_status: Literal["recognized", "not_recognized"] | None = None
    date_hint: str | None = None
```

`build_mutable_parser_payload` JSON keys: existing four + `"today": "YYYY-MM-DD"`. Audio bytes are **not** in the JSON text part — they are a separate Gemini `parts[]` entry:

```python
parts = [{"text": user_content}]
if request.audio_base64 and request.audio_mime_type:
    parts.append({
        "inline_data": {  # Gemini REST uses camelCase inlineData in JSON
            "mime_type": request.audio_mime_type,
            "data": request.audio_base64,
        }
    })
```

Use the exact key casing Gemini's `generateContent` REST API expects for the installed docs pattern already used in this repo (`inlineData` / `mimeType` camelCase — verify against a current Google example in the worker task; if unsure, check https://ai.google.dev/api/caching or existing measure script style and prefer camelCase `inlineData`/`mimeType` as used by the Generative Language API JSON).

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/parsing/types.py` | Additive `ParseRequest` audio fields; `ParseResponse.speech_status`, `date_hint` |
| `backend/app/parsing/prompt.py` | Extend `IMMUTABLE_PARSER_INSTRUCTIONS` + `build_mutable_parser_payload` (`today`) |
| `backend/app/parsing/http_adapter.py` | Parse new response fields; attach audio part in `_post_google`; gate non-google audio |
| `backend/app/parsing/stub.py` | Support audio requests in stub (key by a sentinel or `audio_base64` presence) |
| `backend/app/services/quick_entry_dates.py` | Add `apply_date_hint` |
| `backend/app/config.py` | Delete `SPEECH_*` |
| `backend/app/speech/**` | **Delete entire package** |
| `backend/bot/quick_entry/handlers.py` | Voice → audio ParseRequest; speech_status branch; remove speech client; date/rate audio paths |
| `backend/tests/test_phase14_voice.py` | Rewrite for direct-Gemini path |
| Frontend | **Do not touch** |

## Test removals (must name each)

Remove these Speech-to-Text-specific tests (invalid after delete):

1. `test_google_speech_client_posts_ogg_and_returns_transcript`
2. `test_google_speech_client_empty_results_returns_empty_string`
3. `test_google_speech_client_http_error_raises_unavailable`
4. `test_get_speech_client_inactive_without_credentials`
5. `test_get_speech_client_google_when_configured`
6. `test_get_speech_client_inactive_for_non_google_provider`
7. `test_config_exposes_speech_env_vars`

Keep / replace with equivalents:

- `test_msg_voice_not_recognized_constant` — keep
- `test_process_quick_entry_text_is_importable` — keep
- Acceptance class tests — rewrite to stub **parser** (not speech): typing, card path, noise→§9 via `speech_status=not_recognized`, provider gate→`MSG_MODEL_FAIL`, no-amount via `recognized`+empty ops, three ops→1 model call, no audio/base64/secret leak in replies
- New: `test_http_parser_google_posts_inline_audio_part` (MockTransport)
- New: `test_http_parser_rejects_audio_when_provider_not_google`
- New: `test_parse_response_speech_status_and_date_hint_parsed`
- New: `test_apply_date_hint_*`
- New: `test_config_has_no_speech_env_vars`

## Shared handler flow (locked)

```python
async def handle_quick_entry_voice(message, bot):
    # typing immediately
    # download ogg bytes
    # provider gate → MSG_MODEL_FAIL
    # build ParseRequest(text="", audio_base64=b64, audio_mime_type="audio/ogg", wallets...)
    # parser.parse → on ParserUnavailable|Malformed → MSG_MODEL_FAIL (no unparsed)
    # if response.speech_status == "not_recognized": spend_unparsed; MSG_VOICE_NOT_RECOGNIZED; return
    # else: feed into shared card pipeline with source_text="" and date from apply_date_hint
```

Prefer extracting the post-parse card loop from `process_quick_entry_text` into something like `process_quick_entry_response(message, bot, *, user session state, response, source_text: str)` so text and voice share cards/counters without voice calling `process_quick_entry_text` with a fake transcript. Text keeps building `ParseRequest` from message text and calling parse then the shared response processor.

---

### Task 1: Types + prompt + date_hint helper + parser payload `today`

**Files:**
- Modify: `backend/app/parsing/types.py`
- Modify: `backend/app/parsing/prompt.py`
- Modify: `backend/app/services/quick_entry_dates.py`
- Modify: `backend/tests/test_phase14_voice.py` (new unit tests at top; leave old speech tests until Task 4 deletes them, OR delete speech unit tests in Task 4 only — for TDD, add new tests here that fail on missing fields)
- Modify: `backend/tests/test_quick_entry_parser.py` only if existing prompt tests break on instruction text changes — update assertions to accept new schema fields in the instructions string

**Interfaces:**
- Produces:
  - `ParseRequest.audio_base64: str | None = None`, `audio_mime_type: str | None = None`
  - `ParseResponse.speech_status: Literal["recognized","not_recognized"] | None = None`, `date_hint: str | None = None`
  - `build_mutable_parser_payload` includes `"today": tashkent_today().isoformat()` (import `tashkent_today` from `quick_entry_dates`)
  - `IMMUTABLE_PARSER_INSTRUCTIONS` documents `speech_status`, `date_hint`, audio rules, comment must not contain date words, rate only with spoken marker
  - `apply_date_hint(date_hint: str | None, today: date | None = None) -> date`
- Consumes: existing types/prompt/dates
- Does not yet: http adapter audio parts; handler; delete speech

- [ ] **Step 1: Write failing tests**

```python
# in test_phase14_voice.py (new section) or test_quick_entry_parser.py
from datetime import date
from app.parsing.types import ParseRequest, ParseResponse
from app.parsing.prompt import IMMUTABLE_PARSER_INSTRUCTIONS, build_mutable_parser_payload
from app.services.quick_entry_dates import apply_date_hint

def test_parse_request_accepts_optional_audio_fields():
    req = ParseRequest(
        text="",
        wallet_names=[],
        expense_category_names=[],
        income_category_names=[],
        audio_base64="AAAA",
        audio_mime_type="audio/ogg",
    )
    assert req.audio_base64 == "AAAA"
    assert req.audio_mime_type == "audio/ogg"

def test_parse_response_accepts_speech_status_and_date_hint():
    r = ParseResponse(operations=[], speech_status="not_recognized", date_hint="2026-08-03")
    assert r.speech_status == "not_recognized"
    assert r.date_hint == "2026-08-03"

def test_mutable_payload_includes_today():
    req = ParseRequest(text="x", wallet_names=[], expense_category_names=[], income_category_names=[])
    payload = build_mutable_parser_payload(req)
    assert '"today"' in payload

def test_instructions_document_speech_status_and_date_hint():
    assert "speech_status" in IMMUTABLE_PARSER_INSTRUCTIONS
    assert "date_hint" in IMMUTABLE_PARSER_INSTRUCTIONS

def test_apply_date_hint_yesterday_iso():
    today = date(2026, 8, 4)
    assert apply_date_hint("2026-08-03", today) == date(2026, 8, 3)

def test_apply_date_hint_too_old_becomes_today():
    today = date(2026, 8, 4)
    assert apply_date_hint("2026-01-01", today) == today

def test_apply_date_hint_none_is_today():
    today = date(2026, 8, 4)
    assert apply_date_hint(None, today) == today
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && source /tmp/finance-bot-test-env.sh && ./venv/bin/pytest tests/test_phase14_voice.py::test_parse_request_accepts_optional_audio_fields tests/test_phase14_voice.py::test_parse_response_accepts_speech_status_and_date_hint tests/test_phase14_voice.py::test_mutable_payload_includes_today tests/test_phase14_voice.py::test_instructions_document_speech_status_and_date_hint tests/test_phase14_voice.py::test_apply_date_hint_yesterday_iso tests/test_phase14_voice.py::test_apply_date_hint_too_old_becomes_today tests/test_phase14_voice.py::test_apply_date_hint_none_is_today -q
```

- [ ] **Step 3: Implement types, prompt, `apply_date_hint`**

`apply_date_hint`: parse `YYYY-MM-DD`; on failure return today; then call existing `_finalize_date(resolved, today)`.

Update instructions to the new JSON schema line including `speech_status` and `date_hint`, plus bullet rules from Design decisions §1–2.

- [ ] **Step 4: Run focused tests — PASS; run `./venv/bin/pytest tests/test_quick_entry_parser.py -q` — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/types.py backend/app/parsing/prompt.py backend/app/services/quick_entry_dates.py backend/tests/test_phase14_voice.py backend/tests/test_quick_entry_parser.py
git commit -m "$(cat <<'EOF'
feat(parsing): add audio request fields, speech_status, date_hint

EOF
)"
```

---

### Task 2: HttpParser — parse new fields + Google audio part + non-google gate

**Files:**
- Modify: `backend/app/parsing/http_adapter.py`
- Modify: `backend/tests/test_phase14_voice.py`

**Interfaces:**
- Consumes: Task 1 types/prompt
- Produces:
  - `_parse_operations_payload` becomes `_parse_response_payload(data) -> ParseResponse` reading `operations`, optional `speech_status`, optional `date_hint` (validate enums/types; unknown `speech_status` → `ParserMalformed`)
  - `_post_google`: if audio present, append inlineData part; if audio present and provider≠google — unreachable if `parse` gates first
  - `HttpParser.parse`: if `request.audio_base64` and provider ≠ `"google"` → `ParserUnavailable`
  - Return `ParseResponse(operations=..., speech_status=..., date_hint=...)`

- [ ] **Step 1: Failing tests**

```python
@pytest.mark.anyio
async def test_http_parser_google_posts_inline_audio_part():
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": json.dumps({
                "operations": [{
                    "type": "expense", "amount": 25000, "currency": "UZS",
                    "wallet_hint": None, "category": "Такси", "comment": None,
                    "from_wallet_hint": None, "to_wallet_hint": None, "rate": None,
                }],
                "speech_status": "recognized",
                "date_hint": None,
            })}]}}]
        })
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = HttpParser("google", "key", "env-model", client=client)
        resp = await parser.parse(ParseRequest(
            text="", wallet_names=["Карта"], expense_category_names=["Такси"],
            income_category_names=[], audio_base64="QQ==", audio_mime_type="audio/ogg",
        ))
    assert resp.speech_status == "recognized"
    parts = captured["body"]["contents"][0]["parts"]
    assert any("inlineData" in p or "inline_data" in p for p in parts)

@pytest.mark.anyio
async def test_http_parser_rejects_audio_when_not_google():
    parser = HttpParser("openai", "key", "m")
    with pytest.raises(ParserUnavailable):
        await parser.parse(ParseRequest(
            text="", wallet_names=[], expense_category_names=[], income_category_names=[],
            audio_base64="QQ==", audio_mime_type="audio/ogg",
        ))
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement adapter changes** (keep text-only Google posts identical when audio is None)

- [ ] **Step 4: PASS + `./venv/bin/pytest tests/test_quick_entry_parser.py -q` PASS**

- [ ] **Step 5: Commit** `feat(parsing): send Gemini inline audio and parse speech_status`

---

### Task 3: Voice handler rework + stub parser audio support

**Files:**
- Modify: `backend/bot/quick_entry/handlers.py`
- Modify: `backend/app/parsing/stub.py`
- Modify: `backend/tests/test_phase14_voice.py` (acceptance tests rewritten to stub parser)

**Interfaces:**
- Consumes: Task 1–2
- Produces:
  - Voice handler: typing → download → provider gate → `ParseRequest` with base64 audio → parse → `speech_status` branch → shared response processing
  - Remove `set_speech_client_override`, `_get_speech_client`, speech imports
  - `StubParser`: if `request.audio_base64` is set, look up responses under key `"__audio__"` or a provided `audio_responses` map; tests pass `StubParser(audio_responses={...})` or override `parse` via a small `StubAudioParser` in the test file
  - Text `process_quick_entry_text` still works; shared post-parse path uses `source_text` for `resolve_operation_date` / `effective_rate` / `strip_date_words` when non-empty; when voice (`source_text==""`), use `apply_date_hint` + audio rate rule + comment self-strip

Recommended stub for tests (in test file):

```python
class FixedParser:
    def __init__(self, response: ParseResponse):
        self.response = response
        self.calls = []
    async def parse(self, request: ParseRequest) -> ParseResponse:
        self.calls.append(request)
        return self.response
```

- [ ] **Step 1: Rewrite acceptance tests** (typing, card, noise/not_recognized, provider fail, no amount, three ops / 1 call, no leak of audio_base64 / secret). Remove reliance on `StubSpeech` / `set_speech_client_override`.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement handler + stub**

Provider gate uses `PARSER_PROVIDER` / `PARSER_API_KEY` from `app.config` (monkeypatch in tests).

For «provider fail without unparsed» test: monkeypatch `PARSER_PROVIDER` to `"openai"` or `PARSER_API_KEY` to `None`.

Missing `speech_status` on audio response → `MSG_MODEL_FAIL` (raise/handle as malformed).

- [ ] **Step 4: PASS focused + ensure text flow tests still pass:** `./venv/bin/pytest tests/test_quick_entry_flow.py tests/test_phase14_voice.py -q`

- [ ] **Step 5: Commit** `feat(bot): parse voice audio via Gemini; drop speech client usage`

---

### Task 4: Delete `app/speech/*` + `SPEECH_*` + rewrite leftover tests

**Files:**
- Delete: `backend/app/speech/__init__.py`, `base.py`, `factory.py`, `google_client.py`
- Modify: `backend/app/config.py` — remove SPEECH_* lines
- Modify: `backend/tests/test_phase14_voice.py` — remove the 7 speech-client tests listed above; add `test_config_has_no_speech_env_vars`

**Interfaces:**
- Produces: no `app.speech` package; no `SPEECH_*` in config; no imports of speech anywhere (`rg speech` / `SPEECH_` clean except historical docs)

- [ ] **Step 1: Failing test**

```python
def test_config_has_no_speech_env_vars():
    from app import config
    assert not hasattr(config, "SPEECH_PROVIDER")
    assert not hasattr(config, "SPEECH_API_KEY")
    assert not hasattr(config, "SPEECH_MODEL")
```

- [ ] **Step 2: Delete package + config lines; remove obsolete tests; fix any import errors**

- [ ] **Step 3: `rg -n 'app\\.speech|SPEECH_|SpeechClient|SpeechUnavailable|set_speech' backend --glob '!venv/**'` → only acceptable hits none**

- [ ] **Step 4: Full backend suite** `./venv/bin/pytest -q` — count ≥ prior green (403) minus 7 removed plus new tests; frontend untouched `npx vitest run` still 205/37

- [ ] **Step 5: Commit** `chore: remove Speech-to-Text module and SPEECH_* config`

---

### Task 5: Live verification + suite gate report

**Files:**
- Create: `docs/superpowers/plans/phase14b-task5-live-report.md` (or append to orchestrator notes — worker writes this report file under `docs/superpowers/plans/`)
- Optional tiny script under `backend/scripts/` only if needed for audio smoke — prefer inline `python -c` / small script `backend/scripts/smoke_voice_audio.py` that reads an ogg path and prints `ParseResponse`

**Steps:**

- [ ] **Step 1: Run** `cd backend && ./venv/bin/python scripts/measure_prompt_cache.py` with real `PARSER_*` (from env). Capture full stdout/stderr verbatim into the report. If `.env` unreadable in agent, document blocker exactly (HTTP N/A) — do not fake success.

- [ ] **Step 2: Produce short OGG_OPUS sample** — e.g. `ffmpeg -f lavfi -i "sine=f=440:d=2" -c:a libopus /tmp/tone.ogg` is **not** speech; prefer `espeak`/`ffmpeg` with Russian phrase if available, or record via `ffmpeg` from `anullsrc` for noise sample. State provenance in report. Call `HttpParser` / shared parse with real credentials; print raw parsed JSON/response.

- [ ] **Step 3: Noise/silence sample** through same path; confirm `speech_status=not_recognized` or report exact model output if different.

- [ ] **Step 4: Full `./venv/bin/pytest -q` and frontend vitest; commit report if new script added**

```bash
git add backend/scripts/smoke_voice_audio.py docs/superpowers/plans/phase14b-task5-live-report.md  # only if created
git commit -m "$(cat <<'EOF'
docs: phase 14b live verification notes

EOF
)"
```

---

## Self-review (plan author)

1. **Spec coverage:** §7 Q1–Q4 resolved; hard rules 1–12 mapped to tasks; acceptance §10 items covered by Task 3 tests + Task 5 live; speech module deletion Task 4; text path additive Task 1–2.
2. **Placeholders:** none intentional.
3. **Type consistency:** `speech_status` / `date_hint` / `audio_base64` / `audio_mime_type` names stable across tasks.
4. **Cache:** noted as already handled via `prompt_version()`.
5. **Phase 15:** not started; binary contract designed for image field reuse later.

## Execution

Orchestrator executes via subagent-driven-development with `composer-2.5` per task. Do not pause for execution-choice prompt — user brief already ordered full execution through Task A then Task B.
