# Phase 0 — Foundation & Application Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Replace every-request Telegram `initData` auth with an application pass so the mini app stays signed in beyond one hour (PRD §6).

**Architecture:** At first entry the client sends `Authorization: tma <initData>` to `POST /api/v1/auth/pass`. The server validates the Telegram HMAC and `auth_date` (max 24h at issue only), then returns a 30-day HS256 JWT. All business routes accept only `Authorization: Bearer <jwt>`. Revocation is a `jti` row in PostgreSQL. The frontend stores the JWT in `localStorage` key `chontak_app_pass` and bootstraps with one silent retry before the PRD §6 failure screen.

**Tech Stack:** FastAPI, PyJWT, SQLAlchemy 2 async, Alembic, pytest, React, Vite, TypeScript, Zustand, `@tma.js/sdk-react`, existing TelegramUI.

## Global Constraints

- Spec: `docs/tasks/phase-00-foundation.md` — follow it exactly.
- User-facing failure copy: PRD §6 Russian text character for character; button `Попробовать снова`.
- Banned user-facing words: ошибка, сессия, сервер, токен, запрос.
- Pass lifetime: 30 days (`expires_in` = 2592000). Algorithm: HS256. Secret: `APP_PASS_SECRET`.
- Business routes: Bearer only — no every-request `tma`.
- Do not rebuild the monorepo skeleton from zero; extend the existing MVP 1 codebase.
- Do not implement quick entry, new Home layout, or any later phase.
- Report pytest before/after; list every mock/stub/disabled item (or say empty).

**Scope estimate:** 8 tasks · ~6–10 hours of worker time · one customer co-run of the named pytest.

## File map

| File | Responsibility |
|------|----------------|
| `backend/requirements.txt` | Add `PyJWT` |
| `backend/app/config.py` | Load `APP_PASS_SECRET` |
| `.env.example` | Document `APP_PASS_SECRET` |
| `backend/app/auth/pass_tokens.py` | Issue / decode / verify JWT |
| `backend/app/auth/deps.py` | Bearer dependency replacing every-request `tma` on business routes |
| `backend/app/auth/telegram.py` | Keep HMAC helpers; issue-time max age constant `PASS_ISSUE_MAX_AGE_SECONDS = 86400`; stop exporting business-route `TelegramUserDep` usage |
| `backend/app/models/revoked_app_pass.py` | ORM for revoke table |
| `backend/alembic/versions/h8c9d0e1f2a3_revoked_app_passes.py` | Migration |
| `backend/app/api/v1/auth.py` | `POST /api/v1/auth/pass` |
| `backend/app/api/v1/me.py` | Use Bearer dependency |
| `backend/app/auth/user_deps.py` | Resolve `User` from pass claims |
| `backend/app/main.py` | Include auth router |
| `backend/scripts/revoke_app_pass.py` | Insert `jti` from a JWT for hand acceptance |
| `backend/tests/test_application_pass.py` | Phase 0 tests including the one named test |
| `frontend/src/api/authHeader.ts` | Store/read Bearer token |
| `frontend/src/api/authPass.ts` | `POST /api/v1/auth/pass` |
| `frontend/src/api/me.ts` | Call `/me` with Bearer (no `tma`) |
| `frontend/src/hooks/useAuthBootstrap.ts` | Pass-first bootstrap + one silent retry |
| `frontend/src/components/AuthErrorScreen.tsx` | §6 copy for pass failure; keep other error types |
| `frontend/src/i18n/locales/ru.json` | §6 strings (and button label) |
| `frontend/src/store/authStore.ts` | Add error type for pass failure if needed |

---

### Task 1: Config + PyJWT dependency

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Test: (install check only in this task)

**Interfaces:**
- Consumes: existing `load_dotenv` pattern in `config.py`
- Produces: `APP_PASS_SECRET: str` exported from `app.config`

- [ ] **Step 1: Add PyJWT to requirements**

Append to `backend/requirements.txt`:

```
PyJWT==2.10.1
```

(If that exact patch version is unavailable at install time, pin the newest 2.x and record the chosen version in the worker report — do not jump to a different library.)

