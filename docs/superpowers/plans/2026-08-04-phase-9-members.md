# Phase 9 — Members Full Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Full members lifecycle — invitation link (with refusals), join with own-budget conversion to personal wallets, removal/self-exit into a new owned budget, ownership transfer with confirmation, departed-member labels, default-wallet resolution, and the real Участники settings UI matching the design.

**Architecture:** Core lifecycle logic lives in `app/services/membership_lifecycle.py` (leave/remove split, join conversion, seeding, default-wallet rules). Bot onboarding gains invite refusal texts, §18.2 welcome, join-with-budget confirmation callbacks. Ownership transfer uses a small `ownership_transfers` table plus bot inline accept/refuse. History `created_by` appends ` (бывший участник)` when the author is no longer an active member of the family. Frontend replaces the Phase 6 members shell with invite sheet, member detail (transfer/remove), and member-only exit.

**Tech Stack:** Python/FastAPI/Aiogram/Alembic/pytest; React/Vite/TypeScript/TelegramUI/Zustand/react-i18next; vitest. No new packages.

## Global Constraints

- Spec: `docs/tasks/phase-09-members.md` + PRD §3, §4, §11, §13 (all + Acceptance), §15.4, §17.6, §18.2 only, §19.1 members line.
- Design: Участники screens one-to-one (`docs/design/Chontak MVP2.dc.html` members sub + `limitMember` sheet). Appearance wins for layout/control wording; PRD wins for behaviour.
- One permanent reusable invite link per family; reissue invalidates previous immediately; no expiry.
- Join-with-own-budget check order is fixed: (1) other-members refusal, (2) personal-wallet cap with substituted count, (3) confirmation. Over-cap never sees confirm.
- Brought wallets become **personal** in the new family; never merge into shared pool. Old budget closed. Goals on brought wallets are **deleted** (not converted to personal goals).
- Categories rematch by `translation_key` only; invented → category fields `NULL` (service «Без категории»). No name-string matching.
- Removal and voluntary exit are ONE mechanism; notification texts differ only in the first line. Owner has **no** exit control — absent, not disabled.
- Departed label exact: `{Имя} (бывший участник)` in History and analytics History tab `created_by`.
- Ownership transfer: active member only; recipient confirms; irreversible once accepted; all four §13.5 texts.
- Members app limit message (only case with no second sentence): `В семейном бюджете уже 4 участника — это предел.`
- §18.2 invited `/start` ships verbatim. Do **not** touch §18.1/18.3/18.4 (Phase 12).
- Personal-wallet visibility rules from Phase 7 must not weaken. Goals `· цель` mark and close-from-100% rules from Phase 8 — do not revisit.
- Do **not** edit `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/*`, `docs/tasks/*`.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-9-members` (already checked out).
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Commit after each task. TDD. Stop at end of Phase 9 — no Phase 10, change log, notification switches.
- User-facing Russian verbatim from PRD/design. Forbidden words: ошибка, сессия, сервер, токен, запрос.
- Conversation/report language with customer is Russian; this plan is English (docs/).

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/member_texts.py` | All §13 / §18.2 / §19.1 Russian strings as format helpers |
| `backend/app/services/entity_limits.py` | `MEMBER_LIMIT = 4`, `LIMIT_MEMBERS` (§19.1) |
| `frontend/src/constants/entityLimits.ts` | Same `LIMIT_MEMBERS` |
| `backend/app/services/membership_lifecycle.py` | Leave/remove, join conversion, seed new budget, defaults |
| `backend/app/services/ownership_transfer.py` | Create pending transfer, accept, refuse, notify |
| `backend/app/models/ownership_transfer.py` | Pending transfer ORM |
| `backend/alembic/versions/o5d6e7f8a9b0_ownership_transfers.py` | Migration |
| `backend/app/api/v1/members.py` | Extend: leave, transfer request, regenerate already exists; rewrite delete |
| `backend/app/api/v1/wallets.py` | On shared wallet delete → silent default reassignment |
| `backend/app/services/history_analytics.py` | Departed label + `should_include_created_by` for departed authors |
| `backend/bot/onboarding.py` | Invite refusals, §18.2, join-with-budget flow |
| `backend/bot/membership.py` | Callbacks: join confirm/cancel, transfer accept/refuse |
| `backend/bot/main.py` | Include membership router |
| `backend/tests/test_phase9_members.py` | Backend acceptance tests |
| `frontend/src/api/members.ts` | Full client |
| `frontend/src/pages/settings/MembersSettingsPage.tsx` | Real members screen (replace shell) |
| `frontend/src/pages/settings/MemberDetailPage.tsx` | Member card: transfer / remove |
| `frontend/src/components/settings/InviteLinkSheet.tsx` | Invite + copy + limit hint |
| `frontend/src/i18n/locales/ru.json` | Members UI strings from design/PRD |
| Vitest files | UI + display helpers |

