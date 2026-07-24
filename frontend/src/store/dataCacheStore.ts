import { create } from 'zustand'

import type {
  ExpenseCategory,
  IncomeCategory,
  TransactionResponse,
  Wallet,
} from '../api/transactions'
import type {
  HistoryResponse,
  SummaryResponse,
  WalletBalancesResponse,
} from '../api/home'

type CacheEntry = {
  data: unknown
  fetchedAt: number
}

type DataCacheState = {
  entries: Record<string, CacheEntry>
  setEntry: (key: string, data: unknown) => void
  removeKey: (key: string) => void
  removePrefix: (prefix: string) => void
}

const HOME_TTL_MS = 30_000
const REFERENCE_TTL_MS = 5 * 60_000
const TRANSACTION_TTL_MS = 2 * 60_000

const inFlight = new Map<string, Promise<unknown>>()

export const useDataCacheStore = create<DataCacheState>((set) => ({
  entries: {},
  setEntry: (key, data) =>
    set((state) => ({
      entries: {
        ...state.entries,
        [key]: { data, fetchedAt: Date.now() },
      },
    })),
  removeKey: (key) =>
    set((state) => {
      const entries = { ...state.entries }
      delete entries[key]
      return { entries }
    }),
  removePrefix: (prefix) =>
    set((state) => ({
      entries: Object.fromEntries(
        Object.entries(state.entries).filter(([key]) => !key.startsWith(prefix)),
      ),
    })),
}))

function readEntry<T>(key: string): CacheEntry & { data: T } | null {
  const entry = useDataCacheStore.getState().entries[key]
  return entry ? (entry as CacheEntry & { data: T }) : null
}

function readFresh<T>(key: string, ttlMs: number): T | null {
  const entry = readEntry<T>(key)
  return entry && Date.now() - entry.fetchedAt < ttlMs ? entry.data : null
}

async function fetchCached<T>(
  key: string,
  ttlMs: number,
  fetcher: () => Promise<T>,
  force = false,
): Promise<T> {
  if (!force) {
    const cached = readFresh<T>(key, ttlMs)
    if (cached !== null) {
      return cached
    }
  }

  const pending = inFlight.get(key)
  if (pending) {
    return pending as Promise<T>
  }

  const request = fetcher()
    .then((data) => {
      useDataCacheStore.getState().setEntry(key, data)
      return data
    })
    .finally(() => {
      inFlight.delete(key)
    })

  inFlight.set(key, request)
  return request
}

const summaryKey = (familyId: string, year: number, month: number) =>
  `home:${familyId}:summary:${year}-${month}`
const balancesKey = (familyId: string) => `home:${familyId}:balances`
const recentHistoryKey = (familyId: string) => `home:${familyId}:recent`
const walletsKey = (familyId: string) => `reference:${familyId}:wallets`
const incomeCategoriesKey = (familyId: string) => `reference:${familyId}:income-categories`
const expenseCategoriesKey = (familyId: string) => `reference:${familyId}:expense-categories`
const transactionKey = (familyId: string, transactionId: string) =>
  `transaction:${familyId}:${transactionId}`

export function peekHomeSummary(
  familyId: string,
  year: number,
  month: number,
): SummaryResponse | null {
  return readFresh(summaryKey(familyId, year, month), HOME_TTL_MS)
}

export function getCachedHomeSummary(
  familyId: string,
  year: number,
  month: number,
  fetcher: () => Promise<SummaryResponse>,
  force = false,
): Promise<SummaryResponse> {
  return fetchCached(summaryKey(familyId, year, month), HOME_TTL_MS, fetcher, force)
}

export function peekWalletBalances(familyId: string): WalletBalancesResponse | null {
  return readFresh(balancesKey(familyId), HOME_TTL_MS)
}

