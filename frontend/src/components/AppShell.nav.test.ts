import { describe, expect, it } from 'vitest'

import ru from '../i18n/locales/ru.json'
import { MAIN_TABS } from './mainTabs'

describe('MAIN_TABS', () => {
  it('has four Russian nav labels', () => {
    const labels = MAIN_TABS.map((tab) => {
      const key = tab.labelKey.replace('nav.', '') as keyof typeof ru.nav
      return ru.nav[key]
    })
    expect(labels).toEqual(['Главная', 'Аналитика', 'Цели', 'Настройки'])
  })
})
