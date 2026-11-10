import i18next from 'i18next'
import { afterEach, describe, expect, it } from 'vitest'

import '../i18n/init'
import {
  getDisplayName,
  resolveCategoryAmountDisplayName,
  resolveStoredEntityDisplayName,
  resolveSubcategoryAmountDisplayName,
  getHistoryItemMeta,
  getHistoryItemTitle,
} from './getDisplayName'
import type { HistoryItem } from '../api/home'

// dev-fix9: backend keeps translation_key after a rename, so a renamed default wallet or category
// must still show the user's own name (not the localized default).
describe('display name of default entities', () => {
  afterEach(async () => {
    await i18next.changeLanguage('ru')
  })

  it('shows the localized default while the name is still a default', async () => {
    await i18next.changeLanguage('uz')
    expect(getDisplayName({ name: 'Наличный сум', translation_key: 'cash_uzs' }, i18next.t)).toBe(
      i18next.t('defaultEntities.cash_uzs'),
    )
    expect(getDisplayName({ name: "Naqd so'm", translation_key: 'cash_uzs' }, i18next.t)).toBe(
      i18next.t('defaultEntities.cash_uzs'),
    )
  })

  it('shows the user name when the default entity was renamed', () => {
    expect(getDisplayName({ name: 'Карта-новая', translation_key: 'card_uzs' }, i18next.t)).toBe('Карта-новая')
    expect(resolveStoredEntityDisplayName('Моя аренда', 'rent', i18next.t)).toBe('Моя аренда')
  })

  it('entities without key keep their name', () => {
    expect(getDisplayName({ name: 'X', translation_key: null }, i18next.t)).toBe('X')
  })
})

// dev-fix11: analytics amounts must follow the same rule (renamed default shows the user's name).
describe('analytics amount names', () => {
  it('category: renamed default keeps the user name, untouched default is localized', () => {
    const base = { category_id: 'c1', category_translation_key: 'rent' }
    expect(resolveCategoryAmountDisplayName({ ...base, category_name: 'Моя аренда' }, undefined, i18next.t)).toBe('Моя аренда')
    expect(resolveCategoryAmountDisplayName({ ...base, category_name: 'Моя аренда' }, new Map([['c1', 'Моя аренда']]), i18next.t)).toBe('Моя аренда')
    expect(resolveCategoryAmountDisplayName({ ...base, category_name: 'Аренда' }, undefined, i18next.t)).toBe(i18next.t('defaultEntities.rent'))
  })
  it('subcategory: same rule', () => {
    const base = { subcategory_id: 's1', subcategory_translation_key: 'rent' }
    expect(resolveSubcategoryAmountDisplayName({ ...base, subcategory_name: 'Мой угол' }, undefined, i18next.t)).toBe('Мой угол')
    expect(resolveSubcategoryAmountDisplayName({ ...base, subcategory_name: 'Аренда' }, undefined, i18next.t)).toBe(i18next.t('defaultEntities.rent'))
  })
})

// import-xlsx: entities created by the Excel import carry xls_* keys and must localize like seeded ones.
describe('xls_* import entities', () => {
  afterEach(async () => {
    await i18next.changeLanguage('ru')
  })

  const cases = [
    { key: 'xls_cigarettes', ru: 'Сигареты', uz: 'Sigaretlar' },
    { key: 'xls_archive', ru: 'Архив Excel', uz: 'Excel arxivi' },
    { key: 'xls_opening_balance', ru: 'Начальный остаток', uz: "Boshlang'ich qoldiq" },
    { key: 'xls_education', ru: 'Образование', uz: "Ta'lim" },
  ]

  for (const c of cases) {
    it(`${c.key} shows ru and uz translation`, async () => {
      await i18next.changeLanguage('ru')
      expect(getDisplayName({ name: c.ru, translation_key: c.key }, i18next.t)).toBe(c.ru)
      await i18next.changeLanguage('uz')
      expect(getDisplayName({ name: c.ru, translation_key: c.key }, i18next.t)).toBe(c.uz)
    })

    it(`${c.key} renamed keeps the user name`, async () => {
      await i18next.changeLanguage('uz')
      expect(getDisplayName({ name: 'Моё имя', translation_key: c.key }, i18next.t)).toBe('Моё имя')
    })
  }
})

describe('record without category (B4)', () => {
  afterEach(async () => {
    await i18next.changeLanguage('ru')
  })
  const base = {
    id: 'x', type: 'expense', amount: 1, currency: 'UZS', created_by: null,
    wallet_name: 'Карта', wallet_translation_key: null,
    expense_category_name: null, expense_category_translation_key: null,
    expense_subcategory_name: null, expense_subcategory_translation_key: null,
    income_category_name: null, income_category_translation_key: null,
  } as unknown as HistoryItem
  const labels = { transfer: 'T', exchange: 'E' }

  it('RU: never a dash', async () => {
    await i18next.changeLanguage('ru')
    expect(getHistoryItemTitle(base, labels, i18next.t)).toBe('Без категории')
    expect(getHistoryItemMeta(base, i18next.t)).toBe('Карта')
    const income = { ...base, type: 'income' } as HistoryItem
    expect(getHistoryItemTitle(income, labels, i18next.t)).toBe('Без категории')
    expect(getHistoryItemMeta(income, i18next.t)).not.toContain('—')
    expect(getHistoryItemMeta(income, i18next.t)).not.toContain('Без категории')
  })
  it('UZ', async () => {
    await i18next.changeLanguage('uz')
    expect(getHistoryItemTitle(base, labels, i18next.t)).toBe('Toifasiz')
    expect(getHistoryItemMeta(base, i18next.t)).toBe('Карта')
  })
})
