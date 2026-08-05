import { describe, expect, it } from 'vitest'

import {
  countExpenseParents,
  countExpenseSubcategories,
  countNonProtectedExpenseParents,
  countPersonalWallets,
  countSharedWallets,
  defaultWalletSubtitle,
  expenseCategoriesSubtitle,
  formatWalletSettingsSubtitle,
  incomeCategoriesSubtitle,
  languageSubtitle,
  membersSubtitle,
  notificationsSubtitle,
  walletsSubtitle,
} from './settingsSubtitles'

describe('settingsSubtitles', () => {
  it('formats wallets subtitle', () => {
    expect(walletsSubtitle(4, 2)).toBe('4 общих · 2 личных')
    expect(walletsSubtitle(3, 0)).toBe('3 общих · 0 личных')
  })

  it('formats default wallet subtitle', () => {
    expect(defaultWalletSubtitle('Карта Humo — основная')).toBe('Карта Humo — основная')
    expect(defaultWalletSubtitle(null)).toBe('—')
    expect(defaultWalletSubtitle(undefined)).toBe('—')
  })

  it('formats wallet settings subtitle with balance and active goal mark', () => {
    expect(formatWalletSettingsSubtitle('UZS', 840_000, false)).toBe('UZS · 840 000 сум')
    expect(formatWalletSettingsSubtitle('USD', 1_240, false)).toBe('USD · $1 240')
    expect(formatWalletSettingsSubtitle('UZS', 2_350_000, true)).toBe(
      'UZS · 2 350 000 сум · цель',
    )
    expect(formatWalletSettingsSubtitle('USD', 1_240, true)).toBe('USD · $1 240 · цель')
    expect(formatWalletSettingsSubtitle('UZS', 0, false)).toBe('UZS · 0 сум')
  })

  it('formats income categories subtitle with Russian plural forms', () => {
    expect(incomeCategoriesSubtitle(1)).toBe('1 категория')
    expect(incomeCategoriesSubtitle(2)).toBe('2 категории')
    expect(incomeCategoriesSubtitle(5)).toBe('5 категорий')
    expect(incomeCategoriesSubtitle(21)).toBe('21 категория')
  })

  it('formats expense categories subtitle with Russian plural forms', () => {
    expect(expenseCategoriesSubtitle(7, 23)).toBe('7 родительских · 23 подкатегории')
    expect(expenseCategoriesSubtitle(1, 1)).toBe('1 родительских · 1 подкатегория')
    expect(expenseCategoriesSubtitle(8, 5)).toBe('8 родительских · 5 подкатегорий')
  })

  it('formats members subtitle', () => {
    expect(membersSubtitle(2)).toBe('2 из 4')
    expect(membersSubtitle(3)).toBe('3 из 4')
  })

  it('formats notifications subtitle from enabled prefs', () => {
    expect(notificationsSubtitle(true, true)).toBe('Напоминание вечером · Итоги недели')
    expect(notificationsSubtitle(false, false)).toBe('Выключены')
    expect(notificationsSubtitle(true, false)).toBe('Напоминание вечером')
    expect(notificationsSubtitle(false, true)).toBe('Итоги недели')
  })

  it('formats language subtitle', () => {
    expect(languageSubtitle('ru')).toBe('Русский')
    expect(languageSubtitle('uz')).toBe('Oʻzbekcha')
    expect(languageSubtitle('uz-Latn')).toBe('Oʻzbekcha')
  })

  it('counts wallet types from is_personal', () => {
    const wallets = [
      { is_personal: false },
      { is_personal: false },
      { is_personal: true },
    ]
    expect(countSharedWallets(wallets)).toBe(2)
    expect(countPersonalWallets(wallets)).toBe(1)
    expect(countSharedWallets([{}])).toBe(1)
  })

  it('counts expense parent and subcategory rows', () => {
    const categories = [
      { parent_id: null },
      { parent_id: null },
      { parent_id: 'a' },
      { parent_id: 'a' },
      { parent_id: 'b' },
    ]
    expect(countExpenseParents(categories)).toBe(2)
    expect(countExpenseSubcategories(categories)).toBe(3)
  })

  it('counts only non-protected expense parents for limit UI', () => {
    const categories = [
      { parent_id: null, is_protected: true },
      { parent_id: null, is_protected: true },
      { parent_id: null, is_protected: false },
      { parent_id: null },
      { parent_id: 'a' },
    ]
    expect(countNonProtectedExpenseParents(categories)).toBe(2)
  })
})
