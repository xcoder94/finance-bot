import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'

// recharts needs a layout; the chart is not what these tests are about
vi.mock('recharts', () => {
  const Stub = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
  return { ResponsiveContainer: Stub, BarChart: Stub, Bar: Stub, CartesianGrid: Stub, XAxis: Stub, YAxis: Stub, Tooltip: Stub }
})

import adminRu from '../../i18n/locales/admin.ru.json'
import ru from '../../i18n/locales/ru.json'
import type { AdminOverview, AdminUser } from '../../api/admin'
import { initialUsersState, type AdminUsersState } from '../../utils/adminUsersState'
import { AdminTabs } from './AdminTabs'
import { AdminScreen } from './AdminScreen'
import { GrowthView } from './GrowthView'
import { UsersView } from './UsersView'
import { OpsView } from './OpsView'
import type { AdminUsage } from '../../api/admin'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru, admin: adminRu } },
  lng: 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})
const wrap = (node: React.ReactNode) =>
  renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <MemoryRouter>{node}</MemoryRouter>
    </I18nextProvider>,
  )

const overview: AdminOverview = {
  totals: { users: 120, families: 80, families_multi: 15 },
  new_users: { today: 2, d7: 11, d30: 40 },
  new_families: { today: 1, d7: 6, d30: 22 },
  active: { dau: 30, wau: 70, mau: 100 },
  retention: {
    d7: { returned: 3, cohort: 12, percent: 25 },
    d30: { returned: 0, cohort: 0, percent: null },
  },
  daily_active: Array.from({ length: 30 }, (_, i) => ({
    day: `2026-10-${String(i + 1).padStart(2, '0')}`,
    users: i,
  })),
  activity_since: '2026-10-31',
}

const user = (over: Partial<AdminUser> = {}): AdminUser => ({
  id: '1',
  first_name: 'Али',
  username: 'ali_v',
  phone: '+998901234567',
  language: 'ru',
  registered_at: '2026-10-30T20:00:00Z',
  last_seen_at: '2026-10-30T20:05:00Z',
  family_members: 3,
  family_role: 'owner',
  operations_count: 42,
  ...over,
})

const noop = () => {}

describe('AdminTabs', () => {
  it('marks only the active tab selected', () => {
    for (const tab of ['growth', 'ops', 'users'] as const) {
      const html = wrap(<AdminTabs active={tab} onChange={noop} />)
      expect(html.match(/aria-selected="true"/g)).toHaveLength(1)
      expect(html).toContain('Рост')
      expect(html).toContain('Операции и ИИ')
      expect(html).toContain('Пользователи')
    }
    expect(wrap(<AdminTabs active="ops" onChange={noop} />)).toMatch(/aria-selected="true"[^>]*>Операции и ИИ/)
  })
})

const usage: AdminUsage = {
  period: 'day',
  operations: { text: 5, voice: 2, photo: 1, app: 7, unknown: 3, total: 18 },
  ai: {
    calls: 40, error_calls: 3, calls_without_usage: 0, cost_incomplete: false,
    input_tokens: 123456, output_tokens: 7890, cost_usd: 1.234, messages: 8, unparsed: 2,
    errors: 1, threshold_usd: 5, cost_today_usd: 0.5,
  },
}
const opsRender = (data: AdminUsage, period: 'day' | 'week' | 'month' = 'day') =>
  wrap(<OpsView state={{ period, status: 'ready', data }} onPeriod={noop} onRetry={noop} />)

describe('OpsView', () => {
  it('shows channels, ai calls, cost with two decimals, tokens, unparsed, errors, threshold', () => {
    const html = opsRender(usage)
    for (const s of ['Бот: текст', 'Бот: голос', 'Бот: фото', 'Приложение', 'Не известно (созданы до учёта)', 'Всего', 'Вызовов', 'Стоимость, $', '$1,23', 'Токены: вход / выход', '123\u00a0456 / 7\u00a0890', 'Не разобрано', '25% (2 из 8)', 'Ошибки ИИ', 'Порог в день: $5,00 · сегодня: $0,50']) {
      expect(html).toContain(s)
    }
    expect(html).not.toContain('≈')
  })
  it('marks incomplete cost with ≈', () => {
    expect(opsRender({ ...usage, ai: { ...usage.ai, cost_incomplete: true } })).toContain('≈ $1,23')
  })
  it('shows a dash for unparsed when there were no messages', () => {
    const html = opsRender({ ...usage, ai: { ...usage.ai, messages: 0, unparsed: 0 } })
    expect(html).toContain('Не разобрано')
    expect(html).not.toContain('% (')
  })
  it('says the threshold is not set', () => {
    const html = opsRender({ ...usage, ai: { ...usage.ai, threshold_usd: null } })
    expect(html).toContain('Порог не задан')
    expect(html).not.toContain('Порог в день')
  })
  it('has the period switch with the selected one marked', () => {
    const html = opsRender(usage, 'week')
    expect(html).toContain('Сегодня')
    expect(html).toContain('7 дней')
    expect(html).toContain('30 дней')
    expect(html).toMatch(/aria-selected="true"[^>]*>7 дней/)
  })
  it('renders loading and error states', () => {
    expect(wrap(<OpsView state={{ period: 'day', status: 'loading' }} onPeriod={noop} onRetry={noop} />)).toContain('Загрузка')
    const err = wrap(<OpsView state={{ period: 'day', status: 'error' }} onPeriod={noop} onRetry={noop} />)
    expect(err).toContain('Не получилось загрузить')
    expect(err).toContain('Повторить')
  })
})

