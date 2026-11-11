import { beforeEach, describe, expect, it, vi } from 'vitest'

// «Назад» from History opened through a chart category: the person returns to the chart, with the
// browser's Back and with Telegram's Back button, and no dead history entry is left behind.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('../../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../../i18n', () => ({ default: { language: 'ru' } }))

const navigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useNavigate: () => navigate,
  useLocation: () => ({ pathname: '/analytics', search: '', hash: '', state: null }),
}))

let telegramBack: { open: boolean; handler: () => void } = { open: false, handler: () => undefined }
vi.mock('../../components/nativeBackButtonContext', () => ({
  useNativeBackButtonOverlay: (open: boolean, handler: () => void) => {
    telegramBack = { open, handler }
  },
}))
vi.mock('../../components/PeriodFilterControls', () => ({ PeriodFilterControls: () => null }))
vi.mock('../../store/dataCacheStore', () => ({
  useDataCacheStore: (select: (s: unknown) => unknown) => select({ homeEpoch: 0 }),
}))
vi.mock('../../store/analyticsShellStore', () => ({
  createDefaultAnalyticsShellState: () => ({
    activeTab: 'charts',
    periodTab: 'month',
    selectedMonth: { year: 2026, month: 10 },
    rangeFrom: '',
    rangeTo: '',
    rangeFromTouched: false,
    rangeToTouched: false,
    currency: 'UZS',
    drillParent: null,
    historyCategoryFilter: null,
  }),
  useAnalyticsShellStore: (select: (s: unknown) => unknown) => select({ shell: null, setShell: () => undefined }),
}))
vi.mock('../../contexts/AnalyticsContext', () => ({ AnalyticsProvider: () => null }))
vi.mock('./AnalyticsChartsTab', () => ({ AnalyticsChartsTab: () => null }))
vi.mock('./AnalyticsHistoryTab', () => ({ AnalyticsHistoryTab: () => null }))

const windowListeners: Record<string, Array<() => void>> = {}
vi.stubGlobal('window', {
  addEventListener: (name: string, cb: () => void) => (windowListeners[name] ??= []).push(cb),
  removeEventListener: (name: string, cb: () => void) => {
    windowListeners[name] = (windowListeners[name] ?? []).filter((fn) => fn !== cb)
  },
})

const { mountHook } = await import('../../test/hookHarness')
const { findAll } = await import('../../test/elementTree')
const { AnalyticsLayout } = await import('./AnalyticsLayout')
const { AnalyticsProvider } = await import('../../contexts/AnalyticsContext')

type Ctx = {
  activeTab: string
  historyCategoryFilter: unknown
  setActiveTab: (tab: string) => void
  setHistoryCategoryFilter: (f: unknown) => void
}

const FOOD = { id: 'food', name: 'Еда', color: '#f00' }

async function openChart() {
  const h = await mountHook(() => AnalyticsLayout())
  const ctx = () => (findAll(h.result(), (el) => el.type === AnalyticsProvider)[0].props.value as Ctx)
  return { h, ctx }
}

/** The chart category tap: the filter is set and History is shown. */
async function tapCategory(h: Awaited<ReturnType<typeof openChart>>['h'], ctx: () => Ctx) {
  ctx().setHistoryCategoryFilter(FOOD)
  ctx().setActiveTab('history')
  h.rerender()
  await h.settle(3)
}

beforeEach(() => {
  navigate.mockClear()
  for (const name of Object.keys(windowListeners)) delete windowListeners[name]
  telegramBack = { open: false, handler: () => undefined }
})

describe('Back from the filtered History', () => {
  it('opening the filtered History adds one browser history entry', async () => {
    const { h, ctx } = await openChart()
    expect(navigate).not.toHaveBeenCalled()
    await tapCategory(h, ctx)
    expect(ctx().activeTab).toBe('history')
    expect(navigate).toHaveBeenCalledTimes(1)
    expect(navigate).toHaveBeenCalledWith('/analytics', { state: null })
  })

  it('the browser Back returns to the chart and clears the filter', async () => {
    const { h, ctx } = await openChart()
    await tapCategory(h, ctx)
    windowListeners.popstate?.forEach((cb) => cb())
    h.rerender()
    await h.settle(3)
    expect(ctx().activeTab).toBe('charts')
    expect(ctx().historyCategoryFilter).toBeNull()
    // the browser already went back by itself: no second step back
    expect(navigate).not.toHaveBeenCalledWith(-1)
  })

  it('Telegram Back goes back through the browser history and does not leave the app', async () => {
    const { h, ctx } = await openChart()
    await tapCategory(h, ctx)
    expect(telegramBack.open).toBe(true)
    telegramBack.handler()
    expect(navigate).toHaveBeenCalledWith(-1)
  })

  it('on the chart Telegram Back is not taken over', async () => {
    await openChart()
    expect(telegramBack.open).toBe(false)
  })

  it('leaving the filtered History by the tab removes the extra entry again', async () => {
    const { h, ctx } = await openChart()
    await tapCategory(h, ctx)
    ctx().setActiveTab('charts')
    h.rerender()
    await h.settle(3)
    expect(navigate).toHaveBeenLastCalledWith(-1)
  })
})
