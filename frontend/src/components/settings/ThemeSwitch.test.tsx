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
  it('shows System / Light / Dark with System selected by default', () => {
    useThemeStore.setState({ preference: 'system' })
    const html = render()
    expect(html).toContain('Системная')
    expect(html).toMatch(/aria-checked="true"[^>]*>Системная/)
    expect(html).toMatch(/aria-checked="false"[^>]*>Светлая/)
    expect(html).toMatch(/aria-checked="false"[^>]*>Тёмная/)
  })

  it('marks the saved manual choice', async () => {
    // SSR reads the store's initial state, so seed storage and load a fresh store + component
    vi.stubGlobal('localStorage', { getItem: () => 'dark', setItem: () => undefined })
    vi.resetModules()
    const { ThemeSwitch: Fresh } = await import('./ThemeSwitch')
    const instance = (globalThis as unknown as { __i18n: typeof i18n }).__i18n
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={instance}>
        <Fresh />
      </I18nextProvider>,
    )
    expect(html).toMatch(/aria-checked="true"[^>]*>Тёмная/)
  })

  it('renders radio semantics for both options', () => {
    const html = render()
    expect(html.match(/role="radio"/g)).toHaveLength(3)
    expect(html).toContain('role="radiogroup"')
  })
})