export function getCachedWalletBalances(
  familyId: string,
  fetcher: () => Promise<WalletBalancesResponse>,
  force = false,
): Promise<WalletBalancesResponse> {
  return fetchCached(balancesKey(familyId), HOME_TTL_MS, fetcher, force)
}

export function peekRecentHistory(familyId: string): HistoryResponse | null {
  return readFresh(recentHistoryKey(familyId), HOME_TTL_MS)
}

export function getCachedRecentHistory(
  familyId: string,
  fetcher: () => Promise<HistoryResponse>,
  force = false,
): Promise<HistoryResponse> {
  return fetchCached(recentHistoryKey(familyId), HOME_TTL_MS, fetcher, force)
}

export function peekWallets(familyId: string): Wallet[] | null {
  return readFresh(walletsKey(familyId), REFERENCE_TTL_MS)
}

export function getCachedWallets(
  familyId: string,
  fetcher: () => Promise<Wallet[]>,
  force = false,
): Promise<Wallet[]> {
  return fetchCached(walletsKey(familyId), REFERENCE_TTL_MS, fetcher, force)
}

export function peekIncomeCategories(familyId: string): IncomeCategory[] | null {
  return readFresh(incomeCategoriesKey(familyId), REFERENCE_TTL_MS)
}

export function getCachedIncomeCategories(
  familyId: string,
  fetcher: () => Promise<IncomeCategory[]>,
  force = false,
): Promise<IncomeCategory[]> {
  return fetchCached(incomeCategoriesKey(familyId), REFERENCE_TTL_MS, fetcher, force)
}

export function peekExpenseCategories(familyId: string): ExpenseCategory[] | null {
  return readFresh(expenseCategoriesKey(familyId), REFERENCE_TTL_MS)
}

export function getCachedExpenseCategories(
  familyId: string,
  fetcher: () => Promise<ExpenseCategory[]>,
  force = false,
): Promise<ExpenseCategory[]> {
  return fetchCached(expenseCategoriesKey(familyId), REFERENCE_TTL_MS, fetcher, force)
}

export function peekTransaction(
  familyId: string,
  transactionId: string,
): TransactionResponse | null {
  return readFresh(transactionKey(familyId, transactionId), TRANSACTION_TTL_MS)
}

export function getCachedTransaction(
  familyId: string,
  transactionId: string,
  fetcher: () => Promise<TransactionResponse>,
  force = false,
): Promise<TransactionResponse> {
  return fetchCached(
    transactionKey(familyId, transactionId),
    TRANSACTION_TTL_MS,
    fetcher,
    force,
  )
}

export function cacheTransaction(familyId: string, transaction: TransactionResponse): void {
  useDataCacheStore
    .getState()
    .setEntry(transactionKey(familyId, transaction.id), transaction)
}

export function cacheExpenseCategory(
  familyId: string,
  category: ExpenseCategory,
): void {
  const key = expenseCategoriesKey(familyId)
  const cached = readEntry<ExpenseCategory[]>(key)
  if (!cached || cached.data.some((item) => item.id === category.id)) {
    return
  }
  useDataCacheStore.getState().setEntry(key, [...cached.data, category])
}

export function invalidateHomeData(familyId: string): void {
  useDataCacheStore.getState().removePrefix(`home:${familyId}:`)
}

export function invalidateWalletData(familyId: string): void {
  useDataCacheStore.getState().removeKey(walletsKey(familyId))
  invalidateHomeData(familyId)
}

export function invalidateIncomeCategoryData(familyId: string): void {
  useDataCacheStore.getState().removeKey(incomeCategoriesKey(familyId))
}

export function invalidateExpenseCategoryData(familyId: string): void {
  useDataCacheStore.getState().removeKey(expenseCategoriesKey(familyId))
}

export function invalidateTransactionData(
  familyId: string,
  transactionId?: string,
): void {
  if (transactionId) {
    useDataCacheStore.getState().removeKey(transactionKey(familyId, transactionId))
  }
  invalidateHomeData(familyId)
}
