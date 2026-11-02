import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'

import ru from '../i18n/locales/ru.json'

const mockUser = {
  id: 'u', telegramId: 1, familyBudgetId: 'f', role: 'owner', firstName: 'Ali',
  username: null, language: 'ru', budgetName: 'Семья', memberCount: 1,
  defaultWalletId: null, eveningReminderEnabled: false, weeklyDigestEnabled: false,
}
vi.mock('../store/authStore', () => ({
  useAuthStore: (selector: (s: { user: typeof mockUser }) => unknown) =>
    selector({ user: mockUser }),
}))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('@tma.js/sdk-react', () => ({ useRawInitData: () => undefined }))
vi.mock('../api/wallets', () => ({ getWallets: async () => [] }))
vi.mock('../api/categories', () => ({
  getIncomeCategories: async () => [],
  getExpenseCategories: async () => [],
}))

import { SettingsPage } from './SettingsPage'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

describe('SettingsPage', () => {
  it('has 8 rows, Theme last, a back link to Home and the user card', () => {
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={testI18n}>
        <MemoryRouter initialEntries={['/settings']}>
          <SettingsPage />
        </MemoryRouter>
      </I18nextProvider>,
    )
    const rows = html.match(/class="settings-toc-row[ "]/g) ?? []
    expect(rows).toHaveLength(8)
    const titles = [...html.matchAll(/settings-toc-row__title">([^<]*)</g)].map((m) => m[1])
    expect(titles.at(-1)).toBe('Тема')
    expect(html).toContain('‹ Главная')
    expect(html).toContain('href="/"')
    expect(html).toContain('user-avatar')
    expect(html).toContain('Владелец')
  })

  it('QA m3-1: the Theme row carries the Системная/Светлая/Тёмная switch, System checked by default', () => {
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={testI18n}>
        <MemoryRouter initialEntries={['/settings']}>
          <SettingsPage />
        </MemoryRouter>
      </I18nextProvider>,
    )
    const themeRow = html.slice(html.lastIndexOf('settings-toc-row'))
    expect(themeRow).toContain('role="radiogroup"')
    expect(themeRow.match(/role="radio"/g) ?? []).toHaveLength(3)
    expect(themeRow).toMatch(/aria-checked="true"[^>]*>Системная</)
    expect(themeRow).toContain('Светлая')
    expect(themeRow).toContain('Тёмная')
  })
})
