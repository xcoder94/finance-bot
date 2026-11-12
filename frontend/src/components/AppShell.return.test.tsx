import { beforeEach, describe, expect, it, vi } from 'vitest'

// The person leaves the app and comes back: the data on screen is re-read. The shell is run with a
// tiny React runtime, the browser events are collected from document and fired by the test.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  const m = reactHarnessModule()
  return { ...m, lazy: () => () => null, Suspense: 'div', default: { ...m.default, lazy: () => () => null } }
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('react-router-dom', () => ({
  Navigate: () => null,
  NavLink: () => null,
  Outlet: () => null,
  Route: () => null,
  Routes: () => null,
  useLocation: () => ({ pathname: '/', search: '', hash: '', state: null }),
  useNavigationType: () => 'PUSH',
}))
vi.mock('@telegram-apps/telegram-ui', () => ({ Spinner: () => null, Tabbar: () => null }))
vi.mock('@tma.js/sdk-react', () => ({
  useSignal: () => 0,
  viewport: { height: {}, safeAreaInsetBottom: {}, contentSafeAreaInsetBottom: {}, isMounted: () => true },
  on: () => () => undefined,
}))
vi.mock('lucide-react', () => ({}))
vi.mock('../pages/AddExpensePage', () => ({ AddExpensePage: () => null }))
vi.mock('../pages/AddIncomePage', () => ({ AddIncomePage: () => null }))
vi.mock('../pages/AddTransferPage', () => ({ AddTransferPage: () => null }))
vi.mock('../pages/EditExpensePage', () => ({ EditExpensePage: () => null }))
vi.mock('../pages/EditIncomePage', () => ({ EditIncomePage: () => null }))
vi.mock('../pages/EditTransferPage', () => ({ EditTransferPage: () => null }))
vi.mock('../pages/GoalsPage', () => ({ GoalsPage: () => null }))
vi.mock('../pages/WalletDetailPage', () => ({ WalletDetailPage: () => null }))
vi.mock('../pages/WalletsPage', () => ({ WalletsPage: () => null }))
vi.mock('../pages/HomePage', () => ({ HomePage: () => null }))
vi.mock('../pages/ShoppingPage', () => ({ ShoppingPage: () => null }))
vi.mock('../pages/ShoppingTripPage', () => ({ ShoppingTripPage: () => null }))
vi.mock('../pages/SettingsPage', () => ({ SettingsPage: () => null }))
vi.mock('../pages/TransactionGonePage', () => ({ TransactionGonePage: () => null }))
vi.mock('../pages/settings/DefaultWalletSettingsPage', () => ({ DefaultWalletSettingsPage: () => null }))
vi.mock('../pages/settings/ExpenseCategoriesSettingsPage', () => ({ ExpenseCategoriesSettingsPage: () => null }))
vi.mock('../pages/settings/ExpenseSubcategoriesSettingsPage', () => ({ ExpenseSubcategoriesSettingsPage: () => null }))
vi.mock('../pages/settings/IncomeCategoriesSettingsPage', () => ({ IncomeCategoriesSettingsPage: () => null }))
vi.mock('../pages/settings/LanguageSettingsPage', () => ({ LanguageSettingsPage: () => null }))
vi.mock('../pages/settings/MembersSettingsPage', () => ({ MembersSettingsPage: () => null }))
vi.mock('../pages/settings/MemberDetailPage', () => ({ MemberDetailPage: () => null }))
vi.mock('../pages/settings/NotificationsSettingsShellPage', () => ({ NotificationsSettingsShellPage: () => null }))
vi.mock('../pages/admin/AdminPage', () => ({ AdminPage: () => null }))
vi.mock('../pages/settings/WalletsSettingsPage', () => ({ WalletsSettingsPage: () => null }))
vi.mock('./HistoryRedirect', () => ({ HistoryRedirect: () => null }))
vi.mock('./NativeBackButton', () => ({ NativeBackButtonProvider: () => null }))
vi.mock('./mainTabs', () => ({ MAIN_TABS: [] }))
vi.mock('./SuccessFlash', () => ({ SuccessFlash: () => null }))
vi.mock('../hooks/usePageDirection', () => ({ usePageDirection: () => 'forward' }))
vi.mock('../hooks/useShoppingStartup', () => ({ useShoppingStartup: () => undefined }))
vi.mock('../hooks/useTapHaptic', () => ({ useTapHaptic: () => undefined }))
vi.mock('../hooks/useTxDeepLink', () => ({ useTxDeepLink: () => 'idle' }))
const auth = vi.hoisted(() => ({
  user: { familyBudgetId: 'fam', role: 'owner' } as { familyBudgetId: string; role: string },
  setReady: vi.fn(),
  meNow: { family_budget_id: 'fam', role: 'owner' },
}))
vi.mock('../store/authStore', () => ({
  useAuthStore: Object.assign((select: (s: unknown) => unknown) => select({ user: auth.user }), {
    getState: () => ({ user: auth.user, setReady: auth.setReady }),
  }),
}))
vi.mock('../api/authHeader', () => ({ getAuthHeader: () => 'Bearer t' }))
vi.stubGlobal('fetch', async () => ({
  ok: true,
  status: 200,
  json: async () => ({ id: 'u', telegram_id: 1, first_name: 'A', username: null, language: 'ru', budget_name: 'B', member_count: 1, default_wallet_id: null, ...auth.meNow }),
}))
vi.mock('../store/chromeStore', () => ({
  useChromeStore: (select: (s: unknown) => unknown) => select({ tabbarHidden: false }),
}))

