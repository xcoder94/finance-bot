# Phase 13 — Prompt Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute. `composer-2.5-fast` is forbidden.

**Goal:** Add Google Gemini as a parser provider and cache the static parser instructions via Gemini explicit context caching so one installation-wide cache serves every family, with full-prompt fallback when the cache is missing.

**Architecture:** Keep `HttpParser` as the single HTTP adapter (openai / anthropic / google). Google uses Gemini REST (`generativelanguage.googleapis.com/v1beta`) over existing `httpx` — no new SDK package. A small `google_cache.py` module creates / references / patches TTL / deletes a single `CachedContent` whose `systemInstruction` is the static blob. Process-local memory holds the active cache name; Gemini `displayName` + list/delete enforce “exactly one” across restarts. Missing/expired cache never fails the user call: parse with the full static text, then rebuild the cache in a background `asyncio` task.

**Tech Stack:** Python, httpx, Aiogram/FastAPI bot path (parser only), pytest. No new packages. Backend only — frontend untouched (must stay 205 tests / 37 files).

## Global Constraints

- Spec: `docs/tasks/phase-13-prompt-caching.md` + PRD §20 only.
- Provider value for Gemini: exactly `"google"` (lowercase). Model only from `PARSER_MODEL` — never hard-code a model string.
- Static cache body = `IMMUTABLE_PARSER_INSTRUCTIONS` plus a fixed inert ballast (see below). No wallet name, date, member name, or message text may enter the static body. Variable tail remains `build_mutable_parser_payload()`.
- Exactly one cache for the whole installation — never per-family, even as a temporary step.
- Cache lifetime: long TTL, extended in the background on use; recreate only when prompt version changes; old cache must be deleted on version change (not merely abandoned).
- Missing/expired cache → ordinary full-prompt parse succeeds; rebuild in background; never fail quick entry because of cache.
- Success metric ≥90% cached tokens on one measured call — requires live Gemini credentials. If absent, report blocked; do not invent a number.
- No user-facing copy or behaviour changes. Voice (§9) / receipt-photo (§10) out of scope. Uzbek out of scope.
- Do **not** edit `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/**`, `docs/tasks/*.md`, `docs/context/handoff.md`, `docs/context/cursor-prompt-*.md`.
- Do **not** touch `backend/bot/quick_entry/cards.py`’s `MINI_APP_URL` import.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-13-prompt-caching` (already checked out — do not create/switch/merge/rebase).
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Baseline on entry: backend `382 passed, 1 warning`; frontend `205` vitest / `37` files. Numbers may only grow. No existing test deleted or weakened. Frontend must end at 205 / 37.
- Forbidden user-facing words remain: ошибка, сессия, сервер, токен, запрос (this phase adds no user-facing text).
- Confidence below average → write «not sure», do not guess.
- Conversation/report language with customer is Russian; this plan is English (docs/).
- Stop at end of Phase 13 — no Phase 14.

## Gemini API surface (verified from current docs — do not invent)

Base: `https://generativelanguage.googleapis.com/v1beta`

| Action | Method | Path |
|--------|--------|------|
| Create cache | `POST` | `/cachedContents?key={API_KEY}` |
| List caches | `GET` | `/cachedContents?key={API_KEY}` |
| Get cache | `GET` | `/{name}?key={API_KEY}` (`name` = `cachedContents/{id}`) |
| Extend TTL | `PATCH` | `/{name}?key={API_KEY}` body `{"ttl":"{seconds}s"}` |
| Delete cache | `DELETE` | `/{name}?key={API_KEY}` |
| Generate | `POST` | `/models/{model}:generateContent?key={API_KEY}` |

Create body (static only — no family data):

```json
{
  "model": "models/{PARSER_MODEL}",
  "displayName": "chontak-parser-{prompt_version}",
  "systemInstruction": {"parts": [{"text": "<static_cache_text()>"}]},
  "ttl": "604800s"
}
```

