import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/shopping', async () => {
  const actual = await vi.importActual<typeof import('../api/shopping')>('../api/shopping')
  return {
    ...actual,
    listShoppingItems: vi.fn(),
    addShoppingItem: vi.fn(),
    renameShoppingItem: vi.fn(),
    deleteShoppingItem: vi.fn(),
    createShoppingPurchase: vi.fn(),
  }
})

import * as api from '../api/shopping'
import { ShoppingApiError } from '../api/shopping'
import { FamilyChangedError } from '../api/familyChanged'
import { useShoppingStore } from './shoppingStore'

const m = vi.mocked(api)
const mk = (id: string, name: string) => ({ id, name, created_at: '2026-10-31T10:00:00Z' })
const s = () => useShoppingStore.getState()

beforeEach(() => {
  vi.resetAllMocks()
  useShoppingStore.setState({ items: [], status: 'idle', scope: '' })
})

describe('shoppingStore', () => {
  it('load: loading -> ready, keeps server order', async () => {
    m.listShoppingItems.mockResolvedValue([mk('1', 'Молоко'), mk('2', 'Хлеб')])
    const p = s().load('fam')
    expect(s().status).toBe('loading')
    await p
    expect(s().status).toBe('ready')
    expect(s().items.map((i) => i.name)).toEqual(['Молоко', 'Хлеб'])
  })

  it('load failure -> error; silent reload failure keeps shown items', async () => {
    m.listShoppingItems.mockRejectedValue(new ShoppingApiError('network'))
    await s().load('fam')
    expect(s().status).toBe('error')
    useShoppingStore.setState({ items: [mk('1', 'Молоко')], status: 'ready' })
    await s().load('fam', { silent: true })
    expect(s().status).toBe('ready')
    expect(s().items).toHaveLength(1)
  })

  it('a different family never sees the previous list', async () => {
    useShoppingStore.setState({ items: [mk('1', 'Чужое')], status: 'ready', scope: 'other' })
    m.listShoppingItems.mockResolvedValue([])
    const p = s().load('fam')
    expect(s().items).toEqual([])
    expect(s().status).toBe('loading')
    await p
  })

  it('stale response of an older load is dropped', async () => {
    let resolveFirst: (v: api.ShoppingItem[]) => void = () => {}
    m.listShoppingItems.mockImplementationOnce(() => new Promise((r) => { resolveFirst = r }))
    m.listShoppingItems.mockResolvedValueOnce([mk('2', 'Новое')])
    const first = s().load('fam')
    await s().load('fam', { silent: true })
    resolveFirst([mk('1', 'Старое')])
    await first
    expect(s().items.map((i) => i.name)).toEqual(['Новое'])
  })

  it('add: appended at the end; duplicate (client, case-insensitive) makes no request', async () => {
    useShoppingStore.setState({ items: [mk('1', 'Молоко')], status: 'ready', scope: 'fam' })
    m.addShoppingItem.mockResolvedValue({ item: mk('2', 'Хлеб'), created: true })
    expect(await s().add('  Хлеб ')).toBe('added')
    expect(m.addShoppingItem).toHaveBeenCalledWith('Хлеб')
    expect(s().items.map((i) => i.name)).toEqual(['Молоко', 'Хлеб'])
    expect(await s().add('МОЛОКО')).toBe('duplicate')
    expect(m.addShoppingItem).toHaveBeenCalledTimes(1)
  })

  it('add: empty -> invalid without request; server says existing -> duplicate (and the item is shown)', async () => {
    useShoppingStore.setState({ items: [], status: 'ready', scope: 'fam' })
    expect(await s().add('   ')).toBe('invalid')
    expect(m.addShoppingItem).not.toHaveBeenCalled()
    m.addShoppingItem.mockResolvedValue({ item: mk('9', 'Сыр'), created: false })
    expect(await s().add('Сыр')).toBe('duplicate')
    expect(s().items.map((i) => i.name)).toEqual(['Сыр'])
  })

  it('add: server returns an existing item missing locally (added by a family member) -> shown, still duplicate', async () => {
    useShoppingStore.setState({ items: [mk('1', 'Молоко')], status: 'ready', scope: 'fam' })
    m.addShoppingItem.mockResolvedValue({ item: mk('9', 'Мука'), created: false })
    expect(await s().add('мука')).toBe('duplicate')
    expect(s().items.map((i) => i.name)).toEqual(['Молоко', 'Мука'])
    // already present by id: not doubled
    expect(await s().add('мука')).toBe('duplicate')
    expect(s().items).toHaveLength(2)
  })

  it('add: limit and failure', async () => {
    useShoppingStore.setState({ items: [], status: 'ready', scope: 'fam' })
    m.addShoppingItem.mockRejectedValueOnce(new ShoppingApiError('shopping_limit', 409))
    expect(await s().add('Сыр')).toBe('limit')
    m.addShoppingItem.mockRejectedValueOnce(new ShoppingApiError('network'))
    expect(await s().add('Сыр')).toBe('failed')
  })

  it('rename: replaces in place; duplicate; gone reloads', async () => {
    useShoppingStore.setState({ items: [mk('1', 'Молоко'), mk('2', 'Хлеб')], status: 'ready', scope: 'fam' })
    m.renameShoppingItem.mockResolvedValueOnce(mk('1', 'Кефир'))
    expect(await s().rename('1', ' Кефир ')).toBe('ok')
    expect(s().items.map((i) => i.name)).toEqual(['Кефир', 'Хлеб'])
    expect(await s().rename('1', 'хлеб')).toBe('duplicate')
    expect(await s().rename('1', ' ')).toBe('invalid')
    m.renameShoppingItem.mockRejectedValueOnce(new ShoppingApiError('already_in_list', 409))
    expect(await s().rename('2', 'Рис')).toBe('duplicate')
    m.renameShoppingItem.mockRejectedValueOnce(new ShoppingApiError('not_found', 404))
    m.listShoppingItems.mockResolvedValue([mk('2', 'Хлеб')])
    expect(await s().rename('1', 'Рис')).toBe('gone')
    expect(s().items.map((i) => i.id)).toEqual(['2'])
  })

  it('rename to the same name just succeeds without request', async () => {
    useShoppingStore.setState({ items: [mk('1', 'Молоко')], status: 'ready', scope: 'fam' })
    expect(await s().rename('1', 'Молоко')).toBe('ok')
    expect(m.renameShoppingItem).not.toHaveBeenCalled()
  })

  it('remove: ok drops the row; 404 counts as removed; failure keeps the row', async () => {
    useShoppingStore.setState({ items: [mk('1', 'a'), mk('2', 'b'), mk('3', 'c')], status: 'ready', scope: 'fam' })
    m.deleteShoppingItem.mockResolvedValueOnce(undefined)
    expect(await s().remove('1')).toBe('ok')
    m.deleteShoppingItem.mockRejectedValueOnce(new ShoppingApiError('not_found', 404))
    expect(await s().remove('2')).toBe('ok')
    m.deleteShoppingItem.mockRejectedValueOnce(new ShoppingApiError('network'))
    expect(await s().remove('3')).toBe('failed')
    expect(s().items.map((i) => i.id)).toEqual(['3'])
  })
})