---

### Task 1: Member texts + MEMBER_LIMIT constant

**Files:**
- Create: `backend/app/services/member_texts.py`
- Modify: `backend/app/services/entity_limits.py`
- Modify: `frontend/src/constants/entityLimits.ts`
- Modify: `frontend/src/constants/entityLimits.test.ts`
- Test: `backend/tests/test_phase9_members.py`

**Interfaces:**
- Produces:
  - `MEMBER_LIMIT = 4`
  - `LIMIT_MEMBERS = "В семейном бюджете уже 4 участника — это предел."`
  - Helpers returning exact PRD strings (budget name substituted where needed):
    - `invite_link_invalid()`
    - `invite_family_full()`  # same wording as chat «уже 4 участника»
    - `invite_already_member(budget_name: str)`
    - `join_has_other_members()`
    - `join_personal_wallet_cap(count: int)`
    - `join_confirm_prompt(budget_name: str)`  # body only; buttons separate
    - `welcome_invited(budget_name: str)`  # §18.2 full text
    - `removed_notice(budget_name: str)`
    - `left_notice(budget_name: str)`
    - `transfer_offer(budget_name: str)`
    - `transfer_accepted_to_former(new_owner_name: str, budget_name: str)`
    - `transfer_refused_to_former(name: str)`
    - `transfer_accepted_to_others(new_owner_name: str, budget_name: str)`
    - `departed_label(name: str) -> str`  # `f"{name} (бывший участник)"`
- Chat full-family refusal (§13.1): `В этом семейном бюджете уже 4 участника — это предел.` — keep as separate helper `invite_family_full_chat()` (note «этом» vs app «В семейном»).
- Consumes: nothing.

- [ ] **Step 1: Write failing tests** in `backend/tests/test_phase9_members.py`:

```python
from app.services.entity_limits import LIMIT_MEMBERS, MEMBER_LIMIT
from app.services.member_texts import (
    departed_label,
    invite_already_member,
    invite_family_full_chat,
    invite_link_invalid,
    join_has_other_members,
    join_personal_wallet_cap,
    left_notice,
    removed_notice,
    welcome_invited,
)

def test_member_limit_constant_and_app_message():
    assert MEMBER_LIMIT == 4
    assert LIMIT_MEMBERS == "В семейном бюджете уже 4 участника — это предел."

def test_invite_and_join_texts_verbatim():
    assert "больше не действует" in invite_link_invalid()
    assert invite_family_full_chat() == (
        "В этом семейном бюджете уже 4 участника — это предел."
    )
    assert invite_already_member("Семья Юсуповых") == (
        "Вы уже участник бюджета «Семья Юсуповых»."
    )
    assert "пока в вашем бюджете есть участники" in join_has_other_members()
    assert "Сейчас у вас 12" in join_personal_wallet_cap(12)
    assert departed_label("Рустам") == "Рустам (бывший участник)"
    assert removed_notice("Семья Каримовых").startswith(
        "Вы больше не участник семейного бюджета «Семья Каримовых»."
    )
    assert left_notice("Семья Каримовых").startswith(
        "Вы вышли из бюджета «Семья Каримовых»."
    )
    assert "Вы присоединились к бюджету «Семья Юсуповых»." in welcome_invited(
        "Семья Юсуповых"
    )
```