Generate with cache:

```json
{
  "cachedContent": "cachedContents/{id}",
  "contents": [{"role": "user", "parts": [{"text": "<mutable payload>"}]}]
}
```

Generate full-prompt fallback (no cache):

```json
{
  "systemInstruction": {"parts": [{"text": "<static_cache_text()>"}]},
  "contents": [{"role": "user", "parts": [{"text": "<mutable payload>"}]}]
}
```

Response text path: `candidates[0].content.parts[0].text`.  
Usage for measurement: `usageMetadata.cachedContentTokenCount` / `usageMetadata.promptTokenCount` (JSON field names as returned by the API).

**Minimum size constraint (implementation necessity):** `IMMUTABLE_PARSER_INSTRUCTIONS` is ~848 chars (~212 tokens). Gemini explicit caching requires a minimum of **2048** tokens (Gemini 2 family) or **4096** (Gemini 3 family). Without padding, create fails and the ≥90% metric is unreachable. Therefore `static_cache_text()` = `IMMUTABLE_PARSER_INSTRUCTIONS` + fixed inert ballast (ASCII-only, no family data) sized to ≥4096 approx tokens. Ballast is part of the static blob for Google only (openai/anthropic keep sending bare `IMMUTABLE_PARSER_INSTRUCTIONS`). Flagged as “not sure” for the PM if they prefer expanding real instructions instead.

**TTL:** Gemini has no infinite TTL. Use `604800s` (7 days) on create and on background extend. “Permanent” = keep extending; recreate only on prompt-version change.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/parsing/prompt.py` | Keep `IMMUTABLE_PARSER_INSTRUCTIONS`; add `STATIC_CACHE_BALLAST`, `static_cache_text()`, `prompt_version()` (sha256 hex of static text, 16 chars) |
| `backend/app/parsing/google_cache.py` | Gemini cache CRUD + in-process registry; version reconcile (delete old, create new) |
| `backend/app/parsing/http_adapter.py` | Add `provider=="google"` generate path; use cache when available; fallback + schedule rebuild |
| `backend/tests/test_phase13_prompt_caching.py` | Assembly, google transport, cache miss → transaction, version delete |
| `backend/scripts/measure_prompt_cache.py` | Optional live measurement; exits blocked without credentials |
| `backend/tests/test_quick_entry_parser.py` | Leave existing tests intact (may gain a google extraction case only if Task 2 needs it in the phase-13 file instead) |

---

### Task 1: Prompt version + static/mutable assembly assertions

**Files:**
- Modify: `backend/app/parsing/prompt.py`
- Create: `backend/tests/test_phase13_prompt_caching.py`

**Interfaces:**
- Produces:
  - `STATIC_CACHE_BALLAST: str` — fixed inert text, length such that `len(static_cache_text()) // 4 >= 4096`
  - `static_cache_text() -> str` — `IMMUTABLE_PARSER_INSTRUCTIONS + STATIC_CACHE_BALLAST`
  - `prompt_version() -> str` — first 16 hex chars of `hashlib.sha256(static_cache_text().encode()).hexdigest()`
- Consumes: existing `IMMUTABLE_PARSER_INSTRUCTIONS`, `build_mutable_parser_payload`, `ParseRequest`
- Does **not** change: wording of `IMMUTABLE_PARSER_INSTRUCTIONS` itself (append ballast separately)

- [ ] **Step 1: Write failing tests** in `backend/tests/test_phase13_prompt_caching.py`

