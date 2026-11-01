import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'

import ru from '../i18n/locales/ru.json'
import uz from '../i18n/locales/uz.json'
import { ShoppingListView } from '../components/shopping/ShoppingListView'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru }, uz: { translation: uz } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})

const noop = () => {}
const mk = (id: string, name: string) => ({ id, name, created_at: '2026-10-31T10:00:00Z' })

function render(props: Partial<React.ComponentProps<typeof ShoppingListView>>, lng = 'ru'): string {
  const inst = testI18n.cloneInstance({ lng })
  return renderToStaticMarkup(
    <I18nextProvider i18n={inst}>
      <ShoppingListView
        status="ready"
        items={[]}
        onRetry={noop}
        onAdd={async () => 'added'}
        onEdit={noop}
        onDelete={noop}
        onStart={noop}
        {...props}
      />
    </I18nextProvider>,
  )
}

describe('ShoppingListView', () => {
  it('list: title, counter, names, no checkboxes, start button', () => {
    const html = render({ items: [mk('1', 'Молоко'), mk('2', 'Хлеб'), mk('3', 'Яйца')] })
    expect(html).toContain('Покупки')
    expect(html).toContain('3 позиции')
    expect(html).toContain('Молоко')
    expect(html).not.toContain('checkbox')
    expect(html).toContain('Начать закупку')
    expect(html).toContain('+ добавить')
  })

  it('counter plural: 1 / 5', () => {
    expect(render({ items: [mk('1', 'a')] })).toContain('1 позиция')
    expect(render({ items: ['a', 'b', 'c', 'd', 'e'].map((n) => mk(n, n)) })).toContain('5 позиций')
  })

  it('empty: message + bot hint, no start button, no counter', () => {
    const html = render({ items: [] })
    expect(html).toContain('Список покупок')
    expect(html).toContain(
      'Здесь можно вести список покупок на день, неделю или месяц. Добавьте товары, а в магазине отмечайте купленное. Или напишите боту: «молоко, хлеб, яйца».',
    )
    expect(html).not.toContain('Начать закупку')
    expect(html).not.toMatch(/\d+ позиц/)
    expect(html).toContain('+ добавить')
  })

  it('empty UZ: info card in Uzbek', () => {
    const html = render({ items: [] }, 'uz').replaceAll('&#x27;', "'")
    expect(html).toContain("Xaridlar ro'yxati")
    expect(html).toContain(
      "Bu yerda kun, hafta yoki oy uchun xaridlar ro'yxatini yuritishingiz mumkin. Mahsulotlarni qo'shing, do'konda esa sotib olinganlarini belgilang. Yoki botga yozing: «sut, non, tuxum».",
    )
  })

  it('has items: no info card', () => {
    const html = render({ items: [mk('1', 'Молоко')] })
    expect(html).not.toContain('Здесь можно вести список покупок')
    expect(html).not.toContain('goals-page__empty')
  })

  it('skeleton: busy, no start button, no empty text', () => {
    const html = render({ status: 'loading', items: [] })
    expect(html).toContain('aria-busy="true"')
    expect(html).not.toContain('Здесь можно вести список покупок')
    expect(html).not.toContain('Начать закупку')
  })

  it('loading with already known items shows the items, not the skeleton', () => {
    const html = render({ status: 'loading', items: [mk('1', 'Молоко')] })
    expect(html).toContain('Молоко')
    expect(html).not.toContain('aria-busy="true"')
  })

  it('fail: load error with retry, no list', () => {
    const html = render({ status: 'error', items: [] })
    expect(html).toContain('Не удалось загрузить данные')
    expect(html).toContain('Повторить')
    expect(html).not.toContain('Начать закупку')
  })

  it('long name goes into an ellipsis container (single line)', () => {
    const html = render({ items: [mk('1', 'Подгузники для младшего, размер 4, большая упаковка')] })
    expect(html).toContain('shopping-row__name')
  })

  it('rows expose Изменить and Удалить swipe actions', () => {
    const html = render({ items: [mk('1', 'Молоко')] })
    expect(html).toContain('Изменить')
    expect(html).toContain('Удалить')
  })
})
