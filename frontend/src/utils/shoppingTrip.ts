import type { TFunction } from 'i18next'

import type { ShoppingItem, ShoppingPurchase, ShoppingPurchaseBody } from '../api/shopping'
import type { PurchaseOutcome } from '../store/shoppingStore'
import { getDisplayName } from './getDisplayName'

export function toggleChecked(checked: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(checked)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  return next
}

export function canFinishTrip(checked: ReadonlySet<string>): boolean {
  return checked.size > 0
}

/** Ids of checked items that are still on the list, in list order. */
export function checkedIdsInListOrder(
  items: ShoppingItem[],
  checked: ReadonlySet<string>,
): string[] {
  return items.filter((item) => checked.has(item.id)).map((item) => item.id)
}

/** UUID v4 for the purchase client_token (double-tap / retry protection). */
export function newClientToken(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  const bytes = new Uint8Array(16)
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes)
  } else {
    for (let i = 0; i < 16; i += 1) bytes[i] = Math.floor(Math.random() * 256)
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export type TripSubmitResult =
  | { kind: 'ok'; purchase: ShoppingPurchase; requested: number }
  | { kind: 'no_wallet' }
  | { kind: 'family_changed' }
  | { kind: 'failed' }

/**
 * One client_token per trip. After a network failure / 5xx the answer is unknown (the server may
 * have recorded it), so the token is kept even if sum or ticks changed: a retry then returns what
 * was really recorded. A fresh token only after a definite 4xx answer (decision 17).
 */
export function createTripSubmitter(send: (body: ShoppingPurchaseBody) => Promise<PurchaseOutcome>) {
  let token = newClientToken()
  return {
    async submit(ids: string[], amount: number): Promise<TripSubmitResult> {
      const outcome = await send({ item_ids: ids, amount, client_token: token })
      if (outcome.kind === 'ok') {
        // On a replay the server returns the earlier recording, so «lost» is judged by it alone.
        const requested = outcome.replay ? outcome.purchase.items_recorded : ids.length
        return { kind: 'ok', purchase: outcome.purchase, requested }
      }
      if (outcome.kind === 'no_wallet') {
        token = newClientToken()
        return { kind: 'no_wallet' }
      }
      if (outcome.kind === 'family_changed') {
        token = newClientToken()
        return { kind: 'family_changed' }
      }
      if (outcome.definite) token = newClientToken()
      return { kind: 'failed' }
    },
  }
}

/** «Готово»: re-read the shared list (others may have changed it), then back to the list. */
export function finishTrip(deps: {
  load: (scope: string, options: { silent: boolean }) => Promise<void>
  navigate: (to: string, options: { replace: boolean }) => void
  scope: string
}): void {
  void deps.load(deps.scope, { silent: true })
  deps.navigate('/shopping', { replace: true })
}

/**
 * The wallet the backend will use: the user's default one, else the oldest shared one. The client
 * cannot tell which shared wallet is the oldest (no created_at), so with several it returns null
 * and the screen shows a neutral text; the result screen then names the real wallet from the API.
 */
export function pickTripWallet<W extends { id: string; is_personal: boolean }>(
  wallets: W[],
  defaultWalletId: string | null | undefined,
): W | null {
  const byDefault = wallets.find((w) => w.id === defaultWalletId)
  if (byDefault) return byDefault
  const shared = wallets.filter((w) => !w.is_personal)
  return shared.length === 1 ? shared[0] : null
}

/** Wallet shown on the result comes from the API answer; translated only if it is a default wallet. */
export function resultWalletLabel(
  apiWalletName: string,
  wallets: Array<{ name: string; translation_key: string | null }> | null,
  t: TFunction,
): string {
  const known = wallets?.find((w) => w.name === apiWalletName)
  return known ? getDisplayName(known, t) : apiWalletName
}