```python
"""Phase 13 — prompt caching (Google explicit cache)."""

from __future__ import annotations

import json
import re

from app.parsing.prompt import (
    IMMUTABLE_PARSER_INSTRUCTIONS,
    build_mutable_parser_payload,
    build_parser_messages,
    prompt_version,
    static_cache_text,
)
from app.parsing.types import ParseRequest


FAMILY_MARKERS = (
    "Карта сум",
    "Наличный сум",
    "такси 25 тысяч",
    "Алишер",
    "2026-08-04",
)


def _sample_request() -> ParseRequest:
    return ParseRequest(
        text="такси 25 тысяч",
        wallet_names=["Карта сум", "Наличный сум"],
        expense_category_names=["Такси", "Еда"],
        income_category_names=["Зарплата"],
    )


def test_static_cache_text_is_stable_and_large_enough():
    a = static_cache_text()
    b = static_cache_text()
    assert a == b
    assert a.startswith(IMMUTABLE_PARSER_INSTRUCTIONS)
    assert len(a) // 4 >= 4096


def test_static_blob_contains_no_family_data():
    static = static_cache_text()
    for marker in FAMILY_MARKERS:
        assert marker not in static
    assert "wallet_names" not in static
    # mutable fields must not appear as substitution slots in static
    assert "{text}" not in static
    assert "{wallet" not in static.lower()


def test_mutable_tail_holds_wallets_message_not_in_static():
    req = _sample_request()
    mutable = build_mutable_parser_payload(req)
    payload = json.loads(mutable)
    assert payload["text"] == "такси 25 тысяч"
    assert payload["wallet_names"] == ["Карта сум", "Наличный сум"]
    assert "такси 25 тысяч" not in static_cache_text()
    assert "Карта сум" not in static_cache_text()


def test_prompt_version_changes_when_static_changes(monkeypatch):
    v1 = prompt_version()
    assert re.fullmatch(r"[0-9a-f]{16}", v1)
    import app.parsing.prompt as prompt_mod

    monkeypatch.setattr(
        prompt_mod,
        "STATIC_CACHE_BALLAST",
        prompt_mod.STATIC_CACHE_BALLAST + "x",
    )
    v2 = prompt_version()
    assert v2 != v1


def test_build_parser_messages_still_system_then_user():
    req = _sample_request()
    messages = build_parser_messages(req)
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == IMMUTABLE_PARSER_INSTRUCTIONS
    assert messages[1]["content"] == build_mutable_parser_payload(req)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q`
Expected: FAIL — `static_cache_text` / `prompt_version` / `STATIC_CACHE_BALLAST` not defined.

- [ ] **Step 3: Minimal implementation** in `backend/app/parsing/prompt.py`

Add after `IMMUTABLE_PARSER_INSTRUCTIONS`:

```python
import hashlib

# Inert ballast so Gemini explicit-cache minimum (≥4096 tokens on Gemini 3)
# is met and a single call can show ≥90% cached tokens. No family data.
STATIC_CACHE_BALLAST = (
    "\n\n# cache-ballast\n" + (".".join(["ballast"] * 200) + "\n") * 80
)


def static_cache_text() -> str:
    return IMMUTABLE_PARSER_INSTRUCTIONS + STATIC_CACHE_BALLAST


def prompt_version() -> str:
    digest = hashlib.sha256(static_cache_text().encode("utf-8")).hexdigest()
    return digest[:16]
```

Adjust the ballast multiplier so `len(static_cache_text()) // 4 >= 4096` (verify in the test). Keep `import hashlib` at top of file with other imports; do not leave a mid-file import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q`
Expected: all Task 1 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/prompt.py backend/tests/test_phase13_prompt_caching.py
git commit -m "$(cat <<'EOF'
feat(parsing): add static cache text and prompt version id

EOF
)"
```

---

### Task 2: Google provider full-prompt path (no caching yet)

**Files:**
- Modify: `backend/app/parsing/http_adapter.py`
- Modify: `backend/tests/test_phase13_prompt_caching.py`

**Interfaces:**
- Produces: `HttpParser` accepts `provider="google"`; posts to
  `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}`
  with `systemInstruction` = `static_cache_text()` and user content = mutable payload; extracts text from `candidates[0].content.parts[*].text` joined.
- Consumes: `static_cache_text`, `build_mutable_parser_payload`, existing retry/malformed logic
- Does **not** yet: create or reference CachedContent

