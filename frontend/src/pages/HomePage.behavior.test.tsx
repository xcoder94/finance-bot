import { beforeEach, describe, expect, it, vi } from 'vitest'

// Home as the person uses it: the page is run with a tiny React runtime (no DOM), the API and the
// cache are fakes. We look at the requests it sends and at where «Все» takes the person.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))

vi.mock('../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))

const navigate = vi.fn()
vi.mock('react-router-dom', () => ({
  Link: 'a',
  useNavigate: () => navigate,
  useLocation: () => ({ pathname: '/', search: '', hash: '', state: null }),
}))

const walletsRequests = vi.fn()
let walletsCache: unknown[] | null = null
vi.mock('../api/transactions', () => ({
  fetchWallets: async () => {
    walletsRequests()
    return [{ id: 'w1', is_personal: false, currency: 'UZS', balance: '100' }]
  },
}))
vi.mock('../api/me', () => ({ fetchOnboarding: async () => ({ state: 'done' }) }))
vi.mock('../api/home', () => ({
  fetchRecentHistory: async () => ({ items: [], total_count: 0 }),
  fetchSummary: async () => ({ by_currency: [], day_of_week_expense: {}, day_of_week_income: {} }),
  fetchPersonalSummary: async () => ({ by_currency: [], currencies_with_wallets: [] }),
  fetchPersonalWalletBalances: async () => ({ currencies_with_wallets: [], balances: [] }),
}))
vi.mock('../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) => select({ user: { familyBudgetId: 'fam', role: 'owner', memberCount: 1, firstName: 'A' } }),
}))
vi.mock('../store/dataCacheStore', () => ({
  useDataCacheStore: (select: (s: unknown) => unknown) => select({ homeEpoch: 0 }),
  getCachedHomeSummary: (_f: string, _y: number, _m: number, load: () => Promise<unknown>) => load(),
  getCachedRecentHistory: (_f: string, _y: number, _m: number, load: () => Promise<unknown>) => load(),
  getCachedPersonalSummary: (_f: string, _y: number, _m: number, load: () => Promise<unknown>) => load(),
  getCachedPersonalWalletBalances: (_f: string, load: () => Promise<unknown>) => load(),
  // the real cache stores what was fetched and hands out the stored value: a new array per fetch
  getCachedWallets: async (_f: string, load: () => Promise<unknown[]>) => {
    walletsCache = [...(await load())]
    return walletsCache
  },
  peekHomeSummary: () => null,
  peekRecentHistory: () => null,
  peekPersonalSummary: () => null,
  peekPersonalWalletBalances: () => null,
  peekWallets: () => (walletsCache ? [...walletsCache] : null),
}))
vi.mock('../utils/onboardingDismiss', () => ({
  loadDismissedAt: async () => null,
  readDismissedAtSync: () => null,
  saveDismissedAt: async () => undefined,
  shouldShowOnboardingCard: () => false,
}))

vi.stubGlobal('window', { scrollTo: vi.fn(), scrollY: 0, addEventListener: vi.fn(), removeEventListener: vi.fn() })

const { mountHook } = await import('../test/hookHarness')
const { findButton } = await import('../test/elementTree')
const { HomePage } = await import('./HomePage')
const { useAnalyticsShellStore } = await import('../store/analyticsShellStore')

beforeEach(() => {
  navigate.mockClear()
  walletsRequests.mockClear()
  walletsCache = null
})

describe('Home page', () => {
  it('asks for the wallets once and stays quiet afterwards, even as the page re-renders', async () => {
    const h = await mountHook(() => HomePage(), 80)
    for (let i = 0; i < 15; i += 1) h.rerender()
    await h.settle(40)
    expect(walletsRequests).toHaveBeenCalledTimes(1)
  })

  it('«Все» opens the History tab of Analytics for the month shown on Home', async () => {
    useAnalyticsShellStore.getState().setShell(null as never)
    const h = await mountHook(() => HomePage())
    const seeAll = findButton(h.result(), 'home.seeAll')
    expect(seeAll).toBeDefined()
    ;(seeAll!.props.onClick as () => void)()
    expect(navigate).toHaveBeenCalledWith('/analytics', { state: { from: 'home' } })
    expect(useAnalyticsShellStore.getState().shell?.activeTab).toBe('history')
  })
})
