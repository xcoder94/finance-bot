import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'

const flags = vi.hoisted(() => ({ isAdmin: false }))
vi.mock('../store/authStore', () => ({
  useAuthStore: (selector: (s: { user: Record<string, unknown> }) => unknown) =>
    selector({
      user: {
        id: 'u', telegramId: 1, familyBudgetId: 'f', role: 'owner', firstName: 'Ali',
        username: null, language: 'ru', budgetName: 'Семья', memberCount: 1,
        defaultWalletId: null, eveningReminderEnabled: false, weeklyDigestEnabled: false,
        isAdmin: flags.isAdmin,
      },
    }),
}))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('@tma.js/sdk-react', () => ({ useRawInitData: () => undefined }))
vi.mock('../api/wallets', () => ({ getWallets: async () => [] }))
vi.mock('../api/categories', () => ({
  getIncomeCategories: async () => [],
  getExpenseCategories: async () => [],
}))

import adminRu from '../i18n/locales/admin.ru.json'
import ru from '../i18n/locales/ru.json'
import { SettingsPage } from './SettingsPage'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru, admin: adminRu } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})
const render = () =>
  renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <MemoryRouter initialEntries={['/settings']}>
        <SettingsPage />
      </MemoryRouter>
    </I18nextProvider>,
  )

describe('Settings: Admin row', () => {
  it('is not rendered when is_admin=false', () => {
    flags.isAdmin = false
    const html = render()
    expect(html).not.toContain('Админка')
    expect(html).not.toContain('/admin')
  })
  it('is the last separate group with "Только для вас" for an admin', () => {
    flags.isAdmin = true
    const html = render()
    expect(html).toContain('href="/admin"')
    expect(html).toContain('Только для вас')
    // after the main list (Theme row is its last) and after the language row
    expect(html.indexOf('Админка')).toBeGreaterThan(html.indexOf('Тема'))
    expect(html.match(/class="settings-toc-list/g)).toHaveLength(2)
    // the footer hint stays the very last element
    expect(html.indexOf('settings-page__footer-hint')).toBeGreaterThan(html.indexOf('Админка'))
  })
})