Copy every multiline string **character-for-character** from PRD §13.1, §13.2, §13.3, §13.5, §18.2, §19.1.

- [ ] **Step 2:** Run `cd backend && ./venv/bin/pytest -q tests/test_phase9_members.py::test_member_limit_constant_and_app_message tests/test_phase9_members.py::test_invite_and_join_texts_verbatim -v` — FAIL (modules missing).

- [ ] **Step 3: Implement** `member_texts.py` and add constants to both entity_limits files. Frontend test asserts `LIMIT_MEMBERS` equals the §19.1 string.

- [ ] **Step 4:** Same tests PASS.

- [ ] **Step 5: Commit** `feat(members): add PRD member texts and limit constant`

---

### Task 2: Leave / remove lifecycle service

**Files:**
- Create: `backend/app/services/membership_lifecycle.py`
- Modify: `backend/bot/onboarding.py` — extract `copy_seed_data` / `assign_default_card_uzs` into importable helpers if not already (prefer importing from onboarding or move seed helpers to `app/services/budget_seed.py` **only if needed**; otherwise import from `bot.onboarding` carefully — prefer new `app/services/budget_seed.py` with the same seed lists moved/re-exported so API layer does not import bot).
- Preferred: Create `backend/app/services/budget_seed.py` containing `SEED_*`, `copy_seed_data`, `assign_default_card_uzs`, `copy_seed_categories_only`, `copy_seed_wallets_only`. Update `bot/onboarding.py` to import from there.
- Test: `backend/tests/test_phase9_members.py`
- Modify: `backend/app/api/v1/members.py` — wire `DELETE` to lifecycle; add `POST /members/leave`

**Interfaces:**
- Produces:
  ```python
  async def detach_member_to_own_budget(
      session: AsyncSession,
      *,
      departing_user: User,
      old_budget: FamilyBudget,
      reason: Literal["removed", "left"],
      bot: Bot | None = None,
  ) -> FamilyBudget:
      """Move user to a new owned budget. Personal wallets+ops follow.
      Shared-wallet ops stay. Seed categories always; seed 4 wallets only
      if no personal wallets followed. Set default per §13.3. Notify with
      removed_notice or left_notice. Soft-delete empty old budget only when
      this was a join-conversion path — NOT here.
      Returns the new FamilyBudget.
      """

  async def count_active_members(session, family_budget_id) -> int: ...
  async def count_all_wallets_for_user_budget(session, user) -> int:
      """All non-deleted wallets in user's current budget (shared+personal owned). Used for join cap: solo owner brings every wallet as personal."""
  ```
- Leave/remove algorithm (exact):
  1. Refuse if `departing_user.role == "owner"` (owner must transfer first) — API 400.
  2. Snapshot old-family shared aggregates if tests need (caller may compare).
  3. Create new `FamilyBudget(name=default, invite_token=secrets.token_urlsafe(16))`.
  4. Collect departing user's personal wallets in old budget (`is_personal=True`, `owner_user_id=departing_user.id`, not deleted).
  5. Move each: `family_budget_id=new`, keep `is_personal=True`, `owner_user_id=departing_user.id`. Ops stay on those wallets (travel automatically).
  6. Soft-delete any **active goals** on wallets that will become personal? On leave, personal wallets cannot have goals (Phase 8 blocks). Skip.
  7. `departing_user.family_budget_id = new.id`, `role = "owner"`. Do **not** soft-delete the user.
  8. Seed: always `copy_seed_categories_only(new)`. If `len(personal_wallets) == 0`: also seed four shared wallets; `assign_default_card_uzs`. Else: default = oldest brought personal wallet by `created_at` asc.
  9. Send Telegram notice (`removed_notice` / `left_notice`) if `bot` provided.
  10. Commit responsibility: caller commits, or service commits once — match project pattern (API commits after service). Prefer service does **not** commit; API commits.
