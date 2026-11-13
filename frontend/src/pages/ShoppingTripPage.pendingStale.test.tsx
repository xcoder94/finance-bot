import { beforeEach, describe, expect, it, vi } from 'vitest'

// Voice / receipt-photo purchase while an item is already gone (server 404): the list is re-read, the
// gone item drops, the person is told the list changed (not 'failed, retry' forever). Same as the manual way.
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
  loads: 0,
  load: (async () => undefined) as () => Promise<void>,
  afterLoad: null as null | Array<{ id: string; name: string; created_at: string }>,
  created: 0,
}))
vi.mock('../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { familyBudgetId: world.scope, defaultWalletId: null, receiptPhotoEnabled: false } }),
}))
vi.mock('../store/shoppingStore', () => ({
  useShoppingStore: (select: (s: unknown) => unknown) =>
    select({
      items: world.items,
      load: world.load,
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
vi.mock('../api/shopping', async () => {
  const actual = await vi.importActual<typeof import('../api/shopping')>('../api/shopping')
  return {
    ...actual,
    createPendingPurchase: async () => {
      world.created += 1
      throw new actual.ShoppingApiError('not_found', 404)
    },
    fetchPendingPurchase: vi.fn(),
    cancelPendingPurchaseApi: vi.fn(),
    fetchPurchase: vi.fn(),
    submitPendingAmount: vi.fn(),
  }
})
vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => undefined, removeItem: () => undefined })
vi.stubGlobal('sessionStorage', { getItem: () => null, setItem: () => undefined, removeItem: () => undefined })
vi.stubGlobal('window', { history: { state: null } })

world.load = async () => {
  world.loads += 1
  if (world.afterLoad) world.items = world.afterLoad
}

const { mountHook } = await import('../test/hookHarness')
const { findAll, textOf } = await import('../test/elementTree')
const { ShoppingTripPage } = await import('./ShoppingTripPage')
const { ShoppingTripView } = await import('../components/shopping/ShoppingTripView')
const { ShoppingAmountView } = await import('../components/shopping/ShoppingAmountView')

beforeEach(() => {
  world.items = [{ id: 'a', name: 'Молоко', created_at: '' }, { id: 'b', name: 'Хлеб', created_at: '' }]
  world.afterLoad = null
  world.loads = 0
  world.created = 0
})

describe.each(['voice', 'receipt'] as const)('Shopping trip: %s purchase, an item is gone (404)', (method) => {
  it('re-reads the list, drops the gone item, says the list changed', async () => {
    world.afterLoad = [{ id: 'b', name: 'Хлеб', created_at: '' }]
    const h = await mountHook(() => ShoppingTripPage(), 10)
    const one = (type: unknown) => findAll(h.result(), (e) => e.type === type)[0] as { props: Record<string, any> } | undefined
    one(ShoppingTripView)!.props.onToggle('a')
    one(ShoppingTripView)!.props.onToggle('b')
    await h.settle(2)
    one(ShoppingTripView)!.props.onFinish()
    await h.settle(2)
    const loadsBefore = world.loads
    one(ShoppingAmountView)!.props.onBotMethod(method)
    await h.settle(6)

    expect(world.created).toBeGreaterThan(0)
    expect(world.loads).toBeGreaterThan(loadsBefore)
    const sheet = one(ShoppingAmountView)!
    expect(sheet.props.staleList).toBe(true)
    expect(sheet.props.failed).toBe(false)
    expect(sheet.props.count).toBe(1)
  })
})

describe('Shopping trip: the "list changed" notice on the list screen', () => {
  it('is not drawn behind the open sheet (the sheet has its own), and is on the list once the sheet is gone', async () => {
    world.items = [{ id: 'a', name: 'Молоко', created_at: '' }, { id: 'b', name: 'Хлеб', created_at: '' }]
    world.afterLoad = [{ id: 'b', name: 'Хлеб', created_at: '' }]
    const h = await mountHook(() => ShoppingTripPage(), 10)
    const one = (type: unknown) => findAll(h.result(), (e) => e.type === type)[0] as { props: Record<string, any> } | undefined
    one(ShoppingTripView)!.props.onToggle('a')
    one(ShoppingTripView)!.props.onToggle('b')
    await h.settle(2)
    one(ShoppingTripView)!.props.onFinish()
    await h.settle(2)
    one(ShoppingAmountView)!.props.onBotMethod('voice')
    await h.settle(6)
    // the sheet is open and says it; the list under it stays clean
    expect(one(ShoppingAmountView)!.props.staleList).toBe(true)
    expect(textOf(h.result())).not.toContain('LIST CHANGED')
  })

  it('every ticked item gone: back on the list, the notice is there, inside a padded block', async () => {
    world.items = [{ id: 'a', name: 'Молоко', created_at: '' }]
    world.afterLoad = null
    const h = await mountHook(() => ShoppingTripPage(), 10)
    const one = (type: unknown) => findAll(h.result(), (e) => e.type === type)[0] as { props: Record<string, any> } | undefined
    one(ShoppingTripView)!.props.onToggle('a')
    await h.settle(2)
    one(ShoppingTripView)!.props.onFinish()
    await h.settle(2)
    world.afterLoad = []
    one(ShoppingAmountView)!.props.onBotMethod('voice')
    await h.settle(8)
    expect(one(ShoppingAmountView)).toBeUndefined()
    expect(textOf(h.result())).toContain('LIST CHANGED')
    const [notice] = findAll(h.result(), (e) => e.props?.role === 'alert') as Array<{ props: Record<string, any> }>
    expect(notice.props.className).toContain('shopping-trip__notice')
  })
})