- [ ] **Step 2: Require APP_PASS_SECRET in config**

In `backend/app/config.py`, after `BOT_TOKEN`:

```python
APP_PASS_SECRET = os.environ["APP_PASS_SECRET"]
if not APP_PASS_SECRET:
    raise RuntimeError("APP_PASS_SECRET environment variable is empty")
```

- [ ] **Step 3: Update `.env.example`**

Add:

```
APP_PASS_SECRET=replace-with-long-random-string
```

- [ ] **Step 4: Install and confirm import**

Run:

```bash
cd backend && ./venv/bin/pip install 'PyJWT==2.10.1' && ./venv/bin/python -c "import jwt; print(jwt.__version__)"
```

Expected: prints a 2.x version without error.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/config.py .env.example
git commit -m "$(cat <<'EOF'
chore: add PyJWT and APP_PASS_SECRET for application pass

EOF
)"
```

---

### Task 2: Pass token helpers (TDD)

**Files:**
- Create: `backend/app/auth/pass_tokens.py`
- Create: `backend/tests/test_application_pass.py` (start; more cases in later tasks)
- Modify: `backend/app/auth/telegram.py` (add issue-age constant only)

**Interfaces:**
- Consumes: `APP_PASS_SECRET` from config (pass secret into functions for testability)
- Produces:
  - `PASS_LIFETIME_SECONDS = 2_592_000`
  - `PASS_ISSUE_MAX_AGE_SECONDS = 86_400` (also mirrored / used from telegram module)
  - `issue_app_pass(*, telegram_id: int, user_id: uuid.UUID | None, secret: str, now: int | None = None) -> tuple[str, str, int]` → `(token, jti, expires_in)`
  - `decode_app_pass(token: str, secret: str, *, now: int | None = None) -> dict` → raises `AppPassError` on failure
  - `class AppPassError(Exception): ...`

- [ ] **Step 1: Write failing tests for issue/decode**

Create `backend/tests/test_application_pass.py`:

```python
import time
import uuid

import pytest

from app.auth.pass_tokens import (
    PASS_LIFETIME_SECONDS,
    AppPassError,
    decode_app_pass,
    issue_app_pass,
)

SECRET = "test-app-pass-secret-not-for-production"


def test_issue_and_decode_round_trip() -> None:
    uid = uuid.uuid4()
    token, jti, expires_in = issue_app_pass(
        telegram_id=279058397,
        user_id=uid,
        secret=SECRET,
        now=1_700_000_000,
    )
    assert expires_in == PASS_LIFETIME_SECONDS
    assert jti
    claims = decode_app_pass(token, SECRET, now=1_700_000_000)
    assert claims["sub"] == "279058397"
    assert claims["uid"] == str(uid)
    assert claims["jti"] == jti
    assert claims["exp"] == 1_700_000_000 + PASS_LIFETIME_SECONDS


def test_expired_pass_rejected() -> None:
    token, _, _ = issue_app_pass(
        telegram_id=1,
        user_id=None,
        secret=SECRET,
        now=1_700_000_000,
    )
    with pytest.raises(AppPassError):
        decode_app_pass(token, SECRET, now=1_700_000_000 + PASS_LIFETIME_SECONDS + 1)


def test_tampered_pass_rejected() -> None:
    token, _, _ = issue_app_pass(
        telegram_id=1,
        user_id=None,
        secret=SECRET,
        now=1_700_000_000,
    )
    bad = token[:-4] + ("0000" if not token.endswith("0000") else "1111")
    with pytest.raises(AppPassError):
        decode_app_pass(bad, SECRET, now=1_700_000_000)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && ./venv/bin/pytest tests/test_application_pass.py -v
```

Expected: FAIL (module not found / import error).

- [ ] **Step 3: Implement `pass_tokens.py`**

```python
import uuid
from typing import Any

import jwt

PASS_LIFETIME_SECONDS = 2_592_000


class AppPassError(Exception):
    """Raised when an application pass cannot be issued or verified."""


