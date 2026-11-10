import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { AppRoot } from '@telegram-apps/telegram-ui'

import ru from '../../i18n/locales/ru.json'

vi.mock('../../i18n', () => ({ default: { language: 'ru', resolvedLanguage: 'ru' } }))

import type { HistoryItem, SummaryResponse } from '../../api/history'
import { HistoryTransactionList } from '../../components/history/HistoryTransactionList'
import { HistorySummaryLine } from './HistorySummaryLine'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})

const wrap = (node: React.ReactNode) =>
  renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <AppRoot>{node}</AppRoot>
    </I18nextProvider>,
  )

const summary = (rows: Array<[string, number, number]>) =>
  ({ by_currency: rows.map(([currency, income, expense]) => ({ currency, income, expense })) }) as unknown as SummaryResponse

describe('summary line', () => {
  it('shows UZS only when there are no USD operations', () => {
    const html = wrap(<HistorySummaryLine summary={summary([['UZS', 1000, 400], ['USD', 0, 0]])} />)
    expect(html).toContain('Доход')
    expect(html).toContain('Расход')
    expect(html).not.toContain('$')
  })
  it('shows both currencies when both present', () => {
    const html = wrap(<HistorySummaryLine summary={summary([['UZS', 1000, 400], ['USD', 5, 2]])} />)
    expect(html).toContain('$')
  })
})

describe('day groups', () => {
  const mk = (id: string, iso: string, amount: number) =>
    ({ id, type: 'expense', transaction_date: iso, amount, currency: 'UZS', wallet_id: 'w', wallet_name: 'W', comment: null }) as unknown as HistoryItem

  it('headers Сегодня, Вчера, date, with day expense total', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-10T07:00:00Z'))
    const html = wrap(
      <HistoryTransactionList
        groupByDay
        status="success"
        items={[mk('a', '2026-11-10T09:00:00+05:00', 1000), mk('b', '2026-11-10T08:00:00+05:00', 500), mk('c', '2026-11-09T10:00:00+05:00', 300), mk('d', '2026-11-08T10:00:00+05:00', 200)]}
        totalCount={4}
        onItemClick={() => {}}
        onRetry={() => {}}
      />,
    )
    vi.useRealTimers()
    expect(html).toContain('Сегодня')
    expect(html).toContain('Вчера')
    expect(html).toContain('8 ноября')
    expect(html).toMatch(/Сегодня[\s\S]*?−1[\s ]500/)
    expect(html.match(/history-day__title/g)).toHaveLength(3)
  })
})