- `DELETE /members/{id}`: owner only; call `detach_member_to_own_budget(..., reason="removed")`; resolve bot like goals.
- `POST /api/v1/members/leave`: current user must be `role=member`; `reason="left"`.
- Shared ops: unchanged `family_budget_id` via wallet; `created_by_user_id` unchanged.
- Do **not** change any shared wallet balances or shared transactions.

- [ ] **Step 1: Failing tests** (use existing fixtures from `test_members.py` / `test_phase7`):

```python
@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_remove_member_personal_follows_shared_stays_aggregates_unchanged(api_client):
    # Family: owner + member. Shared wallet with member ops. Personal wallet with ops.
    # Snapshot shared income/expense totals.
    # DELETE member.
    # Assert: personal wallet now in member's new budget; shared ops still in old;
    # shared aggregates identical; new budget has no seeded 4 if personal came;
    # member.role == owner; bot notified with removed first line.
    ...

@pytest.mark.anyio
async def test_remove_member_without_personal_seeds_four_and_default_card_uzs(api_client):
    ...

@pytest.mark.anyio
async def test_leave_uses_left_notice_first_line(api_client, monkeypatch):
    ...

@pytest.mark.anyio
async def test_owner_cannot_leave(api_client):
    # POST /members/leave as owner → 400
    ...
```

- [ ] **Step 2:** Run targeted pytest — FAIL.

- [ ] **Step 3: Implement** seed extract + lifecycle + API wiring + bot send helper (reuse `goal_notify.resolve_bot` pattern or duplicate small `resolve_bot` in membership module).

- [ ] **Step 4:** Tests PASS. Also update `test_members.py` expectations if old soft-delete behaviour is asserted — departing user must remain `is_deleted=False` with new `family_budget_id`.

- [ ] **Step 5: Commit** `feat(members): leave and remove create own budget with personal wallets`

---

### Task 3: Join-with-own-budget conversion + invite refusals + §18.2

**Files:**
- Modify: `backend/app/services/membership_lifecycle.py` — add `join_family_with_own_budget`
- Modify: `backend/bot/onboarding.py` — start_handler refusals + welcome
- Create: `backend/bot/membership.py` — join confirm/cancel callbacks
- Modify: `backend/bot/main.py` — include router
- Test: `backend/tests/test_phase9_members.py`, update `test_onboarding.py` as needed

**Interfaces:**
- Produces:
  ```python
  class JoinBlockReason(str, Enum):
      HAS_OTHER_MEMBERS = "has_other_members"
      PERSONAL_WALLET_CAP = "personal_wallet_cap"

  async def evaluate_join_from_own_budget(session, user, target_budget) -> JoinBlockReason | None:
      """Order: other members first, then wallet count > 5.
      Wallet count = all non-deleted wallets in user's current solo budget
      (they all become personal). Cap is PERSONAL_WALLET_LIMIT (5).
      """

  async def convert_join_with_own_budget(session, *, user: User, target: FamilyBudget) -> None:
      """Preconditions already checked + user confirmed.
      - Delete active goals on any wallets being moved (shared→personal).
      - Remap categories on moved ops by translation_key into target budget;
        unmatched → NULL category ids («Без категории»).
      - Move ALL wallets from old budget to target as personal
        (is_personal=True, owner_user_id=user.id).
      - Keep user's default_wallet_id (wallet travelled).
      - Soft-delete old FamilyBudget (and do not leave orphan shared state).
      - Attach user: family_budget_id=target.id, role=member.
      - Target member count must still be < 4 at confirm time (re-check).
      """
  ```
- Bot `/start` with `invite_<token>` when **already registered**:
  1. Invalid/missing token → `invite_link_invalid()` (replace old invalid_invite wording for this path).
  2. Else if user's `family_budget_id == target.id` and active → `invite_already_member(name)`.
  3. Else if `count_active_members(target) >= 4` → `invite_family_full_chat()`.
  4. Else if user is active in another budget:
     - `evaluate_join_from_own_budget`; if `HAS_OTHER_MEMBERS` → refusal text, nothing changes.
     - if `PERSONAL_WALLET_CAP` → `join_personal_wallet_cap(n)`, nothing changes.
     - else → send `join_confirm_prompt` with inline `[Присоединиться]` `[Отмена]` (callback `join_accept:<token>`, `join_cancel`).
  5. On accept callback: re-run checks; `convert_join_with_own_budget`; send `welcome_invited(target.name)`.
