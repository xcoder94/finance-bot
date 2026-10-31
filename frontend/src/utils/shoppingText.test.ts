import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import ru from '../i18n/locales/ru.json'
import uz from '../i18n/locales/uz.json'
import { MAX_SHOPPING_NAME, normalizeShoppingName } from './shoppingText'

const inst = i18n.createInstance()
void inst.init({ resources: { ru: { translation: ru }, uz: { translation: uz } }, lng: 'ru' })

describe('shopping count label', () => {
  it('RU plural forms', () => {
    const f = (n: number) => inst.t('shopping.count', { count: n, lng: 'ru' })
    expect([1, 2, 3, 4, 5, 9, 11, 12, 21, 22, 25, 100, 101].map(f)).toEqual([
      '1 позиция', '2 позиции', '3 позиции', '4 позиции', '5 позиций', '9 позиций',
      '11 позиций', '12 позиций', '21 позиция', '22 позиции', '25 позиций', '100 позиций',
      '101 позиция',
    ])
  })
  it('UZ has one form', () => {
    expect(inst.t('shopping.count', { count: 9, lng: 'uz' })).toBe('9 ta pozitsiya')
    expect(inst.t('shopping.count', { count: 1, lng: 'uz' })).toBe('1 ta pozitsiya')
  })
})

describe('normalizeShoppingName', () => {
  it('trims and collapses whitespace', () => {
    expect(normalizeShoppingName('  Чай   чёрный \n')).toBe('Чай чёрный')
  })
  it('clips to 60 characters, counting emoji as one', () => {
    expect(Array.from(normalizeShoppingName('я'.repeat(80))).length).toBe(MAX_SHOPPING_NAME)
    expect(Array.from(normalizeShoppingName('🥛'.repeat(61))).length).toBe(MAX_SHOPPING_NAME)
  })
})

describe('strings', () => {
  it('every shopping key exists in both languages', () => {
    const keys = (o: Record<string, unknown>) => Object.keys(o).map((k) => k.replace(/_(one|few|many|other)$/, ''))
    const norm = (o: Record<string, unknown>) => [...new Set(keys(o))].sort()
    expect(norm(uz.shopping)).toEqual(norm(ru.shopping))
  })
})