describe('shoppingStore.purchase', () => {
  const body = { item_ids: ['1'], amount: 5000, client_token: 'tok' }
  const done = {
    id: 'p', transaction_id: 't', items_recorded: 1, amount: 5000, currency: 'UZS',
    category_label: 'Еда', wallet_name: 'W', remaining: 10, items_left: 1,
  }

  it('409 family_changed: its own outcome, the list on screen is untouched', async () => {
    useShoppingStore.setState({ items: [mk('1', 'a')], status: 'ready', scope: 'fam' })
    m.createShoppingPurchase.mockRejectedValue(new FamilyChangedError())
    expect(await s().purchase(body)).toEqual({ kind: 'family_changed' })
    expect(s().items).toHaveLength(1)
  })

  it('404 not_found: its own outcome, the list is re-read from the server and shows what is left', async () => {
    useShoppingStore.setState({ items: [mk('1', 'a'), mk('2', 'b')], status: 'ready', scope: 'fam' })
    m.createShoppingPurchase.mockRejectedValue(new ShoppingApiError('not_found', 404))
    m.listShoppingItems.mockResolvedValue([mk('2', 'b')])
    expect(await s().purchase(body)).toEqual({ kind: 'stale' })
    expect(m.listShoppingItems).toHaveBeenCalledTimes(1)
    expect(s().items.map((i) => i.id)).toEqual(['2'])
  })

  it('ok: returns the purchase and removes bought ids from the shown list', async () => {
    useShoppingStore.setState({ items: [mk('1', 'a'), mk('2', 'b')], status: 'ready', scope: 'fam' })
    m.createShoppingPurchase.mockResolvedValue({ purchase: done, replay: false })
    const r = await s().purchase(body)
    expect(r).toEqual({ kind: 'ok', purchase: done, replay: false })
    expect(m.createShoppingPurchase).toHaveBeenCalledWith(body)
    expect(s().items.map((i) => i.id)).toEqual(['2'])
  })

  it('no_wallet / network failures keep the list and report the kind', async () => {
    useShoppingStore.setState({ items: [mk('1', 'a')], status: 'ready', scope: 'fam' })
    m.createShoppingPurchase.mockRejectedValueOnce(new ShoppingApiError('no_wallet', 409))
    expect(await s().purchase(body)).toEqual({ kind: 'no_wallet' })
    m.createShoppingPurchase.mockRejectedValueOnce(new ShoppingApiError('network'))
    expect(await s().purchase(body)).toEqual({ kind: 'failed', definite: false })
    expect(s().items).toHaveLength(1)
  })

  it('failed: only a 4xx answer is definite; network and 5xx are not', async () => {
    m.createShoppingPurchase.mockRejectedValueOnce(new ShoppingApiError('invalid', 422))
    expect(await s().purchase(body)).toEqual({ kind: 'failed', definite: true })
    m.createShoppingPurchase.mockRejectedValueOnce(new ShoppingApiError('unknown', 500))
    expect(await s().purchase(body)).toEqual({ kind: 'failed', definite: false })
    m.createShoppingPurchase.mockRejectedValueOnce(new ShoppingApiError('network'))
    expect(await s().purchase(body)).toEqual({ kind: 'failed', definite: false })
  })

  it('replay: reports it and re-reads the list instead of trusting the sent ids', async () => {
    useShoppingStore.setState({ items: [mk('1', 'a'), mk('2', 'b')], status: 'ready', scope: 'fam' })
    m.createShoppingPurchase.mockResolvedValue({ purchase: done, replay: true })
    m.listShoppingItems.mockResolvedValue([mk('2', 'b')])
    const r = await s().purchase({ ...body, item_ids: ['2'] })
    expect(r).toEqual({ kind: 'ok', purchase: done, replay: true })
    expect(m.listShoppingItems).toHaveBeenCalled()
    expect(s().items.map((i) => i.id)).toEqual(['2'])
  })
})
