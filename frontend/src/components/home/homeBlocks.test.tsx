import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'

import ru from '../../i18n/locales/ru.json'
import uz from '../../i18n/locales/uz.json'
import { HomeLeftBlock, HomeOnboardingCard } from './homeBlocks'

function make(lng: 'ru' | 'uz') {
  const inst = i18n.createInstance()
  void inst.use(initReactI18next).init({
    resources: { ru: { translation: ru }, uz: { translation: uz } },
    lng,
    interpolation: { escapeValue: false },
  })
  return inst
}
const steps = { firstOperation: false, defaultWalletChecked: false, familyInvited: false }

describe('HomeOnboardingCard close button (owner decision 11)', () => {
  it('renders a × button with a localized aria-label', () => {
    const ru1 = renderToStaticMarkup(
      <I18nextProvider i18n={make('ru')}>
        <HomeOnboardingCard steps={steps} onStart={vi.fn()} onClose={vi.fn()} />
      </I18nextProvider>,
    )
    expect(ru1).toContain('aria-label="Закрыть"')
    expect(ru1).toContain('home-onboarding__close')
    expect(ru1).toContain('×')
    const uz1 = renderToStaticMarkup(
      <I18nextProvider i18n={make('uz')}>
        <HomeOnboardingCard steps={steps} onStart={vi.fn()} onClose={vi.fn()} />
      </I18nextProvider>,
    )
    expect(uz1).toContain('aria-label="Yopish"')
  })
})

describe('HomeLeftBlock layout (B2, B6)', () => {
  const html = (remaining: number, perDay: number | null) =>
    renderToStaticMarkup(
      <I18nextProvider i18n={make('ru')}>
        <HomeLeftBlock remaining={remaining} perDay={perDay} days={14} />
      </I18nextProvider>,
    )

  it('long amounts get a size class instead of being cut by an ellipsis', () => {
    expect(html(-9_100_000, -650_000)).toContain('home-left__value--long')
    expect(html(3_450_000, 246_400)).not.toContain('home-left__value--xlong')
    expect(html(-123_456_789, 1)).toContain('home-left__value--xlong')
  })
})
