import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { AppRoot } from '@telegram-apps/telegram-ui'

import ru from '../../i18n/locales/ru.json'

vi.mock('../../i18n', () => ({ default: { language: 'ru', resolvedLanguage: 'ru' } }))

import type { HistoryItem } from '../../api/history'
import type { WalletOpsState } from '../../utils/walletOps'
import { WalletOpsView, type WalletOpsViewProps } from './WalletOpsView'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})

const wallet = { id: 'A', name: 'Alpha', translation_key: null, currency: 'UZS', is_personal: false, balance: 12000 }
const ops = (over: Partial<WalletOpsState> = {}): WalletOpsState => ({
  status: 'success',
  items: [],
  total: 0,
  loadingMore: false,
  loadMoreError: false,
  ...over,
})
const outTransfer = {
  id: 't1',
  type: 'transfer',
  transaction_date: '2026-11-03T10:00:00+05:00',
  amount: 5000,
  currency: 'UZS',
  wallet_id: 'A',
  wallet_name: 'Alpha',
  wallet_translation_key: null,
  to_wallet_id: 'B',
  to_wallet_name: 'Beta',
  to_wallet_translation_key: null,
  to_amount: 5000,
  to_currency: 'UZS',
  comment: null,
} as unknown as HistoryItem

function render(over: Partial<WalletOpsViewProps> = {}): string {
  const props: WalletOpsViewProps = {
    wallet,
    month: { year: 2026, month: 11 },
    ops: ops(),
    onPrevMonth: () => {},
    onNextMonth: () => {},
    onOpenItem: () => {},
    onRetry: () => {},
    onLoadMore: () => {},
    ...over,
  }
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <AppRoot>
        <WalletOpsView {...props} />
      </AppRoot>
    </I18nextProvider>,
  ).replace(/[  ]/g, ' ')
}

describe('WalletOpsView', () => {
  it('shows name, balance label and balance', () => {
    const html = render()
    expect(html).toContain('Alpha')
    expect(html).toContain(ru.wallets.balanceNow)
    expect(html).toContain('12 000 сум')
  })

  it('month switcher with both arrows', () => {
    const html = render()
    expect(html).toContain(ru.home.previousMonth)
    expect(html).toContain(ru.home.nextMonth)
    expect(html).toContain('2026')
  })

  it('transfer rows are relative to this wallet', () => {
    const out = render({ ops: ops({ items: [outTransfer], total: 1 }) })
    expect(out).toContain('−5 000 сум')
    const incoming = render({
      wallet: { ...wallet, id: 'B' },
      ops: ops({ items: [outTransfer], total: 1 }),
    })
    expect(incoming).toContain('+5 000 сум')
  })

  it('empty month: title and wallet hint, not the category hint', () => {
    const html = render()
    expect(html).toContain(ru.history.emptyTitle)
    expect(html).toContain(ru.wallets.opsEmptyHint)
    expect(html).not.toContain(ru.history.emptyHint)
  })

  it('load error: block with retry', () => {
    const html = render({ ops: ops({ status: 'error' }) })
    expect(html).toContain('role="alert"')
    expect(html).toContain(ru.auth.retry)
  })

  it('show more button when not everything is loaded', () => {
    const html = render({ ops: ops({ items: [outTransfer], total: 60 }) })
    expect(html).toContain(ru.history.loadMore)
  })

  it('long balance shrinks like on Home: 10 digits and minus fit the card', () => {
    const html = render({ wallet: { ...wallet, balance: -1234567890 } })
    expect(html).toContain('home-figures-card__balance--xlong')
    expect(render()).not.toContain('home-figures-card__balance--')
  })
})
