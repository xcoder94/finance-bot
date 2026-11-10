import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'

import ru from '../i18n/locales/ru.json'

const mockUser = {
  id: 'u', telegramId: 1, familyBudgetId: 'fam', role: 'owner', firstName: 'Ali',
  username: null, language: 'ru', budgetName: 'Семья', memberCount: 1,
  defaultWalletId: null, eveningReminderEnabled: false, weeklyDigestEnabled: false,
}
vi.mock('../store/authStore', () => ({
  useAuthStore: (selector: (s: { user: typeof mockUser }) => unknown) =>
    selector({ user: mockUser }),
}))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('@tma.js/sdk-react', () => ({ useRawInitData: () => undefined }))

import { HomePage } from './HomePage'
import { forgetHomeMonth, rememberHomeMonth } from '../utils/homeMonthMemory'
import { useDataCacheStore } from '../store/dataCacheStore'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})

function renderHome(): string {
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </I18nextProvider>,
  )
}

function seed(history: { total_count: number }) {
  const set = useDataCacheStore.getState().setEntry
  set('home:fam:summary:2026-10', {
    by_currency: [{ currency: 'UZS', income: 12_400_000, expense: 8_950_000, net_change: 0 }],
  })
  // all-time wallet balance deliberately different from income - expense: the card must ignore it (owner decision 13)
  set('home:fam:balances', { balances: [{ currency: 'UZS', balance: -13_550_000 }] })
  set('home:fam:personal-summary:2026-10', { currencies_with_wallets: [], by_currency: [] })
  set('home:fam:personal-balances', { currencies_with_wallets: [], balances: [] })
  set('home:fam:recent:2026-10', { items: [], ...history })
  const wallet = (currency: string, balance: number, is_personal = false) => ({
    id: currency + balance, name: 'w', currency, translation_key: null, transaction_count: 0,
    is_personal, has_active_goal: false, balance,
  })
  set('reference:fam:wallets', [wallet('UZS', 10_000_000), wallet('UZS', 2_400_000), wallet('USD', 999), wallet('UZS', 5, true)])
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-18T12:00:00+05:00'))
  useDataCacheStore.setState({ entries: {} })
})
afterEach(() => vi.useRealTimers())

describe('HomePage', () => {
  it('first load without cache shows the skeleton with two plate placeholders', () => {
    const html = renderHome()
    expect(html).toContain('home-skeleton')
    expect(html).toContain('class="home-left__plate home-left__plate--skeleton"')
    expect(html).not.toContain('Можно тратить в день')
  })

  it('empty month shows the empty card with the bot hint', () => {
    seed({ total_count: 0 })
    const html = renderHome()
    expect(html).toContain('В октябре операций нет')
    expect(html).toContain('Напишите боту «такси 32000»')
  })

  it('month with data: heading, balance card and quick actions present, no fail box', () => {
    seed({ total_count: 0 })
    const html = renderHome()
    expect(html).toContain('Октябрь 2026')
    expect(html).toContain('Итог месяца · окт')
    expect(html).toContain('3 450 000 сум')
    expect(html).not.toContain('home-fail')
  })

  it('balance card is income minus expense of the month, not the wallet balance (B1)', () => {
    seed({ total_count: 0 })
    const html = renderHome()
    const card = html.slice(html.indexOf('home-figures-card__balance'))
    expect(card.slice(0, 120)).toContain('3 450 000 сум')
    expect(html).not.toContain('13 550 000')
    expect(html).not.toContain('UZS')
  })

  it('U5.2: wallets line shows the shared UZS wallets sum and is the only button to /wallets', () => {
    seed({ total_count: 0 })
    const html = renderHome().replace(/\u00a0/g, ' ')
    expect(html).toContain('Деньги в кошельках: 12 400 000 сум')
    const m = html.match(/<button[^>]*home-figures-card__wallets[^>]*>/)
    expect(m).not.toBeNull()
    expect(m![0]).toContain('type="button"')
    expect(html).not.toMatch(/<button[^>]*class="home-figures-card /)
    const card = html.slice(html.indexOf('home-figures-card'))
    expect(card).toContain('Итог месяца · окт')
    expect(card).toContain('3 450 000 сум')
    expect(card).toContain('Доход')
    expect(card).toContain('Расход')
  })

  it('keeps the month picked before opening /wallets when Home mounts again', () => {
    seed({ total_count: 0 })
    rememberHomeMonth({ year: 2026, month: 8 })
    try {
      expect(renderHome()).toContain('Август 2026')
    } finally {
      forgetHomeMonth()
    }
    expect(renderHome()).toContain('Октябрь 2026')
  })

  it('U5.1: the word Остаток is gone from Home, Итог месяца is there', () => {
    seed({ total_count: 0 })
    const html = renderHome()
    expect(html).not.toContain('Остаток')
    expect(html).not.toContain('Осталось до конца месяца')
    expect(html).toContain('Итог месяца')
  })

  it('U5.3: expenses without income show the hint; with income it is hidden', () => {
    seed({ total_count: 0 })
    useDataCacheStore.getState().setEntry('home:fam:summary:2026-10', {
      by_currency: [{ currency: 'UZS', income: 0, expense: 500_000, net_change: 0 }],
    })
    expect(renderHome()).toContain('Запишите доход — например, «зарплата 8 млн»')
    useDataCacheStore.getState().setEntry('home:fam:summary:2026-10', {
      by_currency: [{ currency: 'UZS', income: 8_000_000, expense: 500_000, net_change: 0 }],
    })
    expect(renderHome()).not.toContain('Запишите доход')
  })

  it('U5.3b: no hint for an empty month', () => {
    seed({ total_count: 0 })
    useDataCacheStore.getState().setEntry('home:fam:summary:2026-10', { by_currency: [] })
    expect(renderHome()).not.toContain('Запишите доход')
  })

  it('U5: the 3-month trend block is removed', () => {
    seed({ total_count: 0 })
    const html = renderHome()
    expect(html).not.toContain('home-trend')
    expect(html).not.toContain('3 месяца')
  })

  it('U5.4: empty Home has the Добавить расход button', () => {
    seed({ total_count: 0 })
    const html = renderHome()
    const empty = html.slice(html.indexOf('home-empty-card'))
    expect(empty).toContain('home-empty-card__cta')
    expect(empty).toContain('Добавить расход')
  })
})
