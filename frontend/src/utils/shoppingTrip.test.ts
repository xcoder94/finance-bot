import { describe, expect, it } from 'vitest'

import { canFinishTrip, checkedIdsInListOrder, newClientToken, toggleChecked } from './shoppingTrip'

const mk = (id: string) => ({ id, name: id, created_at: '2026-10-31T10:00:00Z' })

describe('shoppingTrip helpers', () => {
  it('toggleChecked adds and removes without mutating', () => {
    const a = new Set<string>()
    const b = toggleChecked(a, 'x')
    expect([...b]).toEqual(['x'])
    expect(a.size).toBe(0)
    expect(toggleChecked(b, 'x').size).toBe(0)
  })

  it('finish is disabled until something is checked', () => {
    expect(canFinishTrip(new Set())).toBe(false)
    expect(canFinishTrip(new Set(['a']))).toBe(true)
  })

  it('only checked ids that still exist, in list order', () => {
    const items = [mk('a'), mk('b'), mk('c')]
    expect(checkedIdsInListOrder(items, new Set(['c', 'a', 'gone']))).toEqual(['a', 'c'])
  })

  it('client token is a uuid, different each time', () => {
    const re = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
    const a = newClientToken()
    expect(a).toMatch(re)
    expect(newClientToken()).not.toBe(a)
  })
})

import { describe as d2, expect as e2, it as i2, vi as v2 } from 'vitest'
import type { ShoppingPurchase } from '../api/shopping'
import type { PurchaseOutcome } from '../store/shoppingStore'
import { createTripSubmitter, finishTrip, pickTripWallet, resultWalletLabel } from './shoppingTrip'

const purchaseOf = (over: Partial<ShoppingPurchase> = {}): ShoppingPurchase => ({
  id: 'p', transaction_id: 't', items_recorded: 1, amount: 10000, currency: 'UZS',
  category_label: 'Еда', wallet_name: 'Карта сум', remaining: 5, items_left: 0, ...over,
})

d2('createTripSubmitter (B1: token survives a lost answer)', () => {
  const lost: PurchaseOutcome = { kind: 'failed', definite: false }
  i2('keeps the token after a network failure even when sum and ticks change', async () => {
    const send = v2.fn().mockResolvedValueOnce(lost).mockResolvedValueOnce(lost)
    const sub = createTripSubmitter(send)
    await sub.submit(['1'], 10000)
    await sub.submit(['1', '2'], 10002)
    e2(send.mock.calls[0][0].client_token).toBe(send.mock.calls[1][0].client_token)
    e2(send.mock.calls[1][0]).toMatchObject({ item_ids: ['1', '2'], amount: 10002 })
  })

  i2('rotates the token only after a definite (4xx) answer', async () => {
    const send = v2.fn()
      .mockResolvedValueOnce({ kind: 'failed', definite: true })
      .mockResolvedValueOnce({ kind: 'no_wallet' })
      .mockResolvedValueOnce(lost)
    const sub = createTripSubmitter(send)
    await sub.submit(['1'], 1)
    await sub.submit(['1'], 1)
    await sub.submit(['1'], 1)
    const t = send.mock.calls.map((c) => c[0].client_token)
    e2(t[1]).not.toBe(t[0])
    e2(t[2]).not.toBe(t[1])
  })

  i2('ok: requested = sent count; on replay the result reflects what was really recorded', async () => {
    const p = purchaseOf({ items_recorded: 1 })
    const fresh = createTripSubmitter(v2.fn().mockResolvedValue({ kind: 'ok', purchase: p, replay: false }))
    e2(await fresh.submit(['1', '2'], 5)).toEqual({ kind: 'ok', purchase: p, requested: 2 })
    const replay = createTripSubmitter(v2.fn().mockResolvedValue({ kind: 'ok', purchase: p, replay: true }))
    e2(await replay.submit(['1', '2'], 5)).toEqual({ kind: 'ok', purchase: p, requested: 1 })
  })

  i2('no_wallet and failed are passed through', async () => {
    const sub = createTripSubmitter(v2.fn().mockResolvedValue({ kind: 'no_wallet' }))
    e2((await sub.submit(['1'], 1)).kind).toBe('no_wallet')
    const sub2 = createTripSubmitter(v2.fn().mockResolvedValue(lost))
    e2((await sub2.submit(['1'], 1)).kind).toBe('failed')
  })
})

d2('finishTrip (Готово)', () => {
  i2('re-reads the list for the family, then goes back to /shopping', () => {
    const calls: string[] = []
    finishTrip({
      load: (scope, opts) => { calls.push(`load:${scope}:${opts.silent}`); return Promise.resolve() },
      navigate: (to, opts) => { calls.push(`nav:${to}:${opts.replace}`) },
      scope: 'fam',
    })
    e2(calls).toEqual(['load:fam:true', 'nav:/shopping:true'])
  })
})

d2('wallets (B2)', () => {
  const w = (id: string, is_personal: boolean) => ({ id, is_personal })
  i2('guess: default wallet; else the only shared one; else unknown (never a wrong name)', () => {
    e2(pickTripWallet([w('p', true), w('s', false)], null)?.id).toBe('s')
    e2(pickTripWallet([w('p', true), w('s', false)], 'p')?.id).toBe('p')
    e2(pickTripWallet([w('p', true), w('s1', false), w('s2', false)], 'gone')).toBeNull()
    e2(pickTripWallet([w('p', true)], null)).toBeNull()
    e2(pickTripWallet([], null)).toBeNull()
  })

  i2('result label comes from the API wallet_name; translated only when it is a known default wallet', () => {
    // seeded (ru) default name is 'Cash'; a renamed default would differ from it
    const t = ((k: string, o?: { lng?: string }) =>
      o?.lng ? (k === 'defaultEntities.cash' ? 'Cash' : `L:${k}`) : `T:${k}`) as never
    const wallets = [
      { id: '1', name: 'Личный QA', translation_key: null },
      { id: '2', name: 'Cash', translation_key: 'cash' },
    ]
    e2(resultWalletLabel('Карта сум', wallets, t)).toBe('Карта сум')
    e2(resultWalletLabel('Cash', wallets, t)).toBe('T:defaultEntities.cash')
    e2(resultWalletLabel('Личный QA', wallets, t)).toBe('Личный QA')
    e2(resultWalletLabel('X', null, t)).toBe('X')
  })
})