- Bot `/start` for **new** user via invite (existing language flow): after attach, send `welcome_invited(budget.name)` instead of old `welcome_member`. Also enforce member limit before language picker / before create.
- New-user path: no own budget — no conversion.

- [ ] **Step 1: Failing tests** for each refusal text; cap before confirm; successful conversion (wallets personal, ops travel, old budget deleted, goals gone, invented category → NULL); aggregates in target family unchanged for pre-existing shared figures.

- [ ] **Step 2–4:** Implement + pass.

- [ ] **Step 5: Commit** `feat(members): join with own budget conversion and invite refusals`

---

### Task 4: Ownership transfer

**Files:**
- Create: `backend/app/models/ownership_transfer.py`
- Create: `backend/alembic/versions/o5d6e7f8a9b0_ownership_transfers.py` (`down_revision = "n4c5d6e7f8a9"`)
- Create: `backend/app/services/ownership_transfer.py`
- Modify: `backend/app/api/v1/members.py` — `POST /members/{id}/transfer`
- Modify: `backend/bot/membership.py` — accept/refuse callbacks
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_phase9_members.py`

**Interfaces:**
- Model `OwnershipTransfer`: `id`, `family_budget_id`, `from_user_id`, `to_user_id`, `status` (`pending`|`accepted`|`refused`|`cancelled`), timestamps. At most one `pending` per family (enforce in service: cancel/refuse previous or reject new).
- `POST /members/{member_id}/transfer` (owner only):
  - Target must be active member of same family, not self, role member.
  - Create pending row; send `transfer_offer(budget.name)` to recipient with `[Принять]` `[Отказаться]`.
- Accept: swap roles (`to`→owner, `from`→member); notify former owner + remaining members (§13.5); irreversible.
- Refuse: notify former owner; keep roles; mark refused.
- Callbacks: `own_xfer_accept:<uuid>`, `own_xfer_refuse:<uuid>`.

- [ ] **Step 1: Failing tests** accept path (roles swapped, three notification audiences), refuse path (owner keeps role, notified).

- [ ] **Step 2–4:** Migration + implement + pass.

- [ ] **Step 5: Commit** `feat(members): ownership transfer with recipient confirmation`

---

### Task 5: Departed label + default wallet on shared delete + should_include_created_by

**Files:**
- Modify: `backend/app/services/history_analytics.py`
- Modify: `backend/app/api/v1/wallets.py` (+ small helper in `membership_lifecycle.py`: `reassign_defaults_after_shared_wallet_deleted`)
- Test: `backend/tests/test_phase9_members.py`, adjust `test_history_analytics.py` if soft-delete-member assumptions break

**Interfaces:**
- Author label helper:
  ```python
  def format_history_author(user: User | None, *, family_budget_id: uuid.UUID) -> str | None:
      # resolve display name as today
      # if user is None: "Unknown"
      # if user.family_budget_id != family_budget_id or user.is_deleted:
      #     return departed_label(name)
      # return name
  ```
- `should_include_created_by`: True if active members ≥ 2 **OR** any non-deleted transaction in the family has `created_by_user_id` of a user who is not an active member of this family (covers departed after move). Keep existing soft-deleted-in-family behaviour working.
- On owner delete of **shared** wallet: for every active family user whose `default_wallet_id == deleted_wallet.id`, set default to oldest non-deleted **shared** wallet in the family (`created_at` asc). **No** Telegram message. Personal wallet deletes: existing behaviour / SET NULL is fine if holder must pick again — if holder's default was that personal wallet, existing FK ondelete SET NULL may already clear it; if null, quick entry falls back to first visible — acceptable unless PRD says otherwise (PRD only specifies shared-delete case).

- [ ] **Step 1: Failing tests** departed label after remove; silent default reassignment; old-family aggregates unchanged regression already in Task 2.

- [ ] **Step 2–4:** Implement + pass.

- [ ] **Step 5: Commit** `feat(members): departed labels and silent default wallet reassignment`

---

### Task 6: Frontend — Members settings UI

**Files:**
- Replace/rename: `MembersSettingsShellPage.tsx` → `MembersSettingsPage.tsx` (or keep filename and upgrade in place; update `AppShell` import)
- Create: `InviteLinkSheet.tsx`, `MemberDetailPage.tsx`, exit confirm sheet
- Modify: `frontend/src/api/members.ts` — `regenerateInviteLink`, `removeMember`, `leaveFamily`, `requestTransfer`; extend `MemberResponse` with `created_at: string`
- Modify: backend `MemberResponse` to include `created_at` (ISO) for design subtitle `с DD.MM.YYYY`
- Modify: `memberDisplay.ts` — row subtitle with join date when not self; keep `Владелец · вы` / `Участник · вы`
- Modify: `ru.json` — strings from design: `Ссылка-приглашение`, `Скопировать`, `Выйти из бюджета`, transfer/remove confirm copy (use PRD meaning; control labels from design where present)
- Tests: replace `membersSettingsShell.test.tsx`; add invite sheet limit test; owner has no exit; member has exit and no invite action
- Limit sheet: when `member_count >= 4`, invite sheet shows `LIMIT_MEMBERS` under field, copy disabled (design `limitMember`)

**UI behaviour (design + PRD):**
- Owner: action `Ссылка-приглашение` opens sheet with link + `Скопировать`; optional `Перевыпустить` control — PRD requires reissue; if design omits a separate button, put reissue as secondary action on the same sheet (PRD behaviour wins). Do not invent a third screen.
- Member: `hasDanger` `Выйти из бюджета` with confirmation → `POST /members/leave`; **no** invite action.
- Rows chevron → `/settings/members/:id`. Owner on another member: actions `Передать права владения` (confirm) and `Удалить участника` (confirm). Owner on self: no remove/transfer-to-self. Member: read-only detail.
- Owner never sees exit.

- [ ] **Step 1: Failing vitest** for owner/member chrome, limit message, no owner exit.

- [ ] **Step 2–4:** Implement + pass. Backend list endpoint returns `created_at`.

- [ ] **Step 5: Commit** `feat(members): real Участники settings UI`

---

### Task 7: Full suite green + acceptance coverage gaps

**Files:**
- `backend/tests/test_phase9_members.py` (fill any missing PRD acceptance automatable cases)
- Fix regressions in `test_members.py`, `test_onboarding.py`, `test_history_analytics.py`

**Must have automated coverage:**
1. Each §13.1 refusal text
2. Join conversion to personal + goals deleted + category remap
3. Wallet cap blocks before confirm
4. Removal split personal vs shared + aggregate equality
5. Default wallet rules (leave with/without personal; join keeps default; shared delete silent)
6. Transfer accept + refuse
7. Departed label
8. §18.2 welcome text
9. Owner no leave endpoint success

- [ ] **Step 1:** Run `cd backend && ./venv/bin/pytest -q` and `cd frontend && npx vitest run --reporter=dot` — fix failures.

- [ ] **Step 2: Commit** `test(members): complete phase 9 acceptance coverage` (or fix commits as needed)

- [ ] **Step 3:** Ensure branch has all Phase 9 commits; no Phase 10 work.

---

## Self-review checklist

1. Spec coverage: §13.1–13.5, §18.2, §19.1 members, Settings Участники, personal wallet visibility preserved, goals deleted on join conversion, seed rules, default wallet three cases — mapped to Tasks 1–6.
2. No placeholders / TBD in steps.
3. `LIMIT_MEMBERS` (app) ≠ `invite_family_full_chat` (bot) — wording differs by design/PRD («В семейном» vs «В этом семейном»).
4. Per-person analytics breakdown = History `created_by` in analytics History tab (no separate charts block exists in §17.5).
5. Member detail screen not drawn in design file — actions required by design note + PRD; follow existing settings entity detail patterns; ask customer only if action set is ambiguous (it is not: transfer + remove on card).
)
