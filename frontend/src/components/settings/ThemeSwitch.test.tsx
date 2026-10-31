import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'

import ru from '../../i18n/locales/ru.json'
import { useThemeStore } from '../../store/themeStore'
import { ThemeSwitch } from './ThemeSwitch'

vi.mock('../../telegram/themeStorage', () => ({
  cloudGet: async () => null,
  cloudSet: async () => undefined,
}))
vi.mock('../../telegram/telegramChrome', () => ({ applyTelegramChrome: () => undefined }))

beforeEach(async () => {
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => undefined })
  vi.stubGlobal('document', { documentElement: { dataset: {} } })
  const instance = i18n.createInstance()
  await instance.use(initReactI18next).init({
    lng: 'ru',
    resources: { ru: { translation: ru } },
  })
  ;(globalThis as { __i18n?: typeof instance }).__i18n = instance
})

function render() {
  const instance = (globalThis as unknown as { __i18n: typeof i18n }).__i18n
  return renderToStaticMarkup(
    <I18nextProvider i18n={instance}>
      <ThemeSwitch />
    </I18nextProvider>,
  )
}

describe('ThemeSwitch', () => {
  it('shows both options with the dark one selected by default', () => {
    useThemeStore.setState({ theme: 'dark' })
    const html = render()
    expect(html).toContain('Тёмная')
    expect(html).toContain('Светлая')
    expect(html).toMatch(/aria-checked="true"[^>]*>Тёмная/)
    expect(html).toMatch(/aria-checked="false"[^>]*>Светлая/)
  })

  it('renders radio semantics for both options', () => {
    const html = render()
    expect(html.match(/role="radio"/g)).toHaveLength(2)
    expect(html).toContain('role="radiogroup"')
  })
})
