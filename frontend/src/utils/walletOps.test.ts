import { describe, expect, it, vi } from 'vitest'

vi.mock('../i18n', () => ({ default: { language: 'ru', resolvedLanguage: 'ru' } }))

import type { HistoryItem, HistoryResponse } from '../api/history'
import {
  createWalletOpsController,
  leaveIfWalletMissing,
  mergeUniqueById,
  resolveWalletScreen,
  walletOpAmount,
  walletOpsPath,
  type WalletOpsState,
} from './walletOps'

const item = (id: string, over: Partial<HistoryItem> = {}): HistoryItem => ({
  id,
  type: 'expense',
  transaction_date: '2026-11-03T10:00:00+05:00',
  amount: 1000,
  currency: 'UZS',
  wallet_id: 'A',
  wallet_name: 'A',
  wallet_translation_key: null,
  to_wallet_id: null,
  to_wallet_name: null,
  to_wallet_translation_key: null,
  to_amount: null,
  to_currency: null,
  income_category_name: null,
  income_category_translation_key: null,
  expense_category_name: null,
  expense_category_translation_key: null,
  expense_subcategory_name: null,
  expense_subcategory_translation_key: null,
  comment: null,
  created_by: null,
  ...over,
})
const clean = (s: string) => s.replace(/[  ]/g, ' ')

describe('walletOpAmount', () => {
  const transfer = item('t', { type: 'transfer', wallet_id: 'A', to_wallet_id: 'B', amount: 5000, to_amount: 5000, to_currency: 'UZS' })
  it('outgoing transfer: minus amount in own currency', () => {
    expect(clean(walletOpAmount(transfer, 'A'))).toBe('−5 000 сум')
  })
  it('incoming transfer: plus to_amount', () => {
    expect(clean(walletOpAmount(transfer, 'B'))).toBe('+5 000 сум')
  })
  it('exchange UZS -> USD', () => {
    const ex = item('x', { type: 'transfer', wallet_id: 'A', currency: 'UZS', amount: 125000, to_wallet_id: 'U', to_amount: 10, to_currency: 'USD' })
    expect(clean(walletOpAmount(ex, 'A'))).toBe('−125 000 сум')
    expect(clean(walletOpAmount(ex, 'U'))).toBe('+$10')
  })
  it('exchange USD -> UZS', () => {
    const ex = item('x', { type: 'transfer', wallet_id: 'U', currency: 'USD', amount: 10, to_wallet_id: 'A', to_amount: 125000, to_currency: 'UZS' })
    expect(clean(walletOpAmount(ex, 'U'))).toBe('−$10')
    expect(clean(walletOpAmount(ex, 'A'))).toBe('+125 000 сум')
  })
  it('income and expense keep the usual signs', () => {
    expect(clean(walletOpAmount(item('e'), 'A'))).toBe('−1 000 сум')
    expect(clean(walletOpAmount(item('i', { type: 'income' }), 'A'))).toBe('+1 000 сум')
  })
})

describe('paths and merging', () => {
  it('walletOpsPath', () => expect(walletOpsPath('abc')).toBe('/wallets/abc'))
  it('mergeUniqueById drops repeated ids and keeps order', () => {
    const merged = mergeUniqueById([item('1'), item('2')], [item('2'), item('3')])
    expect(merged.map((i) => i.id)).toEqual(['1', '2', '3'])
  })
})

describe('wallet route resolution', () => {
  const wallet = { id: 'A' }
  it('known wallet', () => expect(resolveWalletScreen([wallet], true, 'A')).toEqual({ kind: 'ready', wallet }))
  it('unknown id on fresh list is missing', () => expect(resolveWalletScreen([wallet], true, 'zzz')).toEqual({ kind: 'missing' }))
  it('unknown id on a stale list is still loading, not missing', () =>
    expect(resolveWalletScreen([wallet], false, 'zzz')).toEqual({ kind: 'loading' }))
  it('no list yet: loading', () => expect(resolveWalletScreen(null, false, 'A')).toEqual({ kind: 'loading' }))
  it('missing wallet replaces the route with /wallets', () => {
    const navigate = vi.fn()
    leaveIfWalletMissing({ kind: 'missing' }, navigate)
    expect(navigate).toHaveBeenCalledWith('/wallets', { replace: true })
    navigate.mockClear()
    leaveIfWalletMissing({ kind: 'loading' }, navigate)
    leaveIfWalletMissing({ kind: 'ready', wallet }, navigate)
    expect(navigate).not.toHaveBeenCalled()
  })
})

