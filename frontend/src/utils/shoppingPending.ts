import type {
  PendingMethod,
  PendingPurchase,
  PendingStatus,
  ShoppingPurchase,
} from '../api/shopping'
import { ShoppingApiError } from '../api/shopping'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const KEY = 'shopping_pending'

export type PendingStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
export type RememberedPending = { id: string; method: PendingMethod; ids: string[] }

/** `?purchase=<uuid>` from the bot launcher button. */
export function parseLaunchParam(search: string): string | null {
  const value = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search).get('purchase')
  return value && UUID_RE.test(value) ? value : null
}

export function browserStorage(): PendingStorage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

export function rememberPending(storage: PendingStorage | null, value: RememberedPending): void {
  try {
    storage?.setItem(KEY, JSON.stringify(value))
  } catch {
    // private mode: the wait state on the tab is just not shown
  }
}

export function readPending(storage: PendingStorage | null): RememberedPending | null {
  try {
    const raw = storage?.getItem(KEY)
    if (!raw) return null
    const v = JSON.parse(raw) as Partial<RememberedPending>
    if (
      typeof v.id !== 'string' ||
      (v.method !== 'receipt' && v.method !== 'voice') ||
      !Array.isArray(v.ids)
    ) {
      return null
    }
    return { id: v.id, method: v.method, ids: v.ids.filter((x) => typeof x === 'string') }
  } catch {
    return null
  }
}

export function clearPending(storage: PendingStorage | null): void {
  try {
    storage?.removeItem(KEY)
  } catch {
    // ignore
  }
}

export type StartBotResult = 'closed' | 'receipt_disabled' | 'failed' | 'conflict'

/** Create the wait, remember it, and only then minimise the app (the bot is waiting for the user). */
export async function startBotAmount(
  deps: {
    create: (body: {
      item_ids: string[]
      method: PendingMethod
      client_token?: string
    }) => Promise<{ pending: PendingPurchase; created: boolean }>
    remember: (value: RememberedPending) => void
    close: () => void
  },
  method: PendingMethod,
  ids: string[],
  clientToken: string,
): Promise<StartBotResult> {
  try {
    const { pending } = await deps.create({ item_ids: ids, method, client_token: clientToken })
    deps.remember({ id: pending.id, method, ids })
  } catch (e) {
    if (e instanceof ShoppingApiError &&
      (e.code === 'token_conflict' || e.code === 'purchase_closed')) return 'conflict'
    return e instanceof ShoppingApiError && e.code === 'receipt_disabled'
      ? 'receipt_disabled'
      : 'failed'
  }
  deps.close()
  return 'closed'
}

type StartDeps = Parameters<typeof startBotAmount>[0]

/**
 * client_token per attempt: a network retry of the same choice keeps it (no double wait),
 * another way / a new choice gets a fresh one; on 409 token_conflict / 410 purchase_closed one retry with a fresh token.
 */
export function createBotStarter(deps: StartDeps, makeToken: () => string) {
  let attempt: { key: string; token: string } | null = null
  return {
    async start(method: PendingMethod, ids: string[]): Promise<StartBotResult> {
      const key = `${method}:${ids.join(',')}`
      if (!attempt || attempt.key !== key) attempt = { key, token: makeToken() }
      let result = await startBotAmount(deps, method, ids, attempt.token)
      if (result === 'conflict') {
        attempt = { key, token: makeToken() }
        result = await startBotAmount(deps, method, ids, attempt.token)
      }
      if (result === 'closed' || result === 'conflict') attempt = null // a refused token is never reused
      return result === 'conflict' ? 'failed' : result
    },
  }
}

export type LaunchResolution =
  | { kind: 'result'; purchase: ShoppingPurchase }
  | { kind: 'manual'; id: string; method: PendingMethod; status: 'awaiting' | 'unrecognized' }
  | { kind: 'gone' }
  | { kind: 'failed' }

