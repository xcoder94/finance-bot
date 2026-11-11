import i18next from 'i18next'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ru from '../../i18n/locales/ru.json'

// Analytics -> Charts as the person reads it: the comparison line under the headline, and what is
// on screen while the data is re-read after coming back to the app. The tab is run with a tiny
// React runtime; the API is a fake whose answers the test releases one by one.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('@telegram-apps/telegram-ui', () => ({ Text: 'span', Spinner: () => null }))
vi.mock('../../components/analytics/CategoryDonutChart', () => ({ CategoryDonutChart: () => null }))
vi.mock('../../components/analytics/TrendChart', () => ({ TrendChart: () => null }))
vi.mock('../../components/analytics/WeekdayBarChart', () => ({ WeekdayBarChart: () => null }))
vi.mock('../../components/BlockError', () => ({ BlockError: () => null }))

const ruI18n = i18next.createInstance()
await ruI18n.init({ lng: 'ru', resources: { ru: { translation: ru } }, interpolation: { escapeValue: false } })
vi.mock('../../i18n/t', () => ({
  t: (key: string, options?: Record<string, unknown>) => ruI18n.t(key, options) as string,
}))
vi.mock('../../i18n', () => ({ default: ruI18n }))

type Call = { name: string; resolve: (v: unknown) => void }
const calls: Call[] = []
const request = (name: string) =>
  new Promise((resolve) => {
    calls.push({ name, resolve })
  })
vi.mock('../../api/analytics', () => ({
  fetchExpenseComparison: () => request('comparison'),
  fetchExpensesByCategory: () => request('expenses'),
  fetchIncomeByCategory: () => request('income'),
  fetchExpensesBySubcategory: () => request('subcategories'),
  fetchSummaryForRange: () => request('summary'),
  fetchTrend: () => request('trend'),
}))
vi.mock('../../api/home', () => ({ fetchPersonalSummary: async () => ({ by_currency: [] }) }))
vi.mock('../../api/transactions', () => ({ fetchExpenseCategories: async () => [] }))
vi.mock('../../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) => select({ user: { familyBudgetId: 'fam' } }),
}))
vi.mock('../../store/dataCacheStore', () => ({
  getCachedExpenseCategories: async () => [{ id: 'food', name: 'Еда', translation_key: null, parent_id: null, color_index: 0 }],
  getCachedPersonalSummary: async () => ({ by_currency: [] }),
}))

const context: Record<string, unknown> = {}
vi.mock('../../contexts/AnalyticsContext', () => ({ useAnalyticsContext: () => context }))

const { mountHook } = await import('../../test/hookHarness')
const { textOf } = await import('../../test/elementTree')
const { AnalyticsChartsTab } = await import('./AnalyticsChartsTab')

function setPeriod(from: string, to: string, epoch = 0) {
  context.range = { dateFrom: from, dateTo: to }
  context.rangeKey = `${from}|${to}`
  context.fetchKey = `${from}|${to}|UZS|${epoch}`
}

/** Releases every request waiting right now with the usual answers of a month with spending. */
async function answerAll(h: { settle: (n?: number) => Promise<void> }, comparison: Record<string, unknown>) {
  const answers: Record<string, unknown> = {
    comparison,
    expenses: [{ category_id: 'food', category_name: 'Еда', category_translation_key: null, color_index: 0, amount: 120_000 }],
    income: [],
    summary: { by_currency: [{ currency: 'UZS', income: 0, expense: 120_000, transfer_net: 0, net_change: 0, average_daily_expense: 0, most_expensive_weekday: null, most_expensive_weekday_average: 0 }], day_of_week_expense: { UZS: [0, 0, 0, 0, 0, 0, 0] }, day_of_week_income: {} },
    trend: [],
    subcategories: [],
  }
  const waiting = calls.splice(0)
  waiting.forEach((c) => c.resolve(answers[c.name]))
  await h.settle(8)
}

beforeEach(() => {
  calls.length = 0
  Object.assign(context, {
    selectedMonth: { year: 2026, month: 10 },
    currency: 'UZS',
    rangeFetchEnabled: true,
    periodTab: 'month',
    drillParent: null,
    setDrillParent: vi.fn(),
    setHistoryCategoryFilter: vi.fn(),
    setActiveTab: vi.fn(),
  })
  setPeriod('2026-10-01T00:00:00+05:00', '2026-10-31T23:59:59.999+05:00')
})

const COMPARISON_SEPT = {
  total: 120_000,
  prev_total: 100_000,
  prev_date_from: '2026-09-01T00:00:00+05:00',
  prev_date_to: '2026-09-30T23:59:59.999+05:00',
}

describe('Analytics charts: comparison line', () => {
  it('for a 31-day range compared with a 30-day previous period it says 30 days, not 31', async () => {
    context.periodTab = 'range'
    const h = await mountHook(() => AnalyticsChartsTab())
    await answerAll(h, COMPARISON_SEPT)
    const screen = textOf(h.result())
    expect(screen).toContain('на 20% больше, чем за прошлые 30 дней')
    expect(screen).not.toContain('31')
  })

  it('for a calendar month it names the month before', async () => {
    const h = await mountHook(() => AnalyticsChartsTab())
    await answerAll(h, COMPARISON_SEPT)
    expect(textOf(h.result())).toContain('на 20% больше, чем в сентябре')
  })
})

describe('Analytics charts: coming back to the app', () => {
  it('the charts stay on screen while the same month is re-read (no skeleton)', async () => {
    const h = await mountHook(() => AnalyticsChartsTab())
    await answerAll(h, COMPARISON_SEPT)
    expect(textOf(h.result())).toContain('120')

    setPeriod('2026-10-01T00:00:00+05:00', '2026-10-31T23:59:59.999+05:00', 1) // the data epoch moved
    h.rerender()
    await h.settle(5)
    expect(calls.length).toBeGreaterThan(0) // the re-read really started and has not finished
    expect(textOf(h.result())).toContain('120')
  })

  it('another month shows the loading placeholder, not the old month\'s figures', async () => {
    const h = await mountHook(() => AnalyticsChartsTab())
    await answerAll(h, COMPARISON_SEPT)

    setPeriod('2026-09-01T00:00:00+05:00', '2026-09-30T23:59:59.999+05:00')
    context.selectedMonth = { year: 2026, month: 9 }
    h.rerender()
    await h.settle(5)
    expect(textOf(h.result())).not.toContain('120')
  })
})
