import { describe, expect, it, vi } from 'vitest'

// Stale list: see below. (copy of the family-changed harness)
// The person is in the middle of a trip (two items ticked, amount sheet open) when they join
// another family. The list becomes the new family's. The sheet must not stay open over an empty
// list with a button that does nothing: back to the list, ticks dropped, the reason said.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => (key === 'shopping.staleList' ? 'LIST CHANGED' : key) }),
}))
vi.mock('../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ search: '' }),
}))
vi.mock('../components/nativeBackButtonContext', () => ({ useNativeBackButtonOverlay: () => undefined }))
vi.mock('../telegram/closeMiniApp', () => ({ closeMiniApp: vi.fn() }))
vi.mock('../telegram/haptic', () => ({ haptic: { error: vi.fn() } }))
vi.mock('../store/chromeStore', () => ({ useHideTabbar: () => undefined }))
vi.mock('../components/FailBox', () => ({ FailBox: () => null }))

const world = vi.hoisted(() => ({
  scope: 'old',
  items: [
    { id: 'a', name: 'Молоко', created_at: '' },
    { id: 'b', name: 'Хлеб', created_at: '' },
  ] as Array<{ id: string; name: string; created_at: string }>,
  sent: [] as unknown[],
}))
vi.mock('../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { familyBudgetId: world.scope, defaultWalletId: null, receiptPhotoEnabled: false } }),
}))
vi.mock('../store/shoppingStore', () => ({
  useShoppingStore: (select: (s: unknown) => unknown) =>
    select({
      items: world.items,
      load: async () => undefined,
      purchase: async (body: unknown) => {
        world.sent.push(body)
        world.items = [{ id: 'b', name: 'Хлеб', created_at: '' }]
        return { kind: 'stale' }
      },
    }),
}))
vi.mock('../store/dataCacheStore', () => ({
  getCachedExpenseCategories: async () => [],
  getCachedWallets: async () => [],
  invalidateHomeData: vi.fn(),
  invalidateWalletData: vi.fn(),
}))
vi.mock('../api/transactions', () => ({ fetchExpenseCategories: async () => [], fetchWallets: async () => [] }))
vi.mock('../api/shopping', () => ({
  createPendingPurchase: vi.fn(),
  fetchPendingPurchase: vi.fn(),
  cancelPendingPurchaseApi: vi.fn(),
  fetchPurchase: vi.fn(),
  submitPendingAmount: vi.fn(),
}))
vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => undefined, removeItem: () => undefined })
vi.stubGlobal('sessionStorage', { getItem: () => null, setItem: () => undefined, removeItem: () => undefined })
vi.stubGlobal('window', { history: { state: null } })

const { mountHook } = await import('../test/hookHarness')
const { findAll, textOf } = await import('../test/elementTree')
const { ShoppingTripPage } = await import('./ShoppingTripPage')
const { ShoppingTripView } = await import('../components/shopping/ShoppingTripView')
const { ShoppingAmountView } = await import('../components/shopping/ShoppingAmountView')

describe('Shopping trip: the server says an item is gone (404)', () => {
  it('keeps the amount, drops the gone item, shows the message above the footer, does not retry', async () => {
    const h = await mountHook(() => ShoppingTripPage(), 10)
    const one = (type: unknown) => findAll(h.result(), (e) => e.type === type)[0] as { props: Record<string, any> } | undefined

    one(ShoppingTripView)!.props.onToggle('a')
    one(ShoppingTripView)!.props.onToggle('b')
    await h.settle(2)
    one(ShoppingTripView)!.props.onFinish()
    await h.settle(2)
    one(ShoppingAmountView)!.props.onAmount('12000')
    await h.settle(2)
    one(ShoppingAmountView)!.props.onSubmit()
    await h.settle(4)

    expect(world.sent).toHaveLength(1)
    const sheet = one(ShoppingAmountView)!
    expect(sheet.props.amount).toBe('12000')
    expect(sheet.props.count).toBe(1)
    expect(sheet.props.staleList).toBe(true)
    expect(textOf(h.result())).not.toContain('shopping.recordFailed')
    expect(textOf(h.result())).not.toContain('shopping.resultNoneTitle')
  })
})
