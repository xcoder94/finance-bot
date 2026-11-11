import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// The totals line at the top of Analytics -> History: what the person sees while the period
// changes and while a refresh fails. The tab is run with a tiny React runtime; the API is a fake
// whose answers the test releases one by one.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('../../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }))

type Deferred = { from: string; resolve: (v: unknown) => void; reject: () => void }
const summaryCalls: Deferred[] = []
vi.mock('../../api/history', () => ({
  fetchSummaryForRange: (from: string) =>
    new Promise((resolve, reject) => {
      summaryCalls.push({ from, resolve, reject: () => reject(new Error('network')) })
    }),
  fetchHistoryPage: async () => ({ items: [], total_count: 0 }),
}))
vi.mock('../../api/transactions', () => ({ fetchWallets: async () => [] }))

let homeEpoch = 0
vi.mock('../../store/dataCacheStore', () => ({
  useDataCacheStore: (select: (s: unknown) => unknown) => select({ homeEpoch }),
}))

const context: Record<string, unknown> = {}
vi.mock('../../contexts/AnalyticsContext', () => ({ useAnalyticsContext: () => context }))

const { mountHook } = await import('../../test/hookHarness')
const { findAll } = await import('../../test/elementTree')
const { AnalyticsHistoryTab } = await import('./AnalyticsHistoryTab')
const { HistorySummaryLine } = await import('./HistorySummaryLine')

function monthRange(from: string, to: string) {
  return { dateFrom: from, dateTo: to }
}
function summaryOf(income: number, expense: number) {
  return { by_currency: [{ currency: 'UZS', income, expense }] }
}
function setPeriod(from: string, to: string) {
  context.range = monthRange(from, to)
  context.rangeKey = `${from}|${to}`
}

/** The totals line exactly as it is drawn. */
function totalsOnScreen(tree: unknown): string {
  const [line] = findAll(tree, (el) => el.type === HistorySummaryLine)
  return renderToStaticMarkup((HistorySummaryLine as (p: unknown) => React.ReactElement)(line.props))
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

beforeEach(() => {
  summaryCalls.length = 0
  homeEpoch = 0
  Object.assign(context, {
    rangeFetchEnabled: true,
    historyCategoryFilter: null,
    setHistoryCategoryFilter: vi.fn(),
    setActiveTab: vi.fn(),
    drillParent: null,
    activeTab: 'history',
    periodTab: 'month',
    selectedMonth: { year: 2026, month: 10 },
    rangeFrom: '',
    rangeTo: '',
    rangeFromTouched: false,
    rangeToTouched: false,
    currency: 'UZS',
  })
  setPeriod('2026-10-01', '2026-10-31')
})

describe('Analytics -> History totals line', () => {
  it('shows the totals of the month on screen', async () => {
    const h = await mountHook(() => AnalyticsHistoryTab())
    summaryCalls[0].resolve(summaryOf(100_000, 40_000))
    await h.settle(5)
    expect(totalsOnScreen(h.result())).toContain('100')
  })

  it('switching to another month does not keep the old month\'s totals while the new ones load', async () => {
    const h = await mountHook(() => AnalyticsHistoryTab())
    summaryCalls[0].resolve(summaryOf(100_000, 40_000))
    await h.settle(5)
    expect(totalsOnScreen(h.result())).toContain('100')

    setPeriod('2026-11-01', '2026-11-30')
    h.rerender()
    await h.settle(5)
    expect(summaryCalls).toHaveLength(2)
    expect(totalsOnScreen(h.result())).toBe('')

    summaryCalls[1].resolve(summaryOf(7_000, 3_000))
    await h.settle(5)
    const shown = totalsOnScreen(h.result())
    expect(shown).toContain('7')
    expect(shown).not.toContain('100')
  })

  it('a failed refresh of the same month leaves the totals on screen', async () => {
    const h = await mountHook(() => AnalyticsHistoryTab())
    summaryCalls[0].resolve(summaryOf(100_000, 40_000))
    await h.settle(5)

    homeEpoch = 1 // the person came back to the app: data is re-read
    h.rerender()
    await h.settle(5)
    expect(summaryCalls).toHaveLength(2)
    summaryCalls[1].reject()
    await h.settle(5)
    expect(totalsOnScreen(h.result())).toContain('100')
  })

  it('a failed load of a new month shows no totals at all rather than the old month\'s', async () => {
    const h = await mountHook(() => AnalyticsHistoryTab())
    summaryCalls[0].resolve(summaryOf(100_000, 40_000))
    await h.settle(5)

    setPeriod('2026-11-01', '2026-11-30')
    h.rerender()
    await h.settle(5)
    summaryCalls[1].reject()
    await h.settle(5)
    expect(totalsOnScreen(h.result())).toBe('')
  })
})