describe('AdminScreen', () => {
  const growth = { status: 'ready', data: overview } as const
  const render = (tab: 'growth' | 'ops' | 'users') =>
    wrap(
      <AdminScreen
        tab={tab}
        onTab={noop}
        growth={growth}
        onRetryGrowth={noop}
        users={{ ...initialUsersState, status: 'ready', total: 0 }}
        query=""
        onQuery={noop}
        onMore={noop}
        onRetryUsers={noop}
        ops={{ period: 'day', status: 'ready', data: usage }}
        onPeriod={noop}
        onRetryOps={noop}
      />,
    )
  it('switches the content with the tab and has a back link to Settings', () => {
    expect(render('growth')).toContain('Возвращаемость')
    expect(render('growth')).not.toContain('Скоро')
    expect(render('ops')).toContain('Вызовов')
    expect(render('ops')).not.toContain('Возвращаемость')
    expect(render('users')).toContain('Всего: 0')
    expect(render('growth')).toContain('href="/settings"')
    expect(render('growth')).toContain('‹ Настройки')
  })
})

describe('GrowthView', () => {
  it('shows totals, windows, DAU/WAU/MAU, retention "X% (n из N)" and the since caption', () => {
    const html = wrap(<GrowthView state={{ status: 'ready', data: overview }} onRetry={noop} />)
    expect(html).toContain('120')
    expect(html).toContain('из них семей с 2+ участниками')
    expect(html).toContain('DAU')
    expect(html).toContain('25% (3 из 12)')
    expect(html).toContain('Активность считается с 31.10.2026')
  })
  it('N=0 shows a dash instead of a percent', () => {
    const html = wrap(<GrowthView state={{ status: 'ready', data: overview }} onRetry={noop} />)
    expect(html).toMatch(/D30<\/span><span[^>]*>—</)
  })
  it('hides the caption when there is no activity yet', () => {
    const html = wrap(
      <GrowthView state={{ status: 'ready', data: { ...overview, activity_since: null } }} onRetry={noop} />,
    )
    expect(html).not.toContain('Активность считается')
  })
  it('loading and error states', () => {
    expect(wrap(<GrowthView state={{ status: 'loading' }} onRetry={noop} />)).toContain('Загрузка')
    const err = wrap(<GrowthView state={{ status: 'error' }} onRetry={noop} />)
    expect(err).toContain('Не получилось загрузить')
    expect(err).toContain('Повторить')
  })
})

describe('UsersView', () => {
  const ready = (items: AdminUser[], over: Partial<AdminUsersState> = {}): AdminUsersState => ({
    ...initialUsersState,
    status: 'ready',
    items,
    total: items.length,
    ...over,
  })
  const view = (state: AdminUsersState) =>
    wrap(<UsersView state={state} query="" onQuery={noop} onMore={noop} onRetry={noop} />)

  it('renders a row with all fields, a t.me link and Tashkent dates', () => {
    const html = view(ready([user()]))
    expect(html).toContain('Всего: 1')
    expect(html).toContain('Али')
    expect(html).toContain('href="https://t.me/ali_v"')
    expect(html).toContain('@ali_v')
    expect(html).toContain('+998901234567')
    expect(html).toContain('RU')
    expect(html).toContain('Рег.: 31.10.2026')
    expect(html).toContain('Был: 31.10 01:05')
    expect(html).toContain('Семья: 3 уч., владелец')
    expect(html).toContain('Операций: 42')
  })
  it('empty fields become dashes, no link without username', () => {
    const html = view(ready([user({ first_name: null, username: null, phone: null, last_seen_at: null, family_role: 'member' })]))
    expect(html).not.toContain('t.me')
    expect(html).toContain('Был: —')
    expect(html).toContain('участник')
    expect(html.match(/—/g)!.length).toBeGreaterThanOrEqual(4)
  })
  it('shows "Показать ещё" only while a next page exists', () => {
    expect(view(ready([user()], { nextCursor: 'c' }))).toContain('Показать ещё')
    expect(view(ready([user()], { nextCursor: null }))).not.toContain('Показать ещё')
  })
  it('empty result, loading and error states', () => {
    expect(view(ready([]))).toContain('Ничего не найдено')
    expect(view({ ...initialUsersState, status: 'loading' })).toContain('Загрузка')
    expect(view({ ...initialUsersState, status: 'error' })).toContain('Не получилось загрузить')
  })
  it('renders the search field with the current query', () => {
    const html = wrap(<UsersView state={ready([])} query="ali" onQuery={noop} onMore={noop} onRetry={noop} />)
    expect(html).toContain('value="ali"')
  })
})