def issue_app_pass(
    *,
    telegram_id: int,
    user_id: uuid.UUID | None,
    secret: str,
    now: int | None = None,
) -> tuple[str, str, int]:
    issued_at = int(time.time()) if now is None else now
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": str(telegram_id),
        "iat": issued_at,
        "exp": issued_at + PASS_LIFETIME_SECONDS,
        "jti": jti,
    }
    if user_id is not None:
        payload["uid"] = str(user_id)
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token, jti, PASS_LIFETIME_SECONDS


def decode_app_pass(
    token: str,
    secret: str,
    *,
    now: int | None = None,
) -> dict[str, Any]:
    try:
        options = {"require": ["sub", "iat", "exp", "jti"]}
        kwargs: dict[str, Any] = {
            "algorithms": ["HS256"],
            "options": options,
        }
        if now is not None:
            kwargs["leeway"] = 0
            # PyJWT reads time via jwt.api_jwt.datetime; use payload check:
        claims = jwt.decode(token, secret, **kwargs)
    except jwt.PyJWTError as exc:
        raise AppPassError from exc

    if now is not None and int(claims["exp"]) < now:
        raise AppPassError
    return claims
```

Add `import time` at top. For deterministic `now` in decode when PyJWT also checks `exp` against wall clock, prefer:

```python
def decode_app_pass(token: str, secret: str, *, now: int | None = None) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp", "jti"]},
            leeway=0,
        )
    except jwt.PyJWTError as exc:
        raise AppPassError from exc
    if now is not None and int(claims["exp"]) < now:
        raise AppPassError
    return claims
```

Note: when `now` is in the past relative to real time, `jwt.decode` may already reject via wall-clock `exp`. For unit tests of expiry, either mock time or craft claims with `jwt.encode` directly in the expired test. Prefer crafting:

```python
def test_expired_pass_rejected() -> None:
    payload = {
        "sub": "1",
        "iat": 1_700_000_000,
        "exp": 1_700_000_001,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(AppPassError):
        decode_app_pass(token, SECRET)  # wall clock is far beyond exp
```

Adjust the test file accordingly so it is deterministic.

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && ./venv/bin/pytest tests/test_application_pass.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/pass_tokens.py backend/tests/test_application_pass.py
git commit -m "$(cat <<'EOF'
feat: add application pass JWT issue and decode helpers

EOF
)"
```

---

### Task 3: Revoke table + migration

**Files:**
- Create: `backend/app/models/revoked_app_pass.py`
- Modify: `backend/app/models/__init__.py` (export model if the package lists models)
- Create: `backend/alembic/versions/h8c9d0e1f2a3_revoked_app_passes.py`
- Modify: `backend/tests/test_application_pass.py` (optional model import smoke — skip if no DB in unit tests)

**Interfaces:**
- Produces: table `revoked_app_passes(jti TEXT PRIMARY KEY, revoked_at TIMESTAMPTZ NOT NULL DEFAULT now())`
- Produces: `class RevokedAppPass(Base)` with `jti`, `revoked_at`

- [ ] **Step 1: Write the ORM model**

```python
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RevokedAppPass(Base):
    __tablename__ = "revoked_app_passes"

    jti: Mapped[str] = mapped_column(String, primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
```

- [ ] **Step 2: Write Alembic migration**

`down_revision = "g7b8c9d0e1f2"` (current head). Upgrade creates the table; downgrade drops it.

```python
def upgrade() -> None:
    op.create_table(
        "revoked_app_passes",
        sa.Column("jti", sa.String(), primary_key=True),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("revoked_app_passes")
```

- [ ] **Step 3: Run migration**

```bash
cd backend && ./venv/bin/alembic upgrade head
```

Expected: success, no error.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/revoked_app_pass.py backend/app/models/__init__.py backend/alembic/versions/h8c9d0e1f2a3_revoked_app_passes.py
git commit -m "$(cat <<'EOF'
feat: add revoked_app_passes table for pass revocation

EOF
)"
```

---

### Task 4: Issue endpoint + Bearer dependency

**Files:**
- Create: `backend/app/api/v1/auth.py`
- Create: `backend/app/auth/deps.py`
- Modify: `backend/app/auth/telegram.py` — add `PASS_ISSUE_MAX_AGE_SECONDS = 86400`; keep `validate_init_data`; keep `get_telegram_user` for the issue route only (or inline validation in auth router)
- Modify: `backend/app/api/v1/me.py`
- Modify: `backend/app/auth/user_deps.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_application_pass.py` — add the **named** test and HTTP cases
- Modify: `backend/tests/test_telegram_auth.py` and any test that sends `tma` to business routes — update to Bearer (do in Task 5 if too large; at minimum `/me` tests here)

**Interfaces:**
- Consumes: `validate_init_data`, `issue_app_pass`, `decode_app_pass`, `RevokedAppPass`
- Produces:
  - `POST /api/v1/auth/pass` → `{access_token, token_type: "bearer", expires_in}`
  - `async def get_pass_claims(...) -> dict` FastAPI dependency
  - `TelegramUser`-like access via `int(claims["sub"])` for `/me`

- [ ] **Step 1: Write the named failing test first**

Append to `backend/tests/test_application_pass.py`:

```python
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432")
async def test_application_pass_allows_api_when_init_data_is_stale() -> None:
    """Phase 0 gate: Bearer pass works; raw tma is rejected on /me."""
    # Arrange: seed user, issue pass with fresh initData, then call /me with Bearer.
    # Assert: 200 with Bearer.
    # Assert: same /me with Authorization tma <initData> returns 401.
    # Assert: after inserting claims['jti'] into revoked_app_passes, Bearer returns 401.
    ...
