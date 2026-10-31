import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./authHeader', () => ({ getAuthHeader: () => 'Bearer t' }))

import {
  addShoppingItem,
  deleteShoppingItem,
  listShoppingItems,
  renameShoppingItem,
  ShoppingApiError,
} from './shopping'

const fetchMock = vi.fn()
beforeEach(() => vi.stubGlobal('fetch', fetchMock))
afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

function reply(status: number, body?: unknown) {
  fetchMock.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

const item = { id: 'a', name: 'Молоко', created_at: '2026-10-31T10:00:00Z' }

describe('shopping api', () => {
  it('lists items with bearer header', async () => {
    reply(200, [item])
    expect(await listShoppingItems()).toEqual([item])
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/shopping/items')
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer t')
  })

  it('add: 201 means created, 200 means it was already there', async () => {
    reply(201, item)
    expect(await addShoppingItem('Молоко')).toEqual({ item, created: true })
    reply(200, item)
    expect(await addShoppingItem('молоко')).toEqual({ item, created: false })
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ name: 'Молоко' })
  })

  it('maps 409 shopping_limit, 422 and network failure to typed codes', async () => {
    reply(409, { detail: 'shopping_limit' })
    await expect(addShoppingItem('x')).rejects.toMatchObject({ code: 'shopping_limit' })
    reply(422, { detail: [] })
    await expect(addShoppingItem('x')).rejects.toMatchObject({ code: 'invalid' })
    fetchMock.mockRejectedValueOnce(new TypeError('offline'))
    await expect(addShoppingItem('x')).rejects.toBeInstanceOf(ShoppingApiError)
    fetchMock.mockRejectedValueOnce(new TypeError('offline'))
    await expect(listShoppingItems()).rejects.toMatchObject({ code: 'network' })
  })

  it('rename: PATCH, 409 already_in_list, 404 not_found', async () => {
    reply(200, { ...item, name: 'Хлеб' })
    expect((await renameShoppingItem('a', 'Хлеб')).name).toBe('Хлеб')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/shopping/items/a')
    expect(fetchMock.mock.calls[0][1].method).toBe('PATCH')
    reply(409, { detail: 'already_in_list' })
    await expect(renameShoppingItem('a', 'Хлеб')).rejects.toMatchObject({ code: 'already_in_list' })
    reply(404, { detail: 'nf' })
    await expect(renameShoppingItem('a', 'Хлеб')).rejects.toMatchObject({ code: 'not_found' })
  })

  it('delete: 204 has no body; 404 is not_found', async () => {
    reply(204)
    await expect(deleteShoppingItem('a')).resolves.toBeUndefined()
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE')
    reply(404, {})
    await expect(deleteShoppingItem('a')).rejects.toMatchObject({ code: 'not_found' })
  })
})

describe('shopping api: purchases', () => {
  const purchase = {
    id: 'p1',
    transaction_id: 't1',
    items_recorded: 2,
    amount: 412000,
    currency: 'UZS',
    category_label: 'Еда · Продукты',
    wallet_name: 'Карта Humo',
    remaining: 3038000,
    items_left: 3,
  }

  it('posts ids, amount and client_token; 201 = new, 200 = replay', async () => {
    const { createShoppingPurchase } = await import('./shopping')
    reply(201, purchase)
    const body = { item_ids: ['a', 'b'], amount: 412000, client_token: 'tok' }
    expect(await createShoppingPurchase(body)).toEqual({ purchase, replay: false })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/shopping/purchases')
    expect(fetchMock.mock.calls[0][1].method).toBe('POST')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(body)
    reply(200, purchase)
    expect((await createShoppingPurchase(body)).replay).toBe(true)
  })

  it('maps no_wallet, 404, 422, network', async () => {
    const { createShoppingPurchase } = await import('./shopping')
    const body = { item_ids: ['a'], amount: 1, client_token: 'tok' }
    reply(409, { detail: 'no_wallet' })
    await expect(createShoppingPurchase(body)).rejects.toMatchObject({ code: 'no_wallet' })
    reply(404, { detail: 'x' })
    await expect(createShoppingPurchase(body)).rejects.toMatchObject({ code: 'not_found' })
    reply(422, { detail: [] })
    await expect(createShoppingPurchase(body)).rejects.toMatchObject({ code: 'invalid' })
    fetchMock.mockRejectedValueOnce(new TypeError('x'))
    await expect(createShoppingPurchase(body)).rejects.toMatchObject({ code: 'network' })
  })
})

describe('pending purchase api (m3-4)', () => {
  const pending = {
    id: 'p1', status: 'awaiting', method: 'receipt', expires_at: '2026-10-31T11:00:00Z',
    purchase_id: null, amount: null,
  }

  it('creates pending: body, 201 = new, 200 = same token again', async () => {
    const { createPendingPurchase } = await import('./shopping')
    reply(201, pending)
    const body = { item_ids: ['a', 'b'], method: 'receipt' as const, client_token: 'tok' }
    expect(await createPendingPurchase(body)).toEqual({ pending, created: true })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/shopping/purchases/pending')
    expect(fetchMock.mock.calls[0][1].method).toBe('POST')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(body)
    reply(200, pending)
    expect((await createPendingPurchase(body)).created).toBe(false)
  })

  it('maps receipt_disabled (409) and network on create', async () => {
    const { createPendingPurchase } = await import('./shopping')
    const body = { item_ids: ['a'], method: 'receipt' as const }
    reply(409, { detail: 'receipt_disabled' })
    await expect(createPendingPurchase(body)).rejects.toMatchObject({ code: 'receipt_disabled' })
    fetchMock.mockRejectedValueOnce(new TypeError('x'))
    await expect(createPendingPurchase(body)).rejects.toMatchObject({ code: 'network' })
  })

  it('maps 409 token_conflict on create', async () => {
    const { createPendingPurchase } = await import('./shopping')
    reply(409, { detail: 'token_conflict' })
    await expect(
      createPendingPurchase({ item_ids: ['a'], method: 'voice', client_token: 't' }),
    ).rejects.toMatchObject({ code: 'token_conflict' })
  })

  it('reads pending by id; foreign/missing is not_found', async () => {
    const { fetchPendingPurchase } = await import('./shopping')
    reply(200, pending)
    expect(await fetchPendingPurchase('p1')).toEqual(pending)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/shopping/purchases/pending/p1')
    reply(404, { detail: 'x' })
    await expect(fetchPendingPurchase('p1')).rejects.toMatchObject({ code: 'not_found' })
  })

  it('manual amount: POST amount, 201 new / 200 replay, 410 purchase_closed, 409 no_wallet', async () => {
    const { submitPendingAmount } = await import('./shopping')
    const purchase = { id: 'p1' }
    reply(201, purchase)
    expect(await submitPendingAmount('p1', 412000)).toEqual({ purchase, replay: false })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/shopping/purchases/pending/p1/amount')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ amount: 412000 })
    reply(200, purchase)
    expect((await submitPendingAmount('p1', 412000)).replay).toBe(true)
    reply(410, { detail: 'purchase_closed' })
    await expect(submitPendingAmount('p1', 1)).rejects.toMatchObject({ code: 'purchase_closed' })
    reply(409, { detail: 'no_wallet' })
    await expect(submitPendingAmount('p1', 1)).rejects.toMatchObject({ code: 'no_wallet' })
  })

  it('reads a finished purchase result by id', async () => {
    const { fetchPurchase } = await import('./shopping')
    reply(200, { id: 'p1', amount: 5 })
    expect(await fetchPurchase('p1')).toEqual({ id: 'p1', amount: 5 })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/shopping/purchases/p1')
  })
})

