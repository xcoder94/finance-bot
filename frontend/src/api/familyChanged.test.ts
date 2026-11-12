import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// A write that crossed a family join/leave comes back 409 family_changed. The client must reread
// the person and the family data, keep the form, and say what happened (not "network error").
vi.mock('./authHeader', () => ({ getAuthHeader: () => 'Bearer t' }))

import { createGoal } from './goals'
import { createExpenseCategory } from './categories'
import { createShoppingPurchase } from './shopping'
import {
  createExpenseTransaction,
  createIncomeTransaction,
  createTransferTransaction,
} from './transactions'
import { createWallet } from './wallets'
import { FamilyChangedError, saveErrorKey } from './familyChanged'
import { useAuthStore } from '../store/authStore'
import { useDataCacheStore } from '../store/dataCacheStore'

const fetchMock = vi.fn()

const ME = {
  id: 'u1',
  telegram_id: 1,
  family_budget_id: 'new-family',
  role: 'owner',
  first_name: 'A',
  username: null,
  language: 'ru',
  budget_name: 'B',
  member_count: 1,
  default_wallet_id: null,
}

function mockServer() {
  fetchMock.mockImplementation(async (url: string, init?: { method?: string }) => {
    if (url === '/api/v1/me' && (!init || !init.method || init.method === 'GET')) {
      return { ok: true, status: 200, json: async () => ME }
    }
    return { ok: false, status: 409, json: async () => ({ detail: 'family_changed' }) }
  })
}

const meCalls = () => fetchMock.mock.calls.filter(([url]) => url === '/api/v1/me').length

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  mockServer()
  useAuthStore.setState({
    status: 'ready',
    errorType: null,
    user: { ...(({ id, ...r }) => ({ id, ...r }))({ id: 'u1' }), familyBudgetId: 'old-family' } as never,
  })
  useDataCacheStore.setState({ entries: { 'reference:old-family:wallets': { data: [], fetchedAt: Date.now() } } })
})
afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

const expense = { transaction_date: 'd', amount: 5, wallet_id: 'w', expense_category_id: 'c' }
const writes: Array<[string, () => Promise<unknown>]> = [
  ['expense', () => createExpenseTransaction(expense)],
  ['income', () => createIncomeTransaction({ transaction_date: 'd', amount: 5, wallet_id: 'w', income_category_id: 'c' })],
  ['transfer', () => createTransferTransaction({ transaction_date: 'd', wallet_id: 'a', to_wallet_id: 'b', amount: 5 })],
  ['wallet', () => createWallet({ name: 'x', currency: 'UZS' })],
  ['category', () => createExpenseCategory({ name: 'x', parent_id: 'p' })],
  ['goal', () => createGoal({ wallet_id: 'w', target_amount: 5 })],
  ['purchase', () => createShoppingPurchase({ item_ids: ['i'], amount: 5, client_token: 't' })],
]

describe('409 family_changed', () => {
  it.each(writes)('%s: rereads the person once, drops old family cache, throws the family error', async (_n, write) => {
    await expect(write()).rejects.toBeInstanceOf(FamilyChangedError)
    expect(meCalls()).toBe(1)
    expect(useAuthStore.getState().user?.familyBudgetId).toBe('new-family')
    expect(useDataCacheStore.getState().entries['reference:old-family:wallets']).toBeUndefined()
  })

  it('two writes failing together reread the person once (no duplicate reload)', async () => {
    await Promise.allSettled([createExpenseTransaction(expense), createExpenseTransaction(expense)])
    expect(meCalls()).toBe(1)
  })

  it('an ordinary failure is not a family change', async () => {
    fetchMock.mockImplementation(async () => ({ ok: false, status: 500, json: async () => ({}) }))
    await expect(createExpenseTransaction(expense)).rejects.not.toBeInstanceOf(FamilyChangedError)
    expect(meCalls()).toBe(0)
  })

  it('the explanation is the family message only for this error', async () => {
    const error = await createExpenseTransaction(expense).catch((e) => e)
    expect(saveErrorKey(error, 'addTransaction.submitError')).toBe('familyChanged.message')
    expect(saveErrorKey(new Error('x'), 'addTransaction.submitError')).toBe('addTransaction.submitError')
  })
})