```

Implement the body using the same DB rollback / ASGI patterns as `tests/test_telegram_auth.py` (`AsyncClient`, `sign_init_data` / `build_fresh_init_data`, patch `BOT_TOKEN` and `APP_PASS_SECRET` as needed). Reuse helpers; do not invent a second signing algorithm.

Also add:

- `test_issue_pass_rejects_auth_date_older_than_24h`
- `test_issue_pass_accepts_fresh_init_data`

- [ ] **Step 2: Run named test — expect FAIL**

```bash
cd backend && ./venv/bin/pytest tests/test_application_pass.py::test_application_pass_allows_api_when_init_data_is_stale -v
```

Expected: FAIL (endpoint or Bearer behaviour missing).

- [ ] **Step 3: Implement issue route**

`backend/app/api/v1/auth.py`:

```python
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from app.auth.pass_tokens import issue_app_pass
from app.auth.telegram import (
    PASS_ISSUE_MAX_AGE_SECONDS,
    InitDataValidationError,
    validate_init_data,
)
from app.config import APP_PASS_SECRET, BOT_TOKEN
from app.db import async_session_factory
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth")


@router.post("/pass")
async def create_pass(authorization: str | None = Header(default=None)) -> dict:
    if authorization is None or not authorization.startswith("tma "):
        raise HTTPException(status_code=401)
    init_data = authorization.removeprefix("tma ")
    try:
        tg_user = validate_init_data(
            init_data,
            BOT_TOKEN,
            max_age_seconds=PASS_ISSUE_MAX_AGE_SECONDS,
        )
    except InitDataValidationError:
        raise HTTPException(status_code=401) from None

    async with async_session_factory() as session:
        db_user = await session.scalar(
            select(User).where(User.telegram_id == tg_user.id)
        )
        user_id = None if db_user is None else db_user.id

    token, _jti, expires_in = issue_app_pass(
        telegram_id=tg_user.id,
        user_id=user_id,
        secret=APP_PASS_SECRET,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }
```

In `telegram.py` set:

```python
PASS_ISSUE_MAX_AGE_SECONDS = 86400
```

Leave `AUTH_MAX_AGE_SECONDS` unused by business routes (may delete later in this phase if nothing imports it).

- [ ] **Step 4: Implement Bearer dependency**

`backend/app/auth/deps.py`:

```python
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.pass_tokens import AppPassError, decode_app_pass
from app.config import APP_PASS_SECRET
from app.db import get_session
from app.models.revoked_app_pass import RevokedAppPass


