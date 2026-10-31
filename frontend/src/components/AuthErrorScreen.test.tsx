import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { AppRoot } from '@telegram-apps/telegram-ui'

import ru from '../i18n/locales/ru.json'
import uz from '../i18n/locales/uz.json'
import { AuthErrorScreen } from './AuthErrorScreen'

function render(lng: 'ru' | 'uz', errorType: 'network' | 'pass_failed' | 'unauthorized') {
  const inst = i18n.createInstance()
  void inst.use(initReactI18next).init({
    resources: { ru: { translation: ru }, uz: { translation: uz } },
    lng,
    interpolation: { escapeValue: false },
  })
  return renderToStaticMarkup(
    <I18nextProvider i18n={inst}>
      <AppRoot>
        <AuthErrorScreen errorType={errorType} onRetry={() => undefined} />
      </AppRoot>
    </I18nextProvider>,
  )
}

describe('login error text', () => {
  it.each(['ru', 'uz'] as const)('does not blame the "server" (%s)', (lng) => {
    for (const type of ['network', 'pass_failed', 'unauthorized'] as const) {
      expect(render(lng, type)).not.toMatch(/сервер|server/i)
    }
  })

  it('shows the localized network message', () => {
    expect(render('ru', 'network')).toContain('Не удалось подключиться')
    expect(render('uz', 'network')).toContain("Ulanib bo&#x27;lmadi")
  })
})
