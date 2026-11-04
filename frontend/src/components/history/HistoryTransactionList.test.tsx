import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { AppRoot } from '@telegram-apps/telegram-ui'

import ru from '../../i18n/locales/ru.json'

vi.mock('../../i18n', () => ({ default: { language: 'ru', resolvedLanguage: 'ru' } }))

import type { HistoryItem } from '../../api/history'
import { HistoryTransactionList } from './HistoryTransactionList'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})

const transfer = {
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

function render(extra: Record<string, unknown> = {}, items: HistoryItem[] = [transfer], status = 'success') {
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <AppRoot>
        <HistoryTransactionList
          status={status as 'success'}
          items={items}
          totalCount={items.length}
          onItemClick={() => {}}
          onRetry={() => {}}
          {...extra}
        />
      </AppRoot>
    </I18nextProvider>,
  ).replace(/[  ]/g, ' ')
}

describe('HistoryTransactionList', () => {
  it('default: transfer shown as neutral "↔ amount", empty hint is the category one', () => {
    expect(render()).toContain('↔ 5 000 сум')
    const empty = render({}, [])
    expect(empty).toContain(ru.history.emptyTitle)
    expect(empty).toContain(ru.history.emptyHint)
  })

  it('formatAmount overrides only the amount text', () => {
    const html = render({ formatAmount: () => '−777 сум' })
    expect(html).toContain('−777 сум')
    expect(html).not.toContain('↔')
  })

  it('emptyHint replaces the hint under the same title', () => {
    const empty = render({ emptyHint: 'Выберите другой месяц.' }, [])
    expect(empty).toContain(ru.history.emptyTitle)
    expect(empty).toContain('Выберите другой месяц.')
    expect(empty).not.toContain(ru.history.emptyHint)
  })
})