async def get_app_pass_claims(
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,  # fix: use proper Depends
) -> dict[str, Any]:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401)
    try:
        claims = decode_app_pass(token, APP_PASS_SECRET)
    except AppPassError:
        raise HTTPException(status_code=401) from None

    revoked = await session.scalar(
        select(RevokedAppPass.jti).where(RevokedAppPass.jti == claims["jti"])
    )
    if revoked is not None:
        raise HTTPException(status_code=401)
    return claims


AppPassClaimsDep = Annotated[dict[str, Any], Depends(get_app_pass_claims)]
```

Fix the signature to match project style (`session: Annotated[AsyncSession, Depends(get_session)]` only — no `= None`).

- [ ] **Step 5: Switch `/me` and `user_deps` to Bearer**

`me.py`: resolve `telegram_id = int(claims["sub"])` instead of `TelegramUserDep`.

`user_deps.get_current_user`: depend on `AppPassClaimsDep` and look up `User` by `int(claims["sub"])` (same query as today).

Include `auth.router` in `main.py`.

- [ ] **Step 6: Run the named test — expect PASS**

```bash
cd backend && ./venv/bin/pytest tests/test_application_pass.py::test_application_pass_allows_api_when_init_data_is_stale -v
```

Expected: PASS (Postgres must be up).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/auth.py backend/app/auth/deps.py backend/app/auth/telegram.py backend/app/api/v1/me.py backend/app/auth/user_deps.py backend/app/main.py backend/tests/test_application_pass.py
git commit -m "$(cat <<'EOF'
feat: issue application pass and authenticate /me with Bearer JWT

EOF
)"
```

---

### Task 5: Update remaining backend callers and old auth tests

**Files:**
- Modify: every backend test that hits protected routes with `tma` — issue a pass (or call `issue_app_pass` directly) and send `Bearer`
- Modify: any leftover production code still using `TelegramUserDep` on business routes

**Interfaces:**
- Consumes: `POST /api/v1/auth/pass` or `issue_app_pass`
- Produces: green backend suite for auth-related tests

- [ ] **Step 1: Run full backend tests to list failures**

```bash
cd backend && ./venv/bin/pytest -q
```

Record the failing list in the worker report (before fix).

- [ ] **Step 2: Add a shared test helper**

e.g. in `tests/conftest.py` or a small `tests/auth_helpers.py`:

```python
def bearer_header_for_telegram_id(telegram_id: int, user_id=None) -> dict[str, str]:
    token, _, _ = issue_app_pass(
        telegram_id=telegram_id,
        user_id=user_id,
        secret=APP_PASS_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}
```

Patch tests to use it. For tests that previously built `tma` headers, keep `build_fresh_init_data` only for `POST /api/v1/auth/pass` tests.

- [ ] **Step 3: Re-run suite**

```bash
cd backend && ./venv/bin/pytest -q
```

Expected: PASS (or only pre-existing failures unrelated to auth — if any, list them; do not ignore new auth failures).

- [ ] **Step 4: Commit**

```bash
git add backend/tests
git commit -m "$(cat <<'EOF'
test: authenticate API tests with application pass Bearer tokens

EOF
)"
```

---

### Task 6: Frontend pass storage + API clients

**Files:**
- Modify: `frontend/src/api/authHeader.ts`
- Create: `frontend/src/api/authPass.ts`
- Modify: `frontend/src/api/me.ts`

**Interfaces:**
- Consumes: `POST /api/v1/auth/pass`, `GET /api/v1/me`
- Produces:
  - `PASS_STORAGE_KEY = 'chontak_app_pass'`
  - `getAuthHeader(): string` → `Bearer ${token}`
  - `setAppPass(token: string): void` / `clearAppPass(): void` / `readAppPass(): string | null`
  - `exchangeInitDataForPass(initData: string): Promise<string>`
  - `fetchMe(): Promise<AuthUser>` using Bearer only

- [ ] **Step 1: Rewrite `authHeader.ts`**

