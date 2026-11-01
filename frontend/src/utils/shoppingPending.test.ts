import { describe, expect, it, vi } from 'vitest'

import { ShoppingApiError } from '../api/shopping'
import {
  clearPending,
  clearPendingIfMatches,
  resolveStartup,
  loadWaiting,
  parseLaunchParam,
  readPending,
  rememberPending,
  resolveLaunch,
  startBotAmount,
  createBotStarter,
  submitManualAmount,
  type PendingStorage,
} from './shoppingPending'

const ID = '0b9f3c1e-2d4a-4b6c-8e1f-123456789abc'
const mem = (): PendingStorage & { data: Map<string, string> } => {
  const data = new Map<string, string>()
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  }
}
const pending = (over: Record<string, unknown> = {}) => ({
  id: ID, status: 'awaiting', method: 'receipt', expires_at: 'x', purchase_id: null, amount: null,
  ...over,
}) as never

describe('parseLaunchParam', () => {
  it('reads ?purchase=<uuid>, rejects junk and absence', () => {
    expect(parseLaunchParam(`?purchase=${ID}`)).toBe(ID)
    expect(parseLaunchParam('?purchase=nope')).toBeNull()
    expect(parseLaunchParam('')).toBeNull()
  })
})

describe('remembered pending', () => {
  it('round-trips and clears; survives broken storage', () => {
    const s = mem()
    rememberPending(s, { id: ID, method: 'voice', ids: ['a'] })
    expect(readPending(s)).toEqual({ id: ID, method: 'voice', ids: ['a'] })
    clearPending(s)
    expect(readPending(s)).toBeNull()
    s.setItem('shopping_pending', '{oops')
    expect(readPending(s)).toBeNull()
  })
})

describe('startBotAmount', () => {
  it('creates pending with the ticked ids and method, remembers it, THEN closes the app', async () => {
    const order: string[] = []
    const create = vi.fn(async () => {
      order.push('create')
      return { pending: pending(), created: true }
    })
    const remember = vi.fn(() => void order.push('remember'))
    const close = vi.fn(() => void order.push('close'))
    const r = await startBotAmount({ create, remember, close }, 'receipt', ['a', 'b'], 'tok')
    expect(r).toBe('closed')
    expect(create).toHaveBeenCalledWith({ item_ids: ['a', 'b'], method: 'receipt', client_token: 'tok' })
    expect(remember).toHaveBeenCalledWith({ id: ID, method: 'receipt', ids: ['a', 'b'] })
    expect(order).toEqual(['create', 'remember', 'close'])
  })

  it('does NOT close when the request failed; receipt_disabled is told apart', async () => {
    const close = vi.fn()
    const remember = vi.fn()
    const fail = (code: 'network' | 'receipt_disabled') =>
      vi.fn(async () => { throw new ShoppingApiError(code) })
    expect(await startBotAmount({ create: fail('network'), remember, close }, 'voice', ['a'], 't')).toBe('failed')
    expect(await startBotAmount({ create: fail('receipt_disabled'), remember, close }, 'receipt', ['a'], 't')).toBe('receipt_disabled')
    expect(close).not.toHaveBeenCalled()
    expect(remember).not.toHaveBeenCalled()
  })
})