/** Deep link from the bot: finished -> result, otherwise (unrecognized / still waiting) -> manual entry. */
export async function resolveLaunch(
  id: string,
  deps: {
    fetchPending: (id: string) => Promise<PendingPurchase>
    fetchPurchase: (id: string) => Promise<ShoppingPurchase>
  },
): Promise<LaunchResolution> {
  try {
    const pending = await deps.fetchPending(id)
    if (pending.status === 'completed') {
      return { kind: 'result', purchase: await deps.fetchPurchase(pending.purchase_id ?? pending.id) }
    }
    if (pending.status === 'awaiting' || pending.status === 'unrecognized') {
      return { kind: 'manual', id: pending.id, method: pending.method, status: pending.status }
    }
    return { kind: 'gone' }
  } catch (e) {
    return e instanceof ShoppingApiError && e.code === 'not_found'
      ? { kind: 'gone' }
      : { kind: 'failed' }
  }
}

export type WaitingState = { id: string; method: PendingMethod; status: PendingStatus }

/** «Покупки» tab: is there a live wait to show? Forgets finished / expired / unknown ones. */
export async function loadWaiting(
  storage: PendingStorage | null,
  fetchPending: (id: string) => Promise<PendingPurchase>,
): Promise<WaitingState | null> {
  const remembered = readPending(storage)
  if (!remembered) return null
  try {
    const pending = await fetchPending(remembered.id)
    if (pending.status === 'awaiting' || pending.status === 'unrecognized') {
      return { id: pending.id, method: pending.method, status: pending.status }
    }
    clearPending(storage)
    return null
  } catch (e) {
    if (e instanceof ShoppingApiError && e.code === 'not_found') clearPending(storage)
    return null
  }
}

export type ManualResult = { kind: 'ok'; purchase: ShoppingPurchase } | { kind: 'failed' }

export async function submitManualAmount(
  storage: PendingStorage | null,
  send: (id: string, amount: number) => Promise<{ purchase: ShoppingPurchase; replay: boolean }>,
  id: string,
  amount: number,
): Promise<ManualResult> {
  try {
    const { purchase } = await send(id, amount)
    clearPending(storage)
    return { kind: 'ok', purchase }
  } catch {
    return { kind: 'failed' }
  }
}

/** Forget the remembered wait once its result/manual screen was shown (only if it is that purchase). */
export function clearPendingIfMatches(storage: PendingStorage | null, id: string): void {
  if (readPending(storage)?.id === id) clearPending(storage)
}

export type StartupResolution =
  | { kind: 'skip' }
  | { kind: 'open'; id: string }
  | { kind: 'waiting' }

/**
 * Every app start without an explicit deep link: a remembered wait brings the user back to its
 * result (completed), manual entry (unrecognized) or the «Покупки» tab (still waiting).
 * Dead waits (cancelled / expired / unknown) are forgotten; network trouble changes nothing.
 */
export async function resolveStartup(
  storage: PendingStorage | null,
  fetchPending: (id: string) => Promise<PendingPurchase>,
  ctx: { pathname: string; search: string },
): Promise<StartupResolution> {
  const skip: StartupResolution = { kind: 'skip' }
  const params = new URLSearchParams(ctx.search.startsWith('?') ? ctx.search.slice(1) : ctx.search)
  if (params.has('purchase') || params.has('tx') || ctx.pathname.startsWith('/shopping/trip')) return skip
  const remembered = readPending(storage)
  if (!remembered) return skip
  try {
    const pending = await fetchPending(remembered.id)
    if (pending.status === 'completed' || pending.status === 'unrecognized') {
      return { kind: 'open', id: remembered.id }
    }
    if (pending.status === 'awaiting') {
      return ctx.pathname === '/shopping' ? skip : { kind: 'waiting' }
    }
    clearPending(storage)
    return skip
  } catch (e) {
    if (e instanceof ShoppingApiError && e.code === 'not_found') clearPending(storage)
    return skip
  }
}

export type CancelResult = { kind: 'cancelled' } | { kind: 'closed' } | { kind: 'failed' }

/** Cancel the wait: 404 counts as done (nothing left to cancel); 410 -> already recorded, show its result. */
export async function cancelPendingPurchase(
  storage: PendingStorage | null,
  cancel: (id: string) => Promise<unknown>,
  id: string,
): Promise<CancelResult> {
  try {
    await cancel(id)
  } catch (e) {
    if (e instanceof ShoppingApiError && e.code === 'purchase_closed') return { kind: 'closed' }
    if (!(e instanceof ShoppingApiError && e.code === 'not_found')) return { kind: 'failed' }
  }
  clearPendingIfMatches(storage, id)
  return { kind: 'cancelled' }
}