```typescript
export const PASS_STORAGE_KEY = 'chontak_app_pass'

export function readAppPass(): string | null {
  return localStorage.getItem(PASS_STORAGE_KEY)
}

export function setAppPass(token: string): void {
  localStorage.setItem(PASS_STORAGE_KEY, token)
}

export function clearAppPass(): void {
  localStorage.removeItem(PASS_STORAGE_KEY)
}

export function getAuthHeader(): string {
  const token = readAppPass()
  if (!token) {
    throw new Error('application pass is not available — authenticate first')
  }
  return `Bearer ${token}`
}
```

Remove `setInitData` / cached initData.

- [ ] **Step 2: Add `authPass.ts`**

```typescript
import { setAppPass } from './authHeader'

type PassResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

export async function exchangeInitDataForPass(initData: string): Promise<string> {
  const response = await fetch('/api/v1/auth/pass', {
    method: 'POST',
    headers: { Authorization: `tma ${initData}` },
  })
  if (!response.ok) {
    throw new Error('pass_issue_failed')
  }
  const data = (await response.json()) as PassResponse
  setAppPass(data.access_token)
  return data.access_token
}
```

- [ ] **Step 3: Change `fetchMe` to Bearer-only**

```typescript
export async function fetchMe(): Promise<AuthUser> {
  let response: Response
  try {
    response = await fetch('/api/v1/me', {
      headers: { Authorization: getAuthHeader() },
    })
  } catch {
    throw new MeRequestError('network')
  }
  // same status mapping as today
}
```

Update all call sites that passed `initData` into `fetchMe`.

- [ ] **Step 4: Typecheck / lint**

```bash
cd frontend && npm run build
```

Expected: build succeeds (or only pre-existing unrelated warnings — list them).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/authHeader.ts frontend/src/api/authPass.ts frontend/src/api/me.ts
git commit -m "$(cat <<'EOF'
feat: store application pass and call API with Bearer header

EOF
)"
```

---

### Task 7: Bootstrap + §6 failure screen

**Files:**
- Modify: `frontend/src/hooks/useAuthBootstrap.ts`
- Modify: `frontend/src/store/authStore.ts`
- Modify: `frontend/src/components/AuthErrorScreen.tsx`
- Modify: `frontend/src/i18n/locales/ru.json`
- Modify: `frontend/src/i18n/locales/uz.json` (keep key parity; Uzbek wording out of scope — copy Russian temporarily or leave placeholder keys identical in structure only; do not invent final Uzbek)

**Interfaces:**
- Consumes: `readAppPass`, `clearAppPass`, `exchangeInitDataForPass`, `fetchMe`, `useRawInitData`
- Produces: bootstrap order from Phase 0 spec decision #11; error type `pass_failed` showing §6 copy

- [ ] **Step 1: Extend auth error type**

Add `'pass_failed'` to `AuthErrorType`. Map 401 after exhausted retry to `pass_failed` (not the old `unauthorized` string that contains the banned word «ошибка»).

- [ ] **Step 2: Implement bootstrap**

Pseudocode:

```typescript
async function authenticate() {
  setLoading()
  const tryWithStoredPass = async () => {
    if (!readAppPass()) return false
    try {
      const user = await fetchMe()
      await i18n.changeLanguage(user.language)
      setReady(user)
      return true
    } catch {
      clearAppPass()
      return false
    }
  }

  const tryExchange = async () => {
    if (!rawInitData) return false
    try {
      await exchangeInitDataForPass(rawInitData)
      const user = await fetchMe()
      await i18n.changeLanguage(user.language)
      setReady(user)
      return true
    } catch (error) {
      clearAppPass()
      if (error instanceof MeRequestError && error.errorType === 'not_onboarded') {
        setError('not_onboarded')
        return true // handled
      }
      if (error instanceof MeRequestError && error.errorType === 'removed_from_family') {
        setError('removed_from_family')
        return true
      }
      return false
    }
  }

  if (await tryWithStoredPass()) return
  if (await tryExchange()) return
  // one silent retry
  if (await tryWithStoredPass()) return
  if (await tryExchange()) return
  setError('pass_failed')
}
```

Align exactly with spec decision #11 (one silent retry total). Prefer a single `attempt()` function called at most twice.

- [ ] **Step 3: Failure screen copy**

In `ru.json`:

```json
"auth": {
  "passFailed": "Не удалось открыть приложение. Закройте его и откройте снова через меню бота.",
  "retry": "Попробовать снова",
  "notOnboarded": "...",
  "removedFromFamily": "...",
  "networkError": "..."
}
```

Remove or stop using `auth.unauthorized` («Ошибка аутентификации») for this path.

`AuthErrorScreen`: for `pass_failed` (and keep network retry), show primary `Button` with `t('auth.retry')` → `Попробовать снова`. For `pass_failed`, always show the button (PRD §6).

Do not put «ошибка» / «сессия» / «сервер» / «токен» / «запрос» into the new strings. Existing `networkError` may still contain banned wording from MVP 1 — **do not silently rewrite it in this phase**; if the worker must touch that key, stop and ask.

- [ ] **Step 4: Manual smoke (worker)**

With Vite + API + tunnel: open app, confirm `chontak_app_pass` appears in localStorage, `/api/v1/me` uses Bearer.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useAuthBootstrap.ts frontend/src/store/authStore.ts frontend/src/components/AuthErrorScreen.tsx frontend/src/i18n/locales/ru.json frontend/src/i18n/locales/uz.json
git commit -m "$(cat <<'EOF'
feat: bootstrap mini app with application pass and PRD failure screen

EOF
)"
```

