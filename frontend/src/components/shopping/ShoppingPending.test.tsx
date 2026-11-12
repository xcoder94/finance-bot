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
  initialMethod: undefined as 'manual' | 'receipt' | 'voice' | undefined,
}

describe('ShoppingAmountView: family changed', () => {
  it('says the family changed instead of the usual record failure', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} failed={false} familyChanged />)
    expect(html).toContain('Состав семьи изменился')
    expect(html).not.toContain(ru.shopping.recordFailed)
  })
})

describe('ShoppingAmountView: stale list (404)', () => {
  it('says the list changed, not the usual record failure', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} failed={false} staleList />)
    expect(html).toContain('Список изменился')
    expect(html).not.toContain(ru.shopping.recordFailed)
  })
})

describe('ShoppingAmountView: finish sheet with methods (mockup, dev-fix2)', () => {
  it('is a sheet (dialog) with title, close, caption and the three tabs when the photo flag is on', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} />)
    expect(html).toContain('role="dialog"')
    expect(html).toContain('Завершить закупку')
    expect(html).toContain('aria-label="Закрыть"')
    expect(html).toContain('Одна сумма на всю закупку. Отмечено товаров: 3')
    expect(html).toMatch(/role="tab"[^>]*>Вручную</)
    expect(html).toMatch(/role="tab"[^>]*>Фото чека</)
    expect(html).toMatch(/role="tab"[^>]*>Голос</)
  })
  it('tab order is Вручную, Фото чека, Голос; manual is selected first', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} />)
    expect(html.indexOf('>Вручную<')).toBeLessThan(html.indexOf('>Фото чека<'))
    expect(html.indexOf('>Фото чека<')).toBeLessThan(html.indexOf('>Голос<'))
    expect(html).toMatch(/aria-selected="true"[^>]*>Вручную</)
  })
  it('photo tab hidden when the flag is off; voice stays', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} photoEnabled={false} />)
    expect(html).not.toContain('Фото чека')
    expect(html).not.toContain('Отправить фото чека')
    expect(html).toContain('>Голос<')
  })
  it('manual tab: label, field, Записать, summary; no bot hint', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} />)
    expect(html).toContain('Сумма закупки')
    expect(html).toContain('Записать')
    expect(html).toContain('Категория')
    expect(html).toContain('Кошелёк')
    expect(html).not.toContain('свернётся')
    expect(html).not.toContain('Отправить фото чека')
  })
  it('receipt tab: hint and «Отправить фото чека», no amount field', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} initialMethod="receipt" />)
    expect(html).toContain('Приложение свернётся, бот ждёт фото чека. Сумма вернётся сюда.')
    expect(html).toContain('Отправить фото чека')
    expect(html).not.toContain('Записать')
    expect(html).toContain('Категория')
  })
  it('voice tab: hint and «Сказать сумму голосом»', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} initialMethod="voice" />)
    expect(html).toContain('Приложение свернётся, бот ждёт голосовое. Сумма вернётся сюда.')
    expect(html).toContain('Сказать сумму голосом')
    expect(html).not.toContain('Отправить фото чека')
  })
  it('photo method is never shown when the flag is off, even if asked', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} photoEnabled={false} initialMethod="receipt" />)
    expect(html).not.toContain('Отправить фото чека')
    expect(html).toContain('Записать')
  })
  it('Uzbek labels', () => {
    const html = wrap(<ShoppingAmountView {...amountProps} initialMethod="receipt" />, 'uz')
    expect(html).toContain('Qo&#x27;lda')
    expect(html).toContain('Chek yuboraman')
    expect(html).toContain('Ovoz orqali')
    expect(html).toContain('Xaridni yakunlash')
  })
})

const cancelProps = { onCancelPurchase: noop, cancelBusy: false, cancelFailed: false }
const manualProps = {
  method: 'receipt' as const, status: 'unrecognized' as const, amount: '', overLimit: false, currencySuffix: 'сум', busy: false,
  failed: false, canRetry: true, onAmount: noop, onOverLimit: noop, onSubmit: noop,
  onRetry: noop, onCancel: noop, ...cancelProps,
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
    const r = wrap(<ShoppingWaitingBanner method="receipt" status="awaiting" onManual={noop} {...cancelProps} />)
    expect(r).toContain('Ждём фото чека в боте')
    expect(r).toContain('Ввести сумму вручную')
    const v = wrap(<ShoppingWaitingBanner method="voice" status="awaiting" onManual={noop} {...cancelProps} />)
    expect(v).toContain('Ждём голосовое в боте')
  })
  it('Uzbek', () => {
    const html = wrap(<ShoppingWaitingBanner method="receipt" status="awaiting" onManual={noop} {...cancelProps} />, 'uz')
    expect(html).toContain('Botda chek rasmini kutyapmiz')
    expect(html).toContain('Summani qo&#x27;lda kiritish')
  })
  it('unrecognized: no «waiting» text, only the manual entry', () => {
    const html = wrap(<ShoppingWaitingBanner method="receipt" status="unrecognized" onManual={noop} {...cancelProps} />)
    expect(html).not.toContain('Ждём')
    expect(html).toContain('Ввести сумму вручную')
  })
})

describe('cancel purchase (dev-fix5)', () => {
  it('manual view: secondary cancel button, then an explicit confirmation', async () => {
    const { ShoppingCancelPurchase } = await import('./ShoppingCancelPurchase')
    const html = wrap(<ShoppingManualView {...manualProps} onCancelPurchase={noop} cancelBusy={false} cancelFailed={false} />)
    expect(html).toContain('Отменить закупку')
    const confirm = wrap(<ShoppingCancelPurchase onConfirm={noop} busy={false} failed={false} initialConfirming />)
    expect(confirm).toContain('Да, отменить')
    expect(confirm).toContain('role="alertdialog"')
    expect(wrap(<ShoppingCancelPurchase onConfirm={noop} busy={false} failed />)).toContain('role="alert"')
    expect(wrap(<ShoppingCancelPurchase onConfirm={noop} busy={false} failed={false} initialConfirming />, 'uz')).not.toContain('Да,')
  })
  it('waiting banner has the cancel too', () => {
    const html = wrap(<ShoppingWaitingBanner method="voice" status="awaiting" onManual={noop} onCancelPurchase={noop} cancelBusy={false} cancelFailed={false} />)
    expect(html).toContain('Отменить закупку')
  })
})
