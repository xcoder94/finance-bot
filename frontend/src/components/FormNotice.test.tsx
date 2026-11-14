import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'

vi.mock('../i18n', () => ({ default: { language: 'ru' } }))

import ru from '../i18n/locales/ru.json'
import uz from '../i18n/locales/uz.json'
import { ShoppingAmountView } from './shopping/ShoppingAmountView'
import { ShoppingResultView } from './shopping/ShoppingResultView'
import { ShoppingTripView } from './shopping/ShoppingTripView'
import { FormNotice } from './FormNotice'
import { noticeKindForKey } from '../utils/noticeKind'

const make = (lng: 'ru' | 'uz') => {
  const inst = i18n.createInstance()
  void inst.use(initReactI18next).init({
    resources: { ru: { translation: ru }, uz: { translation: uz } },
    lng,
    interpolation: { escapeValue: false },
  })
  return inst
}
const wrap = (node: React.ReactNode, lng: 'ru' | 'uz' = 'ru') =>
  renderToStaticMarkup(<I18nextProvider i18n={make(lng)}>{node}</I18nextProvider>)
const noop = () => {}

describe('FormNotice: one look for every form status message', () => {
  it('shows an icon and the text, with the class of its kind', () => {
    for (const kind of ['error', 'warning', 'info'] as const) {
      const html = wrap(<FormNotice kind={kind}>Текст сообщения</FormNotice>)
      expect(html).toContain('Текст сообщения')
      expect(html).toContain(`form-notice--${kind}`)
      expect(html).toMatch(/<span class="form-notice__icon" aria-hidden="true">[^<]+<\/span>/)
    }
  })

  it('errors and warnings are announced as alerts, a hint as a status', () => {
    expect(wrap(<FormNotice kind="error">x</FormNotice>)).toContain('role="alert"')
    expect(wrap(<FormNotice kind="warning">x</FormNotice>)).toContain('role="alert"')
    expect(wrap(<FormNotice kind="info">x</FormNotice>)).toContain('role="status"')
  })

  it('maps a message key to its kind', () => {
    expect(noticeKindForKey('addTransaction.submitError')).toBe('error')
    expect(noticeKindForKey('settings.submitError')).toBe('error')
    expect(noticeKindForKey('familyChanged.message')).toBe('warning')
    expect(noticeKindForKey('familyChanged.generic')).toBe('warning')
    expect(noticeKindForKey('familyChanged.pickReplaced')).toBe('info')
  })
})

const amountProps = {
  count: 3, amount: '', overLimit: false, currencySuffix: 'сум', categoryLabel: 'Еда',
  walletLabel: 'Карта', busy: false, failed: false, noWallet: false,
  onAmount: noop, onOverLimit: noop, onSubmit: noop, onBack: noop,
  photoEnabled: true, botMethod: null as 'receipt' | 'voice' | null, onBotMethod: noop,
  initialMethod: undefined as 'manual' | 'receipt' | 'voice' | undefined,
}

describe('the purchase sheet uses the same notice', () => {
  it('family changed is a warning notice with icon', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} familyChanged />)
    expect(html).toMatch(/class="form-notice form-notice--warning"[^>]*>.*Состав семьи изменился/)
  })
  it('a failed record is an error notice', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} failed />)
    expect(html).toMatch(/form-notice--error[^>]*>.*Не получилось записать/)
  })
})

describe('purchase result without marks', () => {
  const purchase = { amount: 1000, remaining: 5000, items_recorded: 0, items_left: 3, wallet_name: 'Карта' }
  const resultNone = (lng: 'ru' | 'uz') =>
    wrap(
      <ShoppingResultView
        purchase={purchase as never}
        requested={3}
        categoryLabel="Еда"
        walletLabel="Карта"
        onDone={noop}
      />,
      lng,
    )
  it('RU title is the short one', () => {
    expect(resultNone('ru')).toContain('Расход записан, позиции не отмечены<')
  })
  it('UZ title is the short draft', () => {
    expect(resultNone('uz')).toContain('Xarajat yozildi, pozitsiyalar belgilanmadi<')
  })
})

describe('trip list with nothing marked', () => {
  const items = [{ id: '1', name: 'Молоко', created_at: '2026-10-31T10:00:00Z' }]
  const trip = (checked: string[], lng: 'ru' | 'uz' = 'ru') =>
    wrap(
      <ShoppingTripView items={items} checked={new Set(checked)} popId={null} onToggle={noop} onCancel={noop} onFinish={noop} />,
      lng,
    )
  it('tells why the finish button is off', () => {
    expect(trip([])).toContain('Отметьте купленное, чтобы завершить закупку')
    expect(trip([], 'uz')).toContain('Yakunlash uchun sotib olinganlarni belgilang')
  })
  it('no hint once something is marked', () => {
    expect(trip(['1'])).not.toContain('Отметьте купленное')
  })
})