describe('createWalletOpsController', () => {
  const range = { dateFrom: 'F1', dateTo: 'T1' }
  const range2 = { dateFrom: 'F2', dateTo: 'T2' }
  const page = (ids: string[], total: number): HistoryResponse => ({ items: ids.map((i) => item(i)), total_count: total })
  const setup = (fetchPage: (r: typeof range, limit: number, offset: number) => Promise<HistoryResponse>) => {
    const states: WalletOpsState[] = []
    const ctl = createWalletOpsController({ fetchPage, onChange: (s) => states.push(s) })
    return { ctl, states, last: () => states[states.length - 1] }
  }

  it('loads the first page of the period: loading then success', async () => {
    const fetchPage = vi.fn().mockResolvedValue(page(['1', '2'], 2))
    const { ctl, states, last } = setup(fetchPage)
    await ctl.setPeriod(range)
    expect(states[0].status).toBe('loading')
    expect(fetchPage).toHaveBeenCalledWith(range, 50, 0)
    expect(last()).toMatchObject({ status: 'success', total: 2 })
    expect(last().items.map((i) => i.id)).toEqual(['1', '2'])
  })

  it('changing the period clears the list and loads the new one', async () => {
    const fetchPage = vi.fn().mockResolvedValueOnce(page(['1'], 1)).mockResolvedValueOnce(page(['9'], 1))
    const { ctl, states, last } = setup(fetchPage)
    await ctl.setPeriod(range)
    const before = states.length
    const p = ctl.setPeriod(range2)
    expect(states[before]).toMatchObject({ status: 'loading', items: [] })
    await p
    expect(fetchPage).toHaveBeenLastCalledWith(range2, 50, 0)
    expect(last().items.map((i) => i.id)).toEqual(['9'])
  })

  it('a slow answer for the old period is ignored', async () => {
    let resolveOld!: (r: HistoryResponse) => void
    const fetchPage = vi
      .fn()
      .mockReturnValueOnce(new Promise<HistoryResponse>((r) => (resolveOld = r)))
      .mockResolvedValueOnce(page(['9'], 1))
    const { ctl, last } = setup(fetchPage)
    const old = ctl.setPeriod(range)
    await ctl.setPeriod(range2)
    resolveOld(page(['1'], 1))
    await old
    expect(last().items.map((i) => i.id)).toEqual(['9'])
  })

  it('load more appends without duplicates, offset = loaded count', async () => {
    const fetchPage = vi.fn().mockResolvedValueOnce(page(['1', '2'], 4)).mockResolvedValueOnce(page(['2', '3', '4'], 4))
    const { ctl, last } = setup(fetchPage)
    await ctl.setPeriod(range)
    await ctl.loadMore()
    expect(fetchPage).toHaveBeenLastCalledWith(range, 50, 2)
    expect(last().items.map((i) => i.id)).toEqual(['1', '2', '3', '4'])
    expect(last().loadingMore).toBe(false)
  })

  it('load more failure keeps the list and flags the error', async () => {
    const fetchPage = vi.fn().mockResolvedValueOnce(page(['1'], 3)).mockRejectedValueOnce(new Error('x'))
    const { ctl, last } = setup(fetchPage)
    await ctl.setPeriod(range)
    await ctl.loadMore()
    expect(last()).toMatchObject({ status: 'success', loadMoreError: true })
    expect(last().items).toHaveLength(1)
  })

  it('refresh re-requests the loaded amount, keeps period and list while waiting', async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(['1', '2'], 2))
      .mockResolvedValueOnce(page(['1', '2', '3'], 3))
    const { ctl, states, last } = setup(fetchPage)
    await ctl.setPeriod(range)
    const before = states.length
    const p = ctl.refresh()
    expect(states.length).toBe(before) // no flicker to loading
    await p
    expect(fetchPage).toHaveBeenLastCalledWith(range, 50, 0)
    expect(last().items.map((i) => i.id)).toEqual(['1', '2', '3'])
  })

  it('refresh asks for as many rows as are already shown (max 500)', async () => {
    const ids = Array.from({ length: 120 }, (_, i) => String(i))
    const fetchPage = vi.fn().mockResolvedValue(page(ids, 120))
    const { ctl } = setup(fetchPage)
    await ctl.setPeriod(range)
    await ctl.refresh()
    expect(fetchPage).toHaveBeenLastCalledWith(range, 120, 0)
  })

  it('refresh failure keeps what is on screen', async () => {
    const fetchPage = vi.fn().mockResolvedValueOnce(page(['1'], 1)).mockRejectedValueOnce(new Error('x'))
    const { ctl, last } = setup(fetchPage)
    await ctl.setPeriod(range)
    await ctl.refresh()
    expect(last()).toMatchObject({ status: 'success' })
    expect(last().items).toHaveLength(1)
  })

  it('first load failure gives error, retry loads again', async () => {
    const fetchPage = vi.fn().mockRejectedValueOnce(new Error('x')).mockResolvedValueOnce(page(['1'], 1))
    const { ctl, last } = setup(fetchPage)
    await ctl.setPeriod(range)
    expect(last().status).toBe('error')
    await ctl.retry()
    expect(last().status).toBe('success')
  })

  it('dispose stops later updates', async () => {
    let resolve!: (r: HistoryResponse) => void
    const fetchPage = vi.fn().mockReturnValue(new Promise<HistoryResponse>((r) => (resolve = r)))
    const { ctl, states } = setup(fetchPage)
    const p = ctl.setPeriod(range)
    ctl.dispose()
    const n = states.length
    resolve(page(['1'], 1))
    await p
    expect(states.length).toBe(n)
  })
})