describe('createBotStarter (client_token per attempt)', () => {
  const mk = (create: ReturnType<typeof vi.fn>) => {
    let n = 0
    const close = vi.fn()
    const starter = createBotStarter(
      { create: create as never, remember: vi.fn(), close },
      () => `tok${++n}`,
    )
    return { starter, close }
  }
  const ok = () => vi.fn(async () => ({ pending: pending(), created: true }))
  const tokenOf = (c: ReturnType<typeof vi.fn>, i: number) => (c.mock.calls[i] as any)[0].client_token

  it('network retry of the same attempt keeps the token', async () => {
    const create = vi.fn()
      .mockRejectedValueOnce(new ShoppingApiError('network'))
      .mockResolvedValueOnce({ pending: pending(), created: true })
    const { starter } = mk(create)
    expect(await starter.start('voice', ['a'])).toBe('failed')
    expect(await starter.start('voice', ['a'])).toBe('closed')
    expect(tokenOf(create, 0)).toBe(tokenOf(create, 1))
  })
  it('another way after a failed one gets a NEW token', async () => {
    const create = vi.fn()
      .mockRejectedValueOnce(new ShoppingApiError('network'))
      .mockResolvedValueOnce({ pending: pending(), created: true })
    const { starter } = mk(create)
    await starter.start('voice', ['a'])
    await starter.start('receipt', ['a'])
    expect(tokenOf(create, 0)).not.toBe(tokenOf(create, 1))
  })
  it('a new choice after a successful one gets a NEW token', async () => {
    const create = ok()
    const { starter } = mk(create)
    await starter.start('voice', ['a'])
    await starter.start('voice', ['a'])
    expect(tokenOf(create, 0)).not.toBe(tokenOf(create, 1))
  })
  it('409 token_conflict: one retry with a fresh token, then closes', async () => {
    const create = vi.fn()
      .mockRejectedValueOnce(new ShoppingApiError('token_conflict', 409))
      .mockResolvedValueOnce({ pending: pending(), created: true })
    const { starter, close } = mk(create)
    expect(await starter.start('receipt', ['a'])).toBe('closed')
    expect(create).toHaveBeenCalledTimes(2)
    expect(tokenOf(create, 0)).not.toBe(tokenOf(create, 1))
    expect(close).toHaveBeenCalledTimes(1)
  })
  it('second conflict is not retried again', async () => {
    const create = vi.fn(async () => { throw new ShoppingApiError('token_conflict', 409) })
    const { starter, close } = mk(create)
    expect(await starter.start('receipt', ['a'])).toBe('failed')
    expect(create).toHaveBeenCalledTimes(2)
    expect(close).not.toHaveBeenCalled()
  })
  it('410 purchase_closed: retries once with a fresh token and closes', async () => {
    const create = vi.fn()
      .mockRejectedValueOnce(new ShoppingApiError('purchase_closed', 410))
      .mockResolvedValueOnce({ pending: pending(), created: true })
    const { starter, close } = mk(create)
    expect(await starter.start('voice', ['a'])).toBe('closed')
    expect(create).toHaveBeenCalledTimes(2)
    expect(tokenOf(create, 0)).not.toBe(tokenOf(create, 1))
    expect(close).toHaveBeenCalledTimes(1)
  })
  it('second refusal -> failed, and the NEXT press uses yet another token', async () => {
    const create = vi.fn(async () => { throw new ShoppingApiError('purchase_closed', 410) })
    const { starter, close } = mk(create)
    expect(await starter.start('voice', ['a'])).toBe('failed')
    expect(create).toHaveBeenCalledTimes(2)
    expect(close).not.toHaveBeenCalled()
    await starter.start('voice', ['a'])
    expect(tokenOf(create, 2)).not.toBe(tokenOf(create, 1))
  })
})

describe('resolveLaunch (deep link from the bot)', () => {
  const purchase = { id: ID, items_recorded: 2 } as never
  it('completed -> result with the purchase', async () => {
    const r = await resolveLaunch(ID, {
      fetchPending: async () => pending({ status: 'completed', purchase_id: ID }),
      fetchPurchase: async () => purchase,
    })
    expect(r).toEqual({ kind: 'result', purchase })
  })
  it('unrecognized -> manual entry with the method (for «ещё раз»)', async () => {
    const r = await resolveLaunch(ID, {
      fetchPending: async () => pending({ status: 'unrecognized', method: 'voice' }),
      fetchPurchase: async () => purchase,
    })
    expect(r).toEqual({ kind: 'manual', id: ID, method: 'voice', status: 'unrecognized' })
  })
  it('awaiting -> manual entry too (user came back himself)', async () => {
    const r = await resolveLaunch(ID, {
      fetchPending: async () => pending(),
      fetchPurchase: async () => purchase,
    })
    expect(r).toMatchObject({ kind: 'manual', id: ID, status: 'awaiting' })
  })
  it('cancelled / expired / not found -> gone; network -> failed', async () => {
    const mk = (f: () => Promise<unknown>) => ({ fetchPending: f as never, fetchPurchase: async () => purchase })
    expect((await resolveLaunch(ID, mk(async () => pending({ status: 'expired' })))).kind).toBe('gone')
    expect((await resolveLaunch(ID, mk(async () => pending({ status: 'cancelled' })))).kind).toBe('gone')
    expect((await resolveLaunch(ID, mk(async () => { throw new ShoppingApiError('not_found', 404) }))).kind).toBe('gone')
    expect((await resolveLaunch(ID, mk(async () => { throw new ShoppingApiError('network') }))).kind).toBe('failed')
  })
})

describe('loadWaiting («Покупки» tab, user came back himself)', () => {
  it('nothing remembered -> null, no request', async () => {
    const fetchPending = vi.fn()
    expect(await loadWaiting(mem(), fetchPending)).toBeNull()
    expect(fetchPending).not.toHaveBeenCalled()
  })
  it('awaiting -> shows the wait with the remembered method', async () => {
    const s = mem()
    rememberPending(s, { id: ID, method: 'voice', ids: ['a'] })
    expect(await loadWaiting(s, async () => pending({ method: 'voice' }))).toEqual({ id: ID, method: 'voice', status: 'awaiting' })
  })
  it('unrecognized still offers manual entry', async () => {
    const s = mem()
    rememberPending(s, { id: ID, method: 'receipt', ids: ['a'] })
    expect((await loadWaiting(s, async () => pending({ status: 'unrecognized' })))?.status).toBe('unrecognized')
  })
  it('finished / expired / foreign -> forgotten, null', async () => {
    for (const status of ['completed', 'cancelled', 'expired']) {
      const s = mem()
      rememberPending(s, { id: ID, method: 'receipt', ids: ['a'] })
      expect(await loadWaiting(s, async () => pending({ status }))).toBeNull()
      expect(readPending(s)).toBeNull()
    }
    const s = mem()
    rememberPending(s, { id: ID, method: 'receipt', ids: ['a'] })
    expect(await loadWaiting(s, async () => { throw new ShoppingApiError('not_found', 404) })).toBeNull()
    expect(readPending(s)).toBeNull()
  })
  it('network hiccup keeps the memory and shows nothing', async () => {
    const s = mem()
    rememberPending(s, { id: ID, method: 'receipt', ids: ['a'] })
    expect(await loadWaiting(s, async () => { throw new ShoppingApiError('network') })).toBeNull()
    expect(readPending(s)).not.toBeNull()
  })
})