---

### Task 8: Revoke helper + Phase 0 gate report

**Files:**
- Create: `backend/scripts/revoke_app_pass.py`
- Modify: none unless README one-liner helps local use (optional; skip if not required)

**Interfaces:**
- Consumes: JWT string, `DATABASE_URL`, inserts `RevokedAppPass`
- Produces: runnable revoke for customer hand step 3

- [ ] **Step 1: Write revoke script**

CLI: `python scripts/revoke_app_pass.py --token '<jwt>'`  
Decode without accepting expired tokens as success for revoke — still read `jti` via `jwt.decode(..., options={"verify_exp": False})`, insert row, print `revoked jti=...`.

- [ ] **Step 2: Run the Phase 0 named test (before claiming done)**

```bash
cd backend && ./venv/bin/pytest tests/test_application_pass.py::test_application_pass_allows_api_when_init_data_is_stale -v
```

Expected: PASS. Capture full output for the customer report.

- [ ] **Step 3: Run broader regression**

```bash
cd backend && ./venv/bin/pytest -q
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/revoke_app_pass.py
git commit -m "$(cat <<'EOF'
chore: add script to revoke an application pass by JWT jti

EOF
)"
```

- [ ] **Step 5: Worker report (mandatory)**

Include:

1. Pytest output **before** Phase 0 auth change (Task 5 step 1 baseline) and **after** final run.
2. Named test output.
3. List of disabled / stubbed / mocked / finish-later items. If none: write `Disabled/stubbed/mocked: none.`
4. Confirm commits landed.

---

## Self-review (orchestrator)

| Spec requirement | Task |
|------------------|------|
| JWT HS256, 30 days, `APP_PASS_SECRET` | 1–2 |
| `POST /api/v1/auth/pass` with `tma` | 4 |
| Bearer-only business routes | 4–5 |
| Revoke by `jti` | 3, 8 |
| `localStorage` `chontak_app_pass` | 6 |
| Bootstrap + one silent retry | 7 |
| §6 failure copy + `Попробовать снова` | 7 |
| Named test `test_application_pass_allows_api_when_init_data_is_stale` | 4, 8 |
| No quick entry / no new screens beyond failure | respected |

**Placeholder scan:** none intentional.  
**Type consistency:** `chontak_app_pass`, `PASS_LIFETIME_SECONDS = 2_592_000`, Bearer header spelling.

---

## Execution handoff (after customer green light only)

Plan complete and saved to `docs/superpowers/plans/2026-08-03-phase-0-foundation.md`.

When approved, two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh `composer-2.5` worker per task, review between tasks  
2. **Inline Execution** — execute tasks in-session with checkpoints  

Do **not** start until the customer says so.