const listeners: Record<string, Array<() => void>> = {}
const documentStub = {
  visibilityState: 'visible',
  addEventListener: (name: string, cb: () => void) => (listeners[name] ??= []).push(cb),
  removeEventListener: (name: string, cb: () => void) => {
    listeners[name] = (listeners[name] ?? []).filter((fn) => fn !== cb)
  },
  documentElement: { style: { setProperty: () => undefined } },
}
vi.stubGlobal('document', documentStub)
vi.stubGlobal('window', { addEventListener: () => undefined, removeEventListener: () => undefined })

const { mountHook } = await import('../test/hookHarness')
const { AppShell } = await import('./AppShell')
const { useDataCacheStore } = await import('../store/dataCacheStore')

const THROTTLE_PLUS = 31_000

describe('return to the app', () => {
  beforeEach(() => {
    for (const name of Object.keys(listeners)) delete listeners[name]
  })

  it('re-reads the family data when the person comes back after a while', async () => {
    let clock = 1_000_000
    vi.spyOn(Date, 'now').mockImplementation(() => clock)
    await mountHook(() => AppShell())
    const before = useDataCacheStore.getState().homeEpoch

    clock += THROTTLE_PLUS
    documentStub.visibilityState = 'visible'
    listeners.visibilitychange?.forEach((cb) => cb())
    await new Promise((r) => setTimeout(r, 0))

    expect(useDataCacheStore.getState().homeEpoch).toBe(before + 1)
  })

  it('takes the new family and role when the person moved while the app was in the background', async () => {
    let clock = 9_000_000
    vi.spyOn(Date, 'now').mockImplementation(() => clock)
    await mountHook(() => AppShell())
    auth.meNow = { family_budget_id: 'other', role: 'member' }
    auth.setReady.mockClear()

    clock += THROTTLE_PLUS
    documentStub.visibilityState = 'visible'
    listeners.visibilitychange?.forEach((cb) => cb())
    await new Promise((r) => setTimeout(r, 0))

    expect(auth.setReady).toHaveBeenCalledTimes(1)
    expect(auth.setReady.mock.calls[0][0]).toMatchObject({ familyBudgetId: 'other', role: 'member' })
    auth.meNow = { family_budget_id: 'fam', role: 'owner' }
  })

  it('does not re-read while the app is hidden, and not twice for one quick return', async () => {
    let clock = 5_000_000
    vi.spyOn(Date, 'now').mockImplementation(() => clock)
    await mountHook(() => AppShell())
    const before = useDataCacheStore.getState().homeEpoch

    clock += THROTTLE_PLUS
    documentStub.visibilityState = 'hidden'
    listeners.visibilitychange?.forEach((cb) => cb())
    expect(useDataCacheStore.getState().homeEpoch).toBe(before)

    documentStub.visibilityState = 'visible'
    listeners.visibilitychange?.forEach((cb) => cb())
    clock += 1_000
    listeners.visibilitychange?.forEach((cb) => cb())
    await new Promise((r) => setTimeout(r, 0))
    expect(useDataCacheStore.getState().homeEpoch).toBe(before + 1)
  })
})
