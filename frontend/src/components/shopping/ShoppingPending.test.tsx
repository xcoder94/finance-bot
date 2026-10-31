import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'

vi.mock('../../i18n', () => ({ default: { language: 'ru' } }))

import ru from '../../i18n/locales/ru.json'
import uz from '../../i18n/locales/uz.json'
import { ShoppingAmountView } from './ShoppingAmountView'
import { ShoppingManualView } from './ShoppingManualView'
import { ShoppingWaitingBanner } from './ShoppingWaitingBanner'

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

const amountProps = {
  count: 3, amount: '', overLimit: false, currencySuffix: 'сум', categoryLabel: 'Еда',
  walletLabel: 'Карта', busy: false, failed: false, noWallet: false,
  onAmount: noop, onOverLimit: noop, onSubmit: noop, onBack: noop,
  photoEnabled: true, botMethod: null as 'receipt' | 'voice' | null, onBotMethod: noop,
}

describe('ShoppingAmountView: bot methods', () => {
  it('shows both ways when the photo flag is on', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} />)
    expect(html).toContain('Отправить фото чека')
    expect(html).toContain('Сказать сумму голосом')
  })
  it('hides the photo button when the flag is off; voice stays', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} photoEnabled={false} />)
    expect(html).not.toContain('Отправить фото чека')
    expect(html).toContain('Сказать сумму голосом')
  })
  it('after a tap shows the minimise hint for that method', () => {
    expect(wrap(<ShoppingAmountView {...amountProps} botMethod="receipt" busy />)).toContain(
      'Приложение свернётся, бот ждёт фото чека. Сумма вернётся сюда.',
    )
    expect(wrap(<ShoppingAmountView {...amountProps} botMethod="voice" busy />)).toContain(
      'Приложение свернётся, бот ждёт голосовое. Сумма вернётся сюда.',
    )
  })
  it('no hint before a tap; Uzbek labels exist', () => {
    expect(wrap(<ShoppingAmountView {...amountProps} />)).not.toContain('свернётся')
    const html = wrap(<ShoppingAmountView {...amountProps} />, 'uz')
    expect(html).toContain('Chek yuboraman')
    expect(html).toContain('Ovoz orqali')
  })
})

const manualProps = {
  method: 'receipt' as const, status: 'unrecognized' as const, amount: '', overLimit: false, currencySuffix: 'сум', busy: false,
  failed: false, canRetry: true, onAmount: noop, onOverLimit: noop, onSubmit: noop,
  onRetry: noop, onCancel: noop,
}

describe('ShoppingManualView («Введите сумму вручную»)', () => {
  it('receipt: title, caption, record and retry-photo buttons', () => {
    const html = wrap(<ShoppingManualView {...manualProps} />)
    expect(html).toContain('Введите сумму вручную')
    expect(html).toContain('Не получилось распознать чек. Сумма нужна одна на всю закупку.')
    expect(html).toContain('Записать')
    expect(html).toContain('Отправить фото ещё раз')
  })
  it('still waiting (status awaiting): neutral caption, never «Не получилось распознать»', () => {
    for (const method of ['receipt', 'voice'] as const) {
      const html = wrap(<ShoppingManualView {...manualProps} method={method} status="awaiting" />)
      expect(html).not.toContain('Не получилось')
      expect(html).toContain('Сумма нужна одна на всю закупку.')
    }
    expect(wrap(<ShoppingManualView {...manualProps} status="awaiting" />, 'uz')).not.toContain('aniqlab bo\'lmadi')
  })
  it('voice: its own caption and «Сказать ещё раз»', () => {
    const html = wrap(<ShoppingManualView {...manualProps} method="voice" />)
    expect(html).toContain('Не получилось разобрать сумму. Сумма нужна одна на всю закупку.')
    expect(html).toContain('Сказать ещё раз')
  })
  it('no retry button when the ticked items are unknown (other device)', () => {
    expect(wrap(<ShoppingManualView {...manualProps} canRetry={false} />)).not.toContain('ещё раз')
  })
  it('failed record shows the shared text, never the word «ошибка»', () => {
    const html = wrap(<ShoppingManualView {...manualProps} failed />)
    expect(html).toContain('Не получилось записать. Повторите.')
    expect(html.toLowerCase()).not.toContain('ошибк')
  })
  it('Record disabled without an amount', () => {
    expect(wrap(<ShoppingManualView {...manualProps} />)).toMatch(/shopping-trip__finish"[^>]*disabled/)
  })
})

describe('ShoppingWaitingBanner (back in the app while waiting)', () => {
  it('receipt / voice wait text with the manual link', () => {
    const r = wrap(<ShoppingWaitingBanner method="receipt" status="awaiting" onManual={noop} />)
    expect(r).toContain('Ждём фото чека в боте')
    expect(r).toContain('Ввести сумму вручную')
    const v = wrap(<ShoppingWaitingBanner method="voice" status="awaiting" onManual={noop} />)
    expect(v).toContain('Ждём голосовое в боте')
  })
  it('Uzbek', () => {
    const html = wrap(<ShoppingWaitingBanner method="receipt" status="awaiting" onManual={noop} />, 'uz')
    expect(html).toContain('Botda chek rasmini kutyapmiz')
    expect(html).toContain('Summani qo&#x27;lda kiritish')
  })
  it('unrecognized: no «waiting» text, only the manual entry', () => {
    const html = wrap(<ShoppingWaitingBanner method="receipt" status="unrecognized" onManual={noop} />)
    expect(html).not.toContain('Ждём')
    expect(html).toContain('Ввести сумму вручную')
  })
})
