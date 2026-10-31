import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'

vi.mock('../../i18n', () => ({ default: { language: 'ru' } }))

import ru from '../../i18n/locales/ru.json'
import { ShoppingAmountView } from './ShoppingAmountView'
import { ShoppingResultView } from './ShoppingResultView'
import { ShoppingTripView } from './ShoppingTripView'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})
const wrap = (node: React.ReactNode) =>
  renderToStaticMarkup(<I18nextProvider i18n={testI18n}>{node}</I18nextProvider>)
const noop = () => {}
const mk = (id: string, name: string) => ({ id, name, created_at: '2026-10-31T10:00:00Z' })

describe('ShoppingTripView', () => {
  const items = [mk('1', 'Молоко'), mk('2', 'Хлеб'), mk('3', 'Яйца')]

  it('title, checkboxes with aria-checked, counter, bar buttons', () => {
    const html = wrap(
      <ShoppingTripView items={items} checked={new Set(['2'])} popId={null} onToggle={noop} onCancel={noop} onFinish={noop} />,
    )
    expect(html).toContain('Закупка')
    expect(html.match(/role="checkbox"/g)).toHaveLength(3)
    expect(html.match(/aria-checked="true"/g)).toHaveLength(1)
    expect(html).toContain('1 / 3')
    expect(html).toContain('Отменить')
    expect(html).toContain('Завершить закупку')
  })

  it('finish disabled with nothing checked, enabled otherwise', () => {
    const none = wrap(
      <ShoppingTripView items={items} checked={new Set()} popId={null} onToggle={noop} onCancel={noop} onFinish={noop} />,
    )
    expect(none).toMatch(/<button[^>]*disabled[^>]*>Завершить закупку/)
    const some = wrap(
      <ShoppingTripView items={items} checked={new Set(['1'])} popId={null} onToggle={noop} onCancel={noop} onFinish={noop} />,
    )
    expect(some).not.toMatch(/<button[^>]*disabled[^>]*>Завершить закупку/)
  })
})

describe('ShoppingAmountView', () => {
  const base = {
    count: 6, amount: '412000', overLimit: false, currencySuffix: 'сум',
    categoryLabel: 'Еда · Продукты', walletLabel: 'Карта Humo',
    busy: false, failed: false, noWallet: false,
    onAmount: noop, onOverLimit: noop, onSubmit: noop, onBack: noop,
    photoEnabled: false, botMethod: null as 'receipt' | 'voice' | null, onBotMethod: noop,
  }

  it('title, caption with N, read-only rows, currency, record button; photo way hidden while the flag is off (m3-4)', () => {
    const html = wrap(<ShoppingAmountView {...base} />)
    expect(html).toContain('Сумма закупки')
    expect(html).toContain('Одна сумма на всю закупку. Отмечено товаров: 6')
    expect(html).toContain('Категория')
    expect(html).toContain('Еда · Продукты')
    expect(html).toContain('Кошелёк')
    expect(html).toContain('Карта Humo')
    expect(html).toContain('сум')
    expect(html).toContain('Записать')
    expect(html).not.toMatch(/фото/i)
  })

  it('record disabled on empty amount, enabled with digits', () => {
    expect(wrap(<ShoppingAmountView {...base} amount="" />)).toMatch(/<button[^>]*disabled[^>]*>Записать/)
    expect(wrap(<ShoppingAmountView {...base} />)).not.toMatch(/<button[^>]*disabled[^>]*>Записать/)
  })

  it('failure shows the neutral text from strings and keeps the button for a retry', () => {
    const html = wrap(<ShoppingAmountView {...base} failed />)
    expect(html).toContain('Не получилось записать. Повторите.')
    expect(html).not.toMatch(/ошибк|сервер|токен|запрос|сесси/i)
    expect(html).not.toMatch(/<button[^>]*disabled[^>]*>Записать/)
  })
})

describe('ShoppingResultView', () => {
  const purchase = {
    id: 'p', transaction_id: 't', items_recorded: 6, amount: 412000, currency: 'UZS',
    category_label: 'Еда · Продукты', wallet_name: 'Карта Humo', remaining: 3038000, items_left: 3,
  }

  it('shows N from the API, amount, remaining, caption with K', () => {
    const html = wrap(<ShoppingResultView purchase={purchase} categoryLabel={null} walletLabel={null} onDone={noop} />)
    expect(html).toContain('Записано 6 товаров')
    expect(html).toContain('−412 000 сум')
    expect(html).toContain('3 038 000 сум')
    expect(html).toContain('осталось')
    expect(html).toContain('Еда · Продукты · Карта Humo')
    expect(html).toContain('Купленные позиции ушли из списка, неотмеченные (3) остались.')
    expect(html).toContain('Готово')
  })

  it('plural of recorded items and the already-bought note', () => {
    const one = wrap(<ShoppingResultView purchase={{ ...purchase, items_recorded: 1 }} categoryLabel={null} walletLabel={null} onDone={noop} />)
    expect(one).toContain('Записан 1 товар')
    const lost = wrap(<ShoppingResultView purchase={{ ...purchase, items_recorded: 4 }} requested={6} categoryLabel={null} walletLabel={null} onDone={noop} />)
    expect(lost).toContain('Эти позиции уже купил кто-то из семьи.')
  })
})
