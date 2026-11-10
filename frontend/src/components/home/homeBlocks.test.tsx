import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'

import ru from '../../i18n/locales/ru.json'
import uz from '../../i18n/locales/uz.json'
import { balanceSizeClass, statSizeClass, HomeLeftBlock, HomeOnboardingCard } from './homeBlocks'

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
        <HomeOnboardingCard steps={steps} onStart={vi.fn()} onStartIncome={vi.fn()} onClose={vi.fn()} />
      </I18nextProvider>,
    )
    expect(ru1).toContain('aria-label="Закрыть"')
    expect(ru1).toContain('home-onboarding__close')
    expect(ru1).toContain('×')
    const uz1 = renderToStaticMarkup(
      <I18nextProvider i18n={make('uz')}>
        <HomeOnboardingCard steps={steps} onStart={vi.fn()} onStartIncome={vi.fn()} onClose={vi.fn()} />
      </I18nextProvider>,
    )
    expect(uz1).toContain('aria-label="Yopish"')
  })
})

describe('HomeLeftBlock layout (B2, B6)', () => {
  const html = (perDay: number | null) =>
    renderToStaticMarkup(
      <I18nextProvider i18n={make('ru')}>
        <HomeLeftBlock perDay={perDay} days={14} />
      </I18nextProvider>,
    )

  it('long amounts get a size class instead of being cut by an ellipsis', () => {
    expect(html(-9_100_000)).toContain('home-left__value--long')
    expect(html(246_400)).not.toContain('home-left__value--xlong')
    expect(html(-123_456_789)).toContain('home-left__value--xlong')
  })
})

describe('HomeLeftBlock amounts use NBSP digit groups', () => {
  it('per-day amount never break on a plain space', () => {
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={make('uz')}>
        <HomeLeftBlock perDay={41100} days={30} />
      </I18nextProvider>,
    )
    expect(html).toContain('41\u00a0100')
    expect(html).not.toMatch(/\d \d{3}/)
  })
})

describe('HomeLeftBlock without income (dev-fix5)', () => {
  it('shows a dash and the add-income hint instead of a sum', () => {
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={make('ru')}>
        <HomeLeftBlock perDay={null} days={14} noIncome />
      </I18nextProvider>,
    )
    expect(html).toContain('Добавьте доход, чтобы посчитать')
    expect(html).not.toContain('месяц завершён')
    expect(html).toContain('—')
  })
})

describe('balanceSizeClass (owner decision: shrink from 15 characters)', () => {
  it('14 characters stay at the normal size', () => {
    expect(balanceSizeClass('1 000 000 so\'m')).toBe('')
    expect(balanceSizeClass('x'.repeat(14))).toBe('')
  })
  it('15 and 16 characters step down, 17+ step down more', () => {
    expect(balanceSizeClass('x'.repeat(15))).toBe(' home-figures-card__balance--long')
    expect(balanceSizeClass('x'.repeat(16))).toBe(' home-figures-card__balance--long')
    expect(balanceSizeClass('x'.repeat(17))).toBe(' home-figures-card__balance--xlong')
  })
})

describe('HomeOnboardingCard step states (B12)', () => {
  const render = (s: typeof steps) =>
    renderToStaticMarkup(
      <I18nextProvider i18n={make('ru')}>
        <HomeOnboardingCard steps={s} onStart={vi.fn()} onStartIncome={vi.fn()} onClose={vi.fn()} />
      </I18nextProvider>,
    )
  it('first step done: check icon, muted, step 2 is current, CTA is the income one', () => {
    const html = render({ ...steps, firstOperation: true })
    expect(html).toContain('home-onboarding__step--done')
    expect(html).toContain('home-onboarding__check')
    expect(html.match(/home-onboarding__step--current/g)).toHaveLength(1)
    expect(html.indexOf('step--done')).toBeLessThan(html.indexOf('step--current'))
    expect(html).toContain('Добавить доход')
    expect(html).not.toContain('Записать расход')
  })
  it('nothing done: first step is current, CTA shown, no check', () => {
    const html = render(steps)
    expect(html).toContain('home-onboarding__cta')
    expect(html).not.toContain('home-onboarding__check')
    expect(html.indexOf('step--current')).toBeLessThan(html.indexOf('step--next'))
  })
})

describe('HomeOnboardingCard U5 step 2', () => {
  it('step 2 reads «Добавьте доход за месяц» and its action opens the income form', () => {
    const onStartIncome = vi.fn()
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={make('ru')}>
        <HomeOnboardingCard
          steps={{ firstOperation: true, defaultWalletChecked: false, familyInvited: false }}
          onStart={vi.fn()}
          onStartIncome={onStartIncome}
          onClose={vi.fn()}
        />
      </I18nextProvider>,
    )
    expect(html).toContain('Добавьте доход за месяц')
    expect(html).not.toContain('Проверьте кошелёк по умолчанию')
    expect(html).toContain('home-onboarding__cta')
    expect(html).toContain('Добавить доход')
  })
})

describe('statSizeClass (B5: digits are never cut, the font steps down instead)', () => {
  it('keeps 16px for short amounts', () => {
    expect(statSizeClass('100 000 сум')).toBe('')
  })
  it('steps down for long amounts', () => {
    expect(statSizeClass('15 500 000 сум')).toBe(' home-figures-card__stat-value--long')
    expect(statSizeClass('2 005 970 900 сум')).toBe(' home-figures-card__stat-value--xlong')
    expect(statSizeClass('x'.repeat(20))).toBe(' home-figures-card__stat-value--xxlong')
  })
})
