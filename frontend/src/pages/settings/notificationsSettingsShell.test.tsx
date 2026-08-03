import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'

import ru from '../../i18n/locales/ru.json'
import { NotificationsSettingsBody } from './NotificationsSettingsShellPage'

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

  it('has no checkbox or switch controls', () => {
    const html = renderNotificationsBody()
    expect(html).not.toContain('type="checkbox"')
    expect(html).not.toContain('role="switch"')
    expect(html).not.toContain('settings-notifications-toggle')
    expect(html).not.toMatch(/<input\b/)
    expect(html).not.toMatch(/<button\b/)
  })
})
