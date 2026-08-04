import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'

import ru from '../../i18n/locales/ru.json'
import { NotificationsSettingsBody } from './NotificationsSettingsShellPage'

vi.mock('../../api/me', () => ({
  patchMe: vi.fn(),
}))

vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector: (state: {
    user: {
      eveningReminderEnabled: boolean
      weeklyDigestEnabled: boolean
    }
    setLocalEveningReminder: () => void
    setLocalWeeklyDigest: () => void
  }) => unknown) =>
    selector({
      user: {
        eveningReminderEnabled: true,
        weeklyDigestEnabled: false,
      },
      setLocalEveningReminder: vi.fn(),
      setLocalWeeklyDigest: vi.fn(),
    }),
}))

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

function renderNotificationsBody() {
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <NotificationsSettingsBody />
    </I18nextProvider>,
  )
}

describe('NotificationsSettingsBody', () => {
  it('renders static notification rows from design copy', () => {
    const html = renderNotificationsBody()
    expect(html).toContain('Напоминание вечером')
    expect(html).toContain('Если за день не было ни одной записи, 21:00')
    expect(html).toContain('Итоги недели')
    expect(html).toContain('Каждый понедельник в 10:00')
    expect(html).toContain('Два независимых переключателя')
  })

  it('renders exactly two toggle switches with correct checked state', () => {
    const html = renderNotificationsBody()
    const switches = html.match(/role="switch"/g) ?? []
    expect(switches).toHaveLength(2)
    expect(html).toContain('aria-checked="true"')
    expect(html).toContain('aria-checked="false"')
    expect(html).toContain('settings-toggle-row__track--on')
    expect(html).toContain('settings-toggle-row__track--off')
  })
})
