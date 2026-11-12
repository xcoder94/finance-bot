import { describe, expect, it, vi, beforeEach } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'

// Effects do not run in server rendering: run them inline and remember the cleanups.
const cleanups: Array<() => void> = []
vi.mock('react', async () => {
  const actual = await vi.importActual<typeof import('react')>('react')
  return {
    ...actual,
    useEffect: (fn: () => void | (() => void)) => {
      const c = fn()
      if (typeof c === 'function') cleanups.push(c)
    },
  }
})
vi.mock('../../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('../../api/shopping', async () => {
  const actual = await vi.importActual<typeof import('../../api/shopping')>('../../api/shopping')
  return { ...actual, listShoppingItems: vi.fn().mockResolvedValue([]) }
})
vi.mock('../../api/transactions', async () => {
  const actual = await vi.importActual<typeof import('../../api/transactions')>('../../api/transactions')
  return { ...actual, fetchWallets: vi.fn().mockResolvedValue([]), fetchExpenseCategories: vi.fn().mockResolvedValue([]) }
})

import ru from '../../i18n/locales/ru.json'
import { listShoppingItems } from '../../api/shopping'
import { ShoppingTripPage } from '../../pages/ShoppingTripPage'
import { useChromeStore } from '../../store/chromeStore'
import { ShoppingResultView } from './ShoppingResultView'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})
const wrap = (node: React.ReactNode) =>
  renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <MemoryRouter>{node}</MemoryRouter>
    </I18nextProvider>,
  )

beforeEach(() => {
  cleanups.length = 0
  useChromeStore.setState({ tabbarHidden: false })
})

describe('ShoppingTripPage', () => {
  it('hides the bottom menu while open and brings it back on leaving', () => {
    const html = wrap(<ShoppingTripPage />)
    expect(html).toContain('Закупка')
    expect(useChromeStore.getState().tabbarHidden).toBe(true)
    cleanups.forEach((c) => c())
    expect(useChromeStore.getState().tabbarHidden).toBe(false)
  })

  it('reads the list when opened', () => {
    wrap(<ShoppingTripPage />)
    expect(listShoppingItems).toHaveBeenCalled()
  })
})

describe('ShoppingResultView (recorded vs ticked)', () => {
  const purchase = {
    id: 'p', transaction_id: 't', items_recorded: 1, amount: 10000, currency: 'UZS',
    category_label: 'Еда', wallet_name: 'Карта сум', remaining: 5, items_left: 0,
  }
  it('title counts items RECORDED by the server, not ticked; notes the lost one', () => {
    const html = wrap(
      <ShoppingResultView purchase={purchase} requested={3} categoryLabel={null} walletLabel="Карта сум" onDone={() => {}} />,
    )
    expect(html).toContain('Записан 1 товар')
    expect(html).not.toContain('Записано 3')
    expect(html).toContain('Эти позиции уже купил кто-то из семьи.')
  })
  it('nothing recorded but the sum was written: says so honestly, not "recorded 0 items"', () => {
    const html = wrap(
      <ShoppingResultView purchase={{ ...purchase, items_recorded: 0 }} requested={2} categoryLabel={null} walletLabel={null} onDone={() => {}} />,
    )
    expect(html).not.toContain('Записано 0')
    expect(html).toContain('Расход записан, но ни одна позиция не отмечена купленной')
    expect(html).toContain('Этих позиций нет в списке вашей семьи')
  })
})
