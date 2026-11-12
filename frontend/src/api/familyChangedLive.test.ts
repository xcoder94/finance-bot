import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// The normal path: the form is open, the person joins/leaves a family in the bot, comes back and
// taps Save. The server answers 403/404 (ids of another budget), not 409. The client must ask
// /me once, and if the family or the role changed, behave as for family_changed.
vi.mock('./authHeader', () => ({ getAuthHeader: () => 'Bearer t' }))

import { createExpenseTransaction, updateExpenseTransaction } from './transactions'
import { createGoal } from './goals'
import { createExpenseCategory } from './categories'
import { createWallet } from './wallets'
import { FamilyChangedError, refreshPersonOnReturn } from './familyChanged'
import { useAuthStore } from '../store/authStore'
import { useDataCacheStore } from '../store/dataCacheStore'

const fetchMock = vi.fn()

function me(family: string, role: string) {
  return {
    id: 'u1', telegram_id: 1, family_budget_id: family, role, first_name: 'A', username: null,
    language: 'ru', budget_name: 'B', member_count: 2, default_wallet_id: null,
  }
}

function server(opts: { writeStatus: number; meNow: ReturnType<typeof me>; body?: unknown }) {
  fetchMock.mockImplementation(async (url: string, init?: { method?: string }) => {
    if (url === '/api/v1/me' && (!init || !init.method)) {
      return { ok: true, status: 200, json: async () => opts.meNow }
    }
    return { ok: false, status: opts.writeStatus, json: async () => opts.body ?? { detail: 'x' } }
  })
}
const meCalls = () => fetchMock.mock.calls.filter(([url]) => url === '/api/v1/me').length
const expense = { transaction_date: 'd', amount: 5, wallet_id: 'w', expense_category_id: 'c' }

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  useAuthStore.setState({
    status: 'ready',
    errorType: null,
    user: { id: 'u1', familyBudgetId: 'old-family', role: 'owner' } as never,
  })
  useDataCacheStore.setState({ entries: { 'reference:old-family:wallets': { data: [], fetchedAt: Date.now() } } })
})
afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

const writes: Array<[string, number, () => Promise<unknown>]> = [
  ['expense 404', 404, () => createExpenseTransaction(expense)],
  ['edit 404', 404, () => updateExpenseTransaction('t', { amount: 5 } as never)],
  ['wallet 403', 403, () => createWallet({ name: 'x', currency: 'UZS' })],
  ['category 403', 403, () => createExpenseCategory({ name: 'x', parent_id: 'p' })],
  ['goal 403', 403, () => createGoal({ wallet_id: 'w', target_amount: 5 })],
]

describe('403/404 on a write after the family changed', () => {
  it.each(writes)('%s: family changed -> family error, person reread once, old cache dropped', async (_n, status, write) => {
    server({ writeStatus: status, meNow: me('new-family', 'owner') })
    await expect(write()).rejects.toBeInstanceOf(FamilyChangedError)
    expect(meCalls()).toBe(1)
    expect(useAuthStore.getState().user?.familyBudgetId).toBe('new-family')
    expect(useDataCacheStore.getState().entries['reference:old-family:wallets']).toBeUndefined()
  })

  it('role changed in the same family (owner -> member) is a family error too', async () => {
    server({ writeStatus: 403, meNow: me('old-family', 'member') })
    await expect(createGoal({ wallet_id: 'w', target_amount: 5 })).rejects.toBeInstanceOf(FamilyChangedError)
    expect(useAuthStore.getState().user?.role).toBe('member')
  })

  it('nothing changed: the usual error, no family error', async () => {
    server({ writeStatus: 404, meNow: me('old-family', 'owner') })
    const error = await createExpenseTransaction(expense).catch((e) => e)
    expect(error).toBeInstanceOf(Error)
    expect(error).not.toBeInstanceOf(FamilyChangedError)
    expect(meCalls()).toBe(1)
  })

  it('a 500 does not even ask /me', async () => {
    server({ writeStatus: 500, meNow: me('new-family', 'owner') })
    await createExpenseTransaction(expense).catch(() => undefined)
    expect(meCalls()).toBe(0)
  })

  it('a plain 409 (not family_changed) with the same person is the usual error and keeps its body readable', async () => {
    server({ writeStatus: 409, meNow: me('old-family', 'owner'), body: { detail: 'goal_already_exists' } })
    const error = await createGoal({ wallet_id: 'w', target_amount: 5 }).catch((e) => e)
    expect(error).not.toBeInstanceOf(FamilyChangedError)
    expect((error as { code?: string }).code).toBe('goal_already_exists')
  })
})

describe('coming back to the app', () => {
  it('rereads /me; a new family replaces the person and drops the old family cache', async () => {
    server({ writeStatus: 500, meNow: me('new-family', 'owner') })
    await refreshPersonOnReturn()
    expect(useAuthStore.getState().user?.familyBudgetId).toBe('new-family')
    expect(useDataCacheStore.getState().entries['reference:old-family:wallets']).toBeUndefined()
  })

  it('a new role is taken over too', async () => {
    server({ writeStatus: 500, meNow: me('old-family', 'member') })
    await refreshPersonOnReturn()
    expect(useAuthStore.getState().user?.role).toBe('member')
  })

  it('same person: the family data is still invalidated, the person stays as it was', async () => {
    server({ writeStatus: 500, meNow: me('old-family', 'owner') })
    const before = useDataCacheStore.getState().homeEpoch
    await refreshPersonOnReturn()
    expect(useDataCacheStore.getState().homeEpoch).toBeGreaterThan(before)
    expect(useAuthStore.getState().user?.familyBudgetId).toBe('old-family')
  })

  it('a failed /me does not break anything: the family data is invalidated', async () => {
    fetchMock.mockRejectedValue(new Error('offline'))
    const before = useDataCacheStore.getState().homeEpoch
    await refreshPersonOnReturn()
    expect(useDataCacheStore.getState().homeEpoch).toBeGreaterThan(before)
  })
})
