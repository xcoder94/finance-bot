import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { AppRoot } from '@telegram-apps/telegram-ui'

import ru from '../../i18n/locales/ru.json'

vi.mock('../../i18n', () => ({ default: { language: 'ru', resolvedLanguage: 'ru' } }))

import { WalletsView } from './WalletsView'
import type { WalletsOverviewItem } from '../../utils/walletsOverview'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})

const w = (
  id: string,
  balance: number,
  over: Partial<WalletsOverviewItem> = {},
): WalletsOverviewItem => ({
  id,
  name: id,
  translation_key: null,
  currency: 'UZS',
  is_personal: false,
  balance,
  ...over,
})

function render(props: Omit<Parameters<typeof WalletsView>[0], 'onOpenWallet'>): string {
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <AppRoot>
        <WalletsView onOpenWallet={() => {}} {...props} />
      </AppRoot>
    </I18nextProvider>,
  ).replace(/\u00a0/g, ' ')
}

describe('WalletsView', () => {
  it('shared + personal groups, total = 1 200', () => {
    const html = render({
      status: 'success',
      wallets: [w('Alpha', 1000), w('Beta', -300), w('Mine', 500, { is_personal: true })],
      onRetry: () => {},
    })
    expect(html).toContain('Кошельки')
    expect(html).toContain('Всего на кошельках')
    expect(html).toContain('1 200 сум')
    expect(html).toContain('Общие')
    expect(html).toContain('Личные')
    expect(html).toContain('1 000 сум')
    expect(html).toContain('-300 сум')
    expect(html).toContain('500 сум')
    expect(html).toContain('Это деньги на кошельках сейчас')
    expect(html.indexOf('Общие')).toBeLessThan(html.indexOf('Личные'))
    expect(html.indexOf('Beta')).toBeLessThan(html.indexOf('Личные'))
    expect(html.indexOf('Mine')).toBeGreaterThan(html.indexOf('Личные'))
  })

  it('UZS and USD get separate totals with own signs', () => {
    const html = render({
      status: 'success',
      wallets: [w('A', 1000), w('B', -25, { currency: 'USD' })],
      onRetry: () => {},
    })
    expect(html).toContain('1 000 сум')
    expect(html).toContain('-$25')
  })

  it('no personal wallets: group hidden', () => {
    const html = render({ status: 'success', wallets: [w('A', 1)], onRetry: () => {} })
    expect(html).not.toContain('Личные')
  })

  it('no wallets: empty text', () => {
    const html = render({ status: 'success', wallets: [], onRetry: () => {} })
    expect(html).toContain('Кошельков пока нет')
  })

  it('error: block with retry', () => {
    const html = render({ status: 'error', wallets: [], onRetry: () => {} })
    expect(html).toContain('role="alert"')
    expect(html).toContain(ru.auth.retry)
  })

  it('loading: status region', () => {
    const html = render({ status: 'loading', wallets: [], onRetry: () => {} })
    expect(html).toContain('role="status"')
  })

  it('every wallet row is a button', () => {
    const html = render({ status: 'success', wallets: [w('Alpha', 1000), w('Beta', 5)], onRetry: () => {} })
    const rows = html.match(/<button[^>]*home-ops-row--clickable[^>]*>/g) ?? []
    expect(rows).toHaveLength(2)
    expect(html).toMatch(/<button[^>]*>[^]*Alpha/)
  })

  it('long total shrinks like on Home', () => {
    const html = render({ status: 'success', wallets: [w('Alpha', 1234567890)], onRetry: () => {} })
    expect(html).toContain('wallets-total__value home-figures-card__balance--xlong')
  })
})