- [ ] **Step 1: Write failing tests**

```python
import httpx
import pytest

from app.parsing.http_adapter import HttpParser
from app.parsing.types import ParseRequest, ParserMalformed


def _google_ok_body(ops_json: str) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": ops_json}], "role": "model"}}
        ],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 20,
            "totalTokenCount": 120,
        },
    }


@pytest.mark.anyio
async def test_google_full_prompt_parse_succeeds():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        ops = (
            '{"operations":[{"type":"expense","amount":25000,"currency":"UZS",'
            '"wallet_hint":null,"category":"Такси","comment":null,'
            '"from_wallet_hint":null,"to_wallet_hint":null,"rate":null}]}'
        )
        return httpx.Response(200, json=_google_ok_body(ops))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    parser = HttpParser("google", "test-key", "test-model-from-env", client=client)
    response = await parser.parse(_sample_request())
    assert response.operations[0].amount == 25000
    assert "generateContent" in seen["url"]
    assert "test-model-from-env" in seen["url"]
    assert "key=test-key" in seen["url"]
    assert "cachedContent" not in seen["body"]
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == static_cache_text()
    assert json.loads(seen["body"]["contents"][0]["parts"][0]["text"])["text"] == (
        "такси 25 тысяч"
    )
    await client.aclose()


@pytest.mark.anyio
async def test_google_unsupported_without_model():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    parser = HttpParser("google", "test-key", "", client=client)
    with pytest.raises(ParserMalformed):
        await parser.parse(_sample_request())
    await client.aclose()
```

- [ ] **Step 2: Run tests — expect FAIL** (google still unsupported)

Run: `cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py::test_google_full_prompt_parse_succeeds -q`

- [ ] **Step 3: Implement google branch**

In `_extract_text_from_provider_body`, add:

```python
if provider == "google":
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ParserMalformed("google response missing candidates")
    content = candidates[0].get("content")
    if not isinstance(content, dict):
        raise ParserMalformed("google response missing content")
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ParserMalformed("google response missing parts")
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
    if not texts:
        raise ParserMalformed("google response missing text")
    return "".join(texts)
```

In `parse`, allow `provider in ("openai", "anthropic", "google")`.

In `_post`, after anthropic/openai branches, add google:

```python
if self._provider == "google":
    model = self._model  # never hard-code
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    return await client.post(
        url,
        params={"key": self._api_key},
        headers={"Content-Type": "application/json"},
        json={
            "systemInstruction": {
                "parts": [{"text": static_cache_text()}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_content}],
                }
            ],
        },
    )
```

Import `static_cache_text` from `app.parsing.prompt`. Keep openai/anthropic paths unchanged (still use `IMMUTABLE_PARSER_INSTRUCTIONS` / `build_parser_messages`).

- [ ] **Step 4: Run Task 1+2 tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/http_adapter.py backend/tests/test_phase13_prompt_caching.py
git commit -m "$(cat <<'EOF'
feat(parsing): add Google Gemini full-prompt provider branch