describe('a record added between pages', () => {
  const range = { dateFrom: 'F1', dateTo: 'T1' }
  const page = (ids: string[], total: number): HistoryResponse => ({ items: ids.map((i) => item(i)), total_count: total })
  it('load more after an insert shows no duplicate and loses nothing', async () => {
    const ids = (from: number, to: number) => Array.from({ length: to - from }, (_, i) => String(from + i))
    // before: 1..60 (newest first). A new row "0" arrives; page 2 (offset 50) now starts at old row 50.
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(ids(1, 51), 60))
      .mockResolvedValueOnce(page(['50', ...ids(51, 61)], 61))
    const states: WalletOpsState[] = []
    const ctl = createWalletOpsController({ fetchPage, onChange: (s) => states.push(s) })
    await ctl.setPeriod(range)
    await ctl.loadMore()
    const shown = states[states.length - 1].items.map((x) => x.id)
    expect(new Set(shown).size).toBe(shown.length)
    expect(shown).toEqual(ids(1, 61))
  })
})

describe('dev-fix12 r3: stuck states', () => {
  const range = { dateFrom: 'F1', dateTo: 'T1' }
  const ids = (from: number, to: number) => Array.from({ length: to - from }, (_, i) => String(from + i))
  const page = (list: string[], total: number): HistoryResponse => ({ items: list.map((i) => item(i)), total_count: total })
  const setup = (fetchPage: (r: typeof range, limit: number, offset: number) => Promise<HistoryResponse>) => {
    const states: WalletOpsState[] = []
    const ctl = createWalletOpsController({ fetchPage, onChange: (s) => states.push(s) })
    return { ctl, last: () => states[states.length - 1] }
  }

  it('B: a record added elsewhere does not freeze "load more" (60 -> 61, offset hits a known row)', async () => {
    // screen has rows 1..60 of 60; row "0" appears on top: offset 60 returns old row 60, already shown
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(ids(1, 51), 60))
      .mockResolvedValueOnce(page(ids(51, 61), 61)) // the insert is noticed only here: total 61, 60 shown
      .mockResolvedValueOnce(page(['60'], 61)) // load more at offset 60: nothing new
      .mockResolvedValueOnce(page(['0', ...ids(1, 61)], 61)) // follow-up full reload
    const { ctl, last } = setup(fetchPage)
    await ctl.setPeriod(range)
    await ctl.loadMore()
    await ctl.loadMore()
    expect(last().items.map((x) => x.id)).toEqual(['0', ...ids(1, 61)])
    expect(last().total).toBe(61)
    expect(last().loadingMore).toBe(false)
  })

  it('B: if the follow-up reload fails, the list stays and the error flag is set', async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(['1', '2'], 3))
      .mockResolvedValueOnce(page(['2'], 3))
      .mockRejectedValueOnce(new Error('x'))
    const { ctl, last } = setup(fetchPage)
    await ctl.setPeriod(range)
    await ctl.loadMore()
    expect(last()).toMatchObject({ status: 'success', loadingMore: false, loadMoreError: true })
    expect(last().items).toHaveLength(2)
  })

  it('V: refresh failing while the first load is pending gives the error state with retry', async () => {
    let resolveFirst!: (r: HistoryResponse) => void
    const fetchPage = vi
      .fn()
      .mockReturnValueOnce(new Promise<HistoryResponse>((r) => (resolveFirst = r)))
      .mockRejectedValueOnce(new Error('x'))
      .mockResolvedValueOnce(page(['1'], 1))
    const { ctl, last } = setup(fetchPage)
    const first = ctl.setPeriod(range)
    await ctl.refresh()
    resolveFirst(page(['9'], 1))
    await first
    expect(last().status).toBe('error')
    await ctl.retry()
    expect(last()).toMatchObject({ status: 'success' })
  })
})
