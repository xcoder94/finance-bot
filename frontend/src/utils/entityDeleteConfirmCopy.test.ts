import { describe, expect, it } from 'vitest'

import {
  buildEntityDeleteTitle,
  buildIncomeCategoryDeleteIntro,
  buildSubcategoryDeleteIntro,
  buildWalletDeleteIntro,
  CATEGORY_DELETE_DANGER_LABEL,
  formatEntityTransactionSubtitle,
  SUBCATEGORY_DELETE_DANGER_LABEL,
  WALLET_DELETE_DANGER_LABEL,
} from './entityDeleteConfirmCopy'

describe('entity delete confirm copy', () => {
  it('builds title with quoted entity name', () => {
    expect(buildEntityDeleteTitle('Тои и маърака')).toBe('Удалить «Тои и маърака»?')
  })

  it('builds wallet intro for zero transactions', () => {
    expect(buildWalletDeleteIntro(0)).toBe('Кошелёк удалится. Отменить нельзя.')
  })

  it('builds wallet intro for multiple transactions', () => {
    expect(buildWalletDeleteIntro(3)).toBe(
      'Кошелёк удалится, а 3 операции останутся в истории и аналитике. Отменить нельзя.',
    )
  })

  it('uses singular verb for one transaction', () => {
    expect(buildWalletDeleteIntro(1)).toBe(
      'Кошелёк удалится, а 1 операция останется в истории и аналитике. Отменить нельзя.',
    )
  })

  it('exports wallet danger label', () => {
    expect(WALLET_DELETE_DANGER_LABEL).toBe('Удалить кошелёк')
  })

  it('exports category danger labels', () => {
    expect(CATEGORY_DELETE_DANGER_LABEL).toBe('Удалить категорию')
    expect(SUBCATEGORY_DELETE_DANGER_LABEL).toBe('Удалить подкатегорию')
  })

  it('formats entity transaction subtitle', () => {
    expect(formatEntityTransactionSubtitle(0)).toBe('нет операций')
    expect(formatEntityTransactionSubtitle(3)).toBe('3 операции')
  })

  it('builds income category delete intro', () => {
    expect(buildIncomeCategoryDeleteIntro(0)).toBe('Категория удалится. Отменить нельзя.')
    expect(buildIncomeCategoryDeleteIntro(2)).toBe(
      'Категория удалится, а 2 операции останутся в истории и аналитике. Отменить нельзя.',
    )
  })

  it('builds subcategory delete intro with parent interpolation', () => {
    expect(buildSubcategoryDeleteIntro(3, 'События и тои', 2026)).toBe(
      'Подкатегория удалится, а 3 операции за 2026 год останутся в родительской категории «События и тои». Отменить нельзя.',
    )
  })
})
