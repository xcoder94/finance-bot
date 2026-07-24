# Task 08 — API: Wallet Balances

Depends on: Task 06 (`06-api-history-analytics.md` — done, verified)
PRD reference: §4.1, §6

## Goal

New read-only endpoint returning the accumulated per-currency wallet
balance (all-time, not scoped to any date range) for the Home screen
summary. No schema changes — computed from existing `wallets` and
`transactions` tables.

## Endpoint

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/v1/analytics/wallet-balances` | Owner, Member | No query params |

## Balance formula

Per currency (`UZS`, `USD`), across **all** wallets of that currency in
the caller's family budget — active and soft-deleted alike (a
soft-deleted wallet still holds real money from past transactions; it's
only hidden from selection, per PRD §7/§4.7):

- `balance = income − expense + transfer_net`
- `income` — sum of income transaction amounts for wallets of this
  currency (excluding soft-deleted transactions).
- `expense` — sum of expense transaction amounts for wallets of this
  currency (excluding soft-deleted transactions).
- `transfer_net` — for every transfer: subtract `amount` from the
  from-wallet's currency bucket, add `to_amount` to the to-wallet's
  currency bucket. Same convention as `summary.transfer_net` in Task 06,
  but **unbounded by date** — every transfer ever made counts.
- No date filtering anywhere in this endpoint — all-time totals only.

## Response shape

Always returns both currencies, even if the family has no wallets of
that currency yet (`balance: 0` in that case) — fixed two-item list, so
the frontend can render a static layout without conditional branches.

```json
{
  "balances": [
    { "currency": "UZS", "balance": 4200000 },
    { "currency": "USD", "balance": 350 }
  ]
}
```

Order is always `UZS` then `USD`. Pydantic response schema
`WalletBalancesResponse` / `CurrencyBalance` in
`app/schemas/history_analytics.py`, `extra="forbid"`, matching the style
of existing schemas in that file (`PerCurrencySummary`, etc.).

## Acceptance criteria

- [x] `GET /analytics/wallet-balances` returns both `UZS` and `USD`
      entries, always, in that order
- [x] Balance = income − expense + transfer_net, computed with no date
      filtering (all-time)
- [x] Transactions belonging to soft-deleted wallets are included in the
      balance
- [x] Soft-deleted transactions (`is_deleted = true`) are excluded
- [x] Transfers between two wallets of the same currency net to zero at
      the family level (but each wallet's individual movement is still
      correctly reflected — verify via the aggregate, not per-wallet,
      since this endpoint returns currency-level totals only)
- [x] Cross-currency transfer (UZS→USD or USD→UZS) correctly moves
      `amount` out of one currency bucket and `to_amount` into the other
- [x] Family with zero wallets of a given currency returns `balance: 0`
      for that currency, not an omitted entry
- [x] Member has full read access (no 403)
- [x] No `require_owner` — both roles allowed
- [x] Response strictly matches `WalletBalancesResponse` schema
      (`extra="forbid"`) — no extra/missing fields

## Verification

Automated verification script, following the pattern of
`backend/scripts/manual_verify_currency_scoping.py` (baseline/delta
pattern — test data is never cleared between runs):

- Snapshot the current `wallet-balances` response as baseline **before**
  inserting any test data.
- Create wallets/transactions directly via `async_session_factory`, with
  known amounts, including: a soft-deleted wallet with a pre-existing
  transaction, a same-currency transfer, and a cross-currency transfer.
- Call the endpoint again, compare the **delta** against the manually
  computed expected delta — not absolute totals.
- Prints `[PASS]`/`[FAIL]` for every "Acceptance criteria" item above,
  plus a final summary, exit code 1 on any failure.

## Changelog

- **2026-07-18**: Task 08 implemented. Added `CurrencyBalance` and
  `WalletBalancesResponse` schemas (`extra="forbid"`) in
  `app/schemas/history_analytics.py`. All-time balance calculation in
  `get_wallet_balances()` in `app/services/history_analytics.py` — reuses
  the same `income − expense + transfer_net` and transfer sign convention
  as `summary`, with no date filtering; soft-deleted wallets included,
  soft-deleted transactions excluded; fixed two-item response always
  `UZS` then `USD`. Route `GET /api/v1/analytics/wallet-balances` wired
  in `app/api/v1/analytics.py` with `CurrentUserDep` only (Owner and
  Member both allowed). No migration. Unit tests in
  `backend/tests/test_history_analytics.py`: 8 new tests in
  `TestWalletBalances` (26/26 in file pass); member read-access test
  updated to include the new endpoint. No deviations from spec.

- **2026-07-19 (verification script)**: added
  `backend/scripts/manual_verify_wallet_balances.py` — exercises every
  Acceptance criteria item via `httpx` against a running local server.
  Uses baseline/delta pattern against the reused Owner/Member family
  (`telegram_id=111111`/`222222`) for the all-time formula, soft-deleted
  wallet inclusion, and soft-deleted transaction exclusion checks; creates
  a throwaway isolated family (no wallets) for the "zero wallets of a
  currency -> balance: 0" check. 11/11 PASS.