describe('submitManualAmount', () => {
  it('success -> result and the waiting memory is cleared', async () => {
    const s = mem()
    rememberPending(s, { id: ID, method: 'receipt', ids: ['a'] })
    const purchase = { id: ID } as never
    const send = vi.fn(async () => ({ purchase, replay: false }))
    expect(await submitManualAmount(s, send, ID, 412000)).toEqual({ kind: 'ok', purchase })
    expect(send).toHaveBeenCalledWith(ID, 412000)
    expect(readPending(s)).toBeNull()
  })
  it('failure keeps the memory and reports failed', async () => {
    const s = mem()
    rememberPending(s, { id: ID, method: 'receipt', ids: ['a'] })
    expect(await submitManualAmount(s, async () => { throw new ShoppingApiError('network') }, ID, 5)).toEqual({ kind: 'failed' })
    expect(readPending(s)).not.toBeNull()
  })
})

describe('resolveStartup', () => {
  const ctx = { pathname: '/', search: '' }
  const remembered = () => {
    const s = mem()
    rememberPending(s, { id: ID, method: 'receipt', ids: ['a'] })
    return s
  }
  it('nothing remembered -> skip, no request', async () => {
    const fetchPending = vi.fn()
    expect(await resolveStartup(mem(), fetchPending, ctx)).toEqual({ kind: 'skip' })
    expect(fetchPending).not.toHaveBeenCalled()
  })
  it('completed -> open the result by id, memory kept until shown', async () => {
    const s = remembered()
    expect(await resolveStartup(s, async () => pending({ status: 'completed', purchase_id: 'p1' }), ctx)).toEqual({ kind: 'open', id: ID })
    expect(readPending(s)).not.toBeNull()
  })
  it('unrecognized -> open manual entry', async () => {
    expect(await resolveStartup(remembered(), async () => pending({ status: 'unrecognized' }), ctx)).toEqual({ kind: 'open', id: ID })
  })
  it('awaiting -> shopping tab with the banner', async () => {
    expect(await resolveStartup(remembered(), async () => pending(), ctx)).toEqual({ kind: 'waiting' })
  })
  it('cancelled / expired / not_found -> cleared, normal start', async () => {
    for (const status of ['cancelled', 'expired']) {
      const s = remembered()
      expect(await resolveStartup(s, async () => pending({ status }), ctx)).toEqual({ kind: 'skip' })
      expect(readPending(s)).toBeNull()
    }
    const s = remembered()
    expect(await resolveStartup(s, async () => { throw new ShoppingApiError('not_found', 404) }, ctx)).toEqual({ kind: 'skip' })
    expect(readPending(s)).toBeNull()
  })
  it('network error -> normal start, memory kept', async () => {
    const s = remembered()
    expect(await resolveStartup(s, async () => { throw new ShoppingApiError('network') }, ctx)).toEqual({ kind: 'skip' })
    expect(readPending(s)).not.toBeNull()
  })
  it('explicit deep link / trip page -> skip without request', async () => {
    const fetchPending = vi.fn()
    expect(await resolveStartup(remembered(), fetchPending, { pathname: '/shopping/trip', search: `?purchase=${ID}` })).toEqual({ kind: 'skip' })
    expect(await resolveStartup(remembered(), fetchPending, { pathname: '/', search: `?purchase=${ID}` })).toEqual({ kind: 'skip' })
    expect(await resolveStartup(remembered(), fetchPending, { pathname: '/', search: `?tx=${ID}` })).toEqual({ kind: 'skip' })
    expect(fetchPending).not.toHaveBeenCalled()
  })
  it('already on the shopping tab and awaiting -> skip (no navigation)', async () => {
    expect(await resolveStartup(remembered(), async () => pending(), { pathname: '/shopping', search: '' })).toEqual({ kind: 'skip' })
  })
})

describe('clearPendingIfMatches', () => {
  it('clears only the matching purchase', () => {
    const s = mem()
    rememberPending(s, { id: ID, method: 'voice', ids: [] })
    clearPendingIfMatches(s, 'other')
    expect(readPending(s)).not.toBeNull()
    clearPendingIfMatches(s, ID)
    expect(readPending(s)).toBeNull()
  })
})