EOF
)"
```

---

### Task 3: Gemini explicit cache manager

**Files:**
- Create: `backend/app/parsing/google_cache.py`
- Modify: `backend/tests/test_phase13_prompt_caching.py`

**Interfaces:**
- Produces:
  - `CACHE_DISPLAY_PREFIX = "chontak-parser-"`
  - `cache_display_name(version: str) -> str` → `chontak-parser-{version}`
  - `GooglePromptCache` class with:
    - `__init__(self, api_key: str, model: str, client: httpx.AsyncClient | None = None)`
    - `async def ensure_cache(self) -> str | None` — return cache resource name for current `prompt_version()`, creating if needed; on version change delete all installation caches with prefix then create one; return `None` on failure (never raise to caller for “soft” ensure)
    - `async def delete_installation_caches(self) -> None` — list + delete every cache whose `displayName` starts with `CACHE_DISPLAY_PREFIX`
    - `async def create_cache(self) -> str` — create; raise on hard failure
    - `async def extend_ttl(self, name: str, ttl_seconds: int = 604800) -> None`
    - `get_cached_name(self) -> str | None` / `clear_local(self) -> None` — process-local registry
  - Module-level helpers used by HttpParser may wrap a shared instance keyed by `(api_key, model)` if useful; keep it simple (instance per HttpParser is fine).
- Consumes: `prompt_version`, `static_cache_text`, httpx
- TTL constant: `DEFAULT_CACHE_TTL_SECONDS = 604800`

- [ ] **Step 1: Write failing tests** (MockTransport)

```python
from app.parsing.google_cache import (
    CACHE_DISPLAY_PREFIX,
    GooglePromptCache,
    cache_display_name,
)
from app.parsing.prompt import prompt_version


