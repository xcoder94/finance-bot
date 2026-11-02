import { create } from 'zustand'

import type {
  ExpenseCategory,
  IncomeCategory,
  TransactionResponse,
  Wallet,
} from '../api/transactions'
import type {
  HistoryResponse,
  PersonalSummaryResponse,
  PersonalWalletBalancesResponse,
  SummaryResponse,
  WalletBalancesResponse,
} from '../api/home'
import type { TrendEntry } from '../api/analytics'

type CacheEntry = {
  data: unknown
  fetchedAt: number
}

type DataCacheState = {
  entries: Record<string, CacheEntry>
  /** Bumped on every home invalidation, so a Home that stays mounted under a form re-fetches. */
  homeEpoch: number
  setEntry: (key: string, data: unknown) => void
  removeKey: (key: string) => void
  removePrefix: (prefix: string) => void
}

const HOME_TTL_MS = 30_000
const REFERENCE_TTL_MS = 5 * 60_000
const TRANSACTION_TTL_MS = 2 * 60_000

const inFlight = new Map<string, { promise: Promise<unknown>; generation: number }>()

/**
 * Bumped on every invalidation. A request started before a change must neither be shared with
 * a request made after it nor write its (already outdated) answer into the cache.
 */
let generation = 0

/**
 * Last value ever fetched per key. Survives TTL expiry and invalidation, so the home screen can
 * render the previous figures instantly (stale-while-revalidate) instead of a skeleton and then
 * jumping when the fresh data lands.
 */
const lastKnown = new Map<string, unknown>()

function readLastKnown<T>(key: string): T | null {
  return lastKnown.has(key) ? (lastKnown.get(key) as T) : null
}

function readFreshOrStale<T>(key: string, ttlMs: number): T | null {
  return readFresh<T>(key, ttlMs) ?? readLastKnown<T>(key)
}

export const useDataCacheStore = create<DataCacheState>((set) => ({
  entries: {},
  homeEpoch: 0,
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
  if (pending && pending.generation === generation) {
    return pending.promise as Promise<T>
  }

  const startedAt = generation
  const request: Promise<T> = fetcher()
    .then((data) => {
      if (startedAt === generation) {
        lastKnown.set(key, data)
        useDataCacheStore.getState().setEntry(key, data)
      }
      return data
    })
    .finally(() => {
      if (inFlight.get(key)?.promise === request) {
        inFlight.delete(key)
      }
    })

  inFlight.set(key, { promise: request, generation: startedAt })
  return request
}

const summaryKey = (familyId: string, year: number, month: number) =>
  `home:${familyId}:summary:${year}-${month}`
const balancesKey = (familyId: string) => `home:${familyId}:balances`
const personalSummaryKey = (familyId: string, year: number, month: number) =>
  `home:${familyId}:personal-summary:${year}-${month}`
const personalBalancesKey = (familyId: string) => `home:${familyId}:personal-balances`
const recentHistoryKey = (familyId: string, year: number, month: number) =>
  `home:${familyId}:recent:${year}-${month}`
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
  return readFreshOrStale(summaryKey(familyId, year, month), HOME_TTL_MS)
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

export function peekPersonalSummary(
  familyId: string,
  year: number,
  month: number,
): PersonalSummaryResponse | null {
  return readFreshOrStale(personalSummaryKey(familyId, year, month), HOME_TTL_MS)
}

export function getCachedPersonalSummary(
  familyId: string,
  year: number,
  month: number,
  fetcher: () => Promise<PersonalSummaryResponse>,
  force = false,
): Promise<PersonalSummaryResponse> {
  return fetchCached(
    personalSummaryKey(familyId, year, month),
    HOME_TTL_MS,
    fetcher,
    force,
  )
}

export function peekPersonalWalletBalances(
  familyId: string,
): PersonalWalletBalancesResponse | null {
  return readFreshOrStale(personalBalancesKey(familyId), HOME_TTL_MS)
}

export function getCachedPersonalWalletBalances(
  familyId: string,
  fetcher: () => Promise<PersonalWalletBalancesResponse>,
  force = false,
): Promise<PersonalWalletBalancesResponse> {
  return fetchCached(personalBalancesKey(familyId), HOME_TTL_MS, fetcher, force)
}

export function peekRecentHistory(
  familyId: string,
  year: number,
  month: number,
): HistoryResponse | null {
  return readFreshOrStale(recentHistoryKey(familyId, year, month), HOME_TTL_MS)
}

export function getCachedRecentHistory(
  familyId: string,
  year: number,
  month: number,
  fetcher: () => Promise<HistoryResponse>,
  force = false,
): Promise<HistoryResponse> {
  return fetchCached(recentHistoryKey(familyId, year, month), HOME_TTL_MS, fetcher, force)
}

const trendKey = (familyId: string, endMonth: string) => `home:${familyId}:trend:${endMonth}`

export function peekTrend(familyId: string, endMonth: string): TrendEntry[] | null {
  return readFreshOrStale(trendKey(familyId, endMonth), HOME_TTL_MS)
}

export function getCachedTrend(
  familyId: string,
  endMonth: string,
  fetcher: () => Promise<TrendEntry[]>,
  force = false,
): Promise<TrendEntry[]> {
  return fetchCached(trendKey(familyId, endMonth), HOME_TTL_MS, fetcher, force)
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

/**
 * One family's data is a web: a transaction changes category/wallet counters and balances, a
 * rename changes names shown inside cached transactions and home lists, and so on. Every change
 * therefore drops everything cached for the family (stale-while-revalidate keeps home figures
 * on screen meanwhile). Never invalidate "just the screen you are on".
 */
export function invalidateFamilyData(familyId: string): void {
  generation += 1
  const store = useDataCacheStore.getState()
  store.removePrefix(`home:${familyId}:`)
  store.removePrefix(`reference:${familyId}:`)
  store.removePrefix(`transaction:${familyId}:`)
  useDataCacheStore.setState((state) => ({ homeEpoch: state.homeEpoch + 1 }))
}

export function invalidateHomeData(familyId: string): void {
  invalidateFamilyData(familyId)
}

export function invalidateWalletData(familyId: string): void {
  invalidateFamilyData(familyId)
}

export function invalidateIncomeCategoryData(familyId: string): void {
  invalidateFamilyData(familyId)
}

export function invalidateExpenseCategoryData(familyId: string): void {
  invalidateFamilyData(familyId)
}

export function invalidateTransactionData(familyId: string, _transactionId?: string): void {
  invalidateFamilyData(familyId)
}