@pytest.mark.anyio
async def test_ensure_cache_creates_with_static_only():
    calls: list[tuple[str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode()) if request.content else None
        calls.append((request.method, str(request.url), body))
        if request.method == "GET" and request.url.path.endswith("/cachedContents"):
            return httpx.Response(200, json={"cachedContents": []})
        if request.method == "POST" and request.url.path.endswith("/cachedContents"):
            assert body["systemInstruction"]["parts"][0]["text"] == static_cache_text()
            assert body["displayName"] == cache_display_name(prompt_version())
            assert body["model"] == f"models/test-model-from-env"
            for marker in FAMILY_MARKERS:
                assert marker not in json.dumps(body, ensure_ascii=False)
            return httpx.Response(
                200,
                json={
                    "name": "cachedContents/abc123",
                    "displayName": body["displayName"],
                    "expireTime": "2099-01-01T00:00:00Z",
                },
            )
        return httpx.Response(500, json={"error": "unexpected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    name = await cache.ensure_cache()
    assert name == "cachedContents/abc123"
    assert cache.get_cached_name() == name
    await client.aclose()


@pytest.mark.anyio
async def test_prompt_version_change_deletes_old_cache():
    deleted: list[str] = []
    state = {"version_suffix": "old"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/cachedContents"):
            return httpx.Response(
                200,
                json={
                    "cachedContents": [
                        {
                            "name": "cachedContents/old1",
                            "displayName": f"{CACHE_DISPLAY_PREFIX}deadbeefdeadbeef",
                        }
                    ]
                },
            )
        if request.method == "DELETE":
            deleted.append(str(request.url.path))
            return httpx.Response(200, json={})
        if request.method == "POST" and request.url.path.endswith("/cachedContents"):
            return httpx.Response(
                200,
                json={
                    "name": "cachedContents/new1",
                    "displayName": cache_display_name(prompt_version()),
                },
            )
        return httpx.Response(500, json={"error": "unexpected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    # Force reconcile path: local empty, list finds old display name ≠ current
    name = await cache.ensure_cache()
    assert name == "cachedContents/new1"
    assert any("cachedContents/old1" in d for d in deleted)
    await client.aclose()
```

Refine the second test so `ensure_cache` deletes any listed cache with `CACHE_DISPLAY_PREFIX` whose displayName is not `cache_display_name(prompt_version())`, then creates if current name not already present. If list already contains the current displayName, reuse it and do not create a second.

- [ ] **Step 2: Run — expect FAIL** (module missing)

- [ ] **Step 3: Implement `google_cache.py`**

Sketch:

```python
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.parsing.prompt import prompt_version, static_cache_text

logger = logging.getLogger(__name__)

CACHE_DISPLAY_PREFIX = "chontak-parser-"
DEFAULT_CACHE_TTL_SECONDS = 604800
_BASE = "https://generativelanguage.googleapis.com/v1beta"


def cache_display_name(version: str) -> str:
    return f"{CACHE_DISPLAY_PREFIX}{version}"


class GooglePromptCache:
    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client
        self._local_name: str | None = None
        self._local_version: str | None = None

    def get_cached_name(self) -> str | None:
        if self._local_version != prompt_version():
            return None
        return self._local_name

    def clear_local(self) -> None:
        self._local_name = None
        self._local_version = None

    def _params(self) -> dict[str, str]:
        return {"key": self._api_key}

    async def ensure_cache(self) -> str | None:
        try:
            return await self._ensure_cache()
        except Exception:
            logger.exception("prompt cache ensure failed")
            return None

    async def _ensure_cache(self) -> str:
        version = prompt_version()
        wanted = cache_display_name(version)
        if self._local_name and self._local_version == version:
            return self._local_name

        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            listed = await self._list(client)
            current = None
            for item in listed:
                name = item.get("name")
                display = item.get("displayName") or ""
                if not isinstance(name, str):
                    continue
                if not display.startswith(CACHE_DISPLAY_PREFIX):
                    continue
                if display == wanted:
                    current = name
                else:
                    await self._delete(client, name)
            if current is None:
                current = await self._create(client, wanted)
            self._local_name = current
            self._local_version = version
            return current
        finally:
            if owns:
                await client.aclose()

    async def delete_installation_caches(self) -> None:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            for item in await self._list(client):
                name = item.get("name")
                display = item.get("displayName") or ""
                if isinstance(name, str) and display.startswith(CACHE_DISPLAY_PREFIX):
                    await self._delete(client, name)
            self.clear_local()
        finally:
            if owns:
                await client.aclose()

    async def create_cache(self) -> str:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            name = await self._create(client, cache_display_name(prompt_version()))
            self._local_name = name
            self._local_version = prompt_version()
            return name
        finally:
            if owns:
                await client.aclose()

    async def extend_ttl(self, name: str, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS) -> None:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.patch(
                f"{_BASE}/{name}",
                params=self._params(),
                headers={"Content-Type": "application/json"},
                json={"ttl": f"{ttl_seconds}s"},
            )
            if response.status_code >= 400:
                logger.warning("cache TTL extend failed: %s", response.status_code)
        finally:
            if owns:
                await client.aclose()

    async def _list(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        response = await client.get(f"{_BASE}/cachedContents", params=self._params())
        response.raise_for_status()
        data = response.json()
        items = data.get("cachedContents") or []
        return items if isinstance(items, list) else []

    async def _delete(self, client: httpx.AsyncClient, name: str) -> None:
        response = await client.delete(f"{_BASE}/{name}", params=self._params())
        if response.status_code >= 400 and response.status_code != 404:
            logger.warning("cache delete failed for %s: %s", name, response.status_code)

    async def _create(self, client: httpx.AsyncClient, display_name: str) -> str:
        response = await client.post(
            f"{_BASE}/cachedContents",
            params=self._params(),
            headers={"Content-Type": "application/json"},
            json={
                "model": f"models/{self._model}",
                "displayName": display_name,
                "systemInstruction": {
                    "parts": [{"text": static_cache_text()}]
                },
                "ttl": f"{DEFAULT_CACHE_TTL_SECONDS}s",
            },
        )
        response.raise_for_status()
        data = response.json()
        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError("cache create returned no name")
        return name
```

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/google_cache.py backend/tests/test_phase13_prompt_caching.py
git commit -m "$(cat <<'EOF'
feat(parsing): add Gemini explicit prompt-cache manager

EOF
)"
```

---

### Task 4: Wire cache into Google parse — hit, miss fallback, background rebuild

**Files:**
- Modify: `backend/app/parsing/http_adapter.py`
- Modify: `backend/tests/test_phase13_prompt_caching.py`

**Interfaces:**
- Produces: For `provider=="google"`, `HttpParser.parse`:
  1. If `GooglePromptCache.get_cached_name()` is set, POST generateContent with `cachedContent` and **without** resending `systemInstruction`.
  2. If that returns 404 / cache-missing style error, clear local name and fall through to full-prompt (step 3).
  3. Full-prompt generateContent with `systemInstruction=static_cache_text()` (Task 2 path).
  4. After a successful full-prompt response when no usable cache was used, schedule `asyncio.create_task(self._rebuild_cache())` which calls `ensure_cache()` (must not await inside the user request beyond fire-and-forget).
  5. After a successful cached response, fire-and-forget `extend_ttl(name)`.
- Inject optional `prompt_cache: GooglePromptCache | None` into `HttpParser.__init__` (default: construct one when provider is google).
- Track rebuild scheduling via an optional hook `on_rebuild: callable | None` for tests, or expose `rebuild_scheduled` flag / capture tasks carefully.

**Missing-cache → transaction test (phase-spec §5.3):**

```python
@pytest.mark.anyio
async def test_missing_cache_still_parses_and_schedules_rebuild():
    """Cache miss must not fail parse; rebuild scheduled in background."""
    rebuild_calls: list[str] = []
    phase = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        # list empty → no cache
        if request.method == "GET" and path.endswith("/cachedContents"):
            return httpx.Response(200, json={"cachedContents": []})
        # create cache (background)
        if request.method == "POST" and path.endswith("/cachedContents"):
            rebuild_calls.append("create")
            return httpx.Response(
                200,
                json={
                    "name": "cachedContents/rebuilt",
                    "displayName": cache_display_name(prompt_version()),
                },
            )
        # generateContent full prompt
        if "generateContent" in path:
            body = json.loads(request.content.decode())
            assert "cachedContent" not in body  # miss path
            assert body["systemInstruction"]["parts"][0]["text"] == static_cache_text()
            ops = (
                '{"operations":[{"type":"expense","amount":25000,"currency":"UZS",'
                '"wallet_hint":null,"category":"Такси","comment":null,'
                '"from_wallet_hint":null,"to_wallet_hint":null,"rate":null}]}'
            )
            return httpx.Response(200, json=_google_ok_body(ops))
        return httpx.Response(500, json={"error": "unexpected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    cache.clear_local()
    parser = HttpParser(
        "google",
        "test-key",
        "test-model-from-env",
        client=client,
        prompt_cache=cache,
    )
    response = await parser.parse(_sample_request())
    assert response.operations[0].amount == 25000
    # allow background task to run
    import asyncio
    await asyncio.sleep(0.05)
    assert "create" in rebuild_calls
    await client.aclose()


@pytest.mark.anyio
async def test_cached_parse_references_cache_not_static():
    def handler(request: httpx.Request) -> httpx.Response:
        if "generateContent" in request.url.path:
            body = json.loads(request.content.decode())
            assert body.get("cachedContent") == "cachedContents/abc"
            assert "systemInstruction" not in body
            ops = (
                '{"operations":[{"type":"expense","amount":1000,"currency":"UZS",'
                '"wallet_hint":null,"category":null,"comment":null,'
                '"from_wallet_hint":null,"to_wallet_hint":null,"rate":null}]}'
            )
            return httpx.Response(200, json=_google_ok_body(ops))
        if request.method == "PATCH":
            return httpx.Response(200, json={"name": "cachedContents/abc"})
        return httpx.Response(500, json={"error": "unexpected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    cache._local_name = "cachedContents/abc"
    cache._local_version = prompt_version()
    parser = HttpParser(
        "google", "test-key", "test-model-from-env", client=client, prompt_cache=cache
    )
    response = await parser.parse(_sample_request())
    assert response.operations[0].amount == 1000
    await client.aclose()
```

**Transaction creation with stub provider (phase-spec §5.3 literal):**

Add a test that uses a stub MessageParser returning one expense op, then `create_quick_entry_expense` — proving the product path does not require a cache. Skip if Postgres is down (same pattern as `test_quick_entry_create.py`). This documents that cache is not a dependency of record creation:

```python
@pytest.mark.anyio
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
async def test_stub_parser_path_still_creates_transaction():
    # reuse helpers from test_quick_entry_create (import or duplicate minimal seed)
    ...
    # StubParser parse → create_quick_entry_expense → assert txn.amount == 25000
```

Do not invent a fake ≥90% number anywhere in tests.

- [ ] **Step 2–4:** Implement wiring in `http_adapter.py`; tests pass.

Implementation notes for `_post` / `parse`:
- Prefer splitting `_post_google(client, request, *, cache_name: str | None)`.
- On cached 404/400 mentioning cache, clear local and retry once full-prompt.
- Background rebuild: 

```python
async def _rebuild_cache(self) -> None:
    if self._prompt_cache is None:
        return
    await self._prompt_cache.ensure_cache()
```

Use `asyncio.get_running_loop().create_task(...)` and store strong refs on `self._bg_tasks: set` with `task.add_done_callback(self._bg_tasks.discard)` to avoid GC.

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/http_adapter.py backend/tests/test_phase13_prompt_caching.py
git commit -m "$(cat <<'EOF'
feat(parsing): use Gemini cache with full-prompt fallback

EOF
)"
```

---

### Task 5: Measurement script + suite gate

**Files:**
- Create: `backend/scripts/measure_prompt_cache.py`
- Modify: none required beyond ensuring exports clean

**Purpose:** When `PARSER_PROVIDER=google`, `PARSER_API_KEY`, and `PARSER_MODEL` are set, run one cached parse (ensure cache → generateContent with cache) and print:

```
promptTokenCount=...
cachedContentTokenCount=...
cached_ratio=...
```

Exit 0 if `cached_ratio >= 0.90`, else exit 1.  
If any of the three env vars is missing, print `blocked: PARSER_* credentials not available` and exit 2. **Never invent a ratio.**

```python
"""Live Gemini prompt-cache measurement. Exit 2 if credentials missing."""

from __future__ import annotations

import asyncio
import os
import sys

# script adds backend to path like other scripts in this repo
...
```

Follow the style of `backend/scripts/send_release_announcement.py` for path/bootstrap.

- [ ] **Step 1: Write the script** (no live call in CI).

- [ ] **Step 2: Run script once in this environment**

Run: `cd backend && ./venv/bin/python scripts/measure_prompt_cache.py`  
Record the exit code and stdout for the phase report. Expected here: exit 2 blocked (credentials likely absent).

- [ ] **Step 3: Full suites**

Before any claim of done:

```bash
cd backend && ./venv/bin/pytest -q
cd frontend && npx vitest run --reporter=dot
```

Backend count must be ≥ 382. Frontend must remain `37 files, 205 tests`.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/measure_prompt_cache.py
git commit -m "$(cat <<'EOF'
chore(parsing): add live Gemini cache measurement script

EOF
)"
```

---

## Evidence for ≥90% cached tokens

1. Prefer `scripts/measure_prompt_cache.py` against real Gemini.
2. If `PARSER_API_KEY` / provider / model are unset in this environment → mark acceptance items 1–4 that need the live provider as **blocked** in the final report under DEFERRED; do **not** approximate.
3. Automated coverage that always runs: Task 1 assembly tests + Task 4 miss-fallback + stub transaction test.

## Self-review checklist

1. **Spec coverage:** §20 static fixed / no family data / one cache / permanent+extend / delete on version / miss fallback / ≥90% evidence path / Google provider — each has a task.
2. **No placeholders:** ballast sizing concrete; REST paths concrete; test code concrete.
3. **Types:** `GooglePromptCache.ensure_cache() -> str | None`; `HttpParser` gains optional `prompt_cache`.

## Execution

Plan is executed in this same Cursor session via Subagent-Driven Development with worker model `composer-2.5` only. Orchestrator (Cursor Grok 4.5) writes the plan, dispatches workers, runs final suite gate, and delivers the section-11 report.
