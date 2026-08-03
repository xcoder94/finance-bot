import { describe, expect, it, vi } from 'vitest'

import {
  buildEditSheetTitle,
  buildExpenseCategoryDisplayLabel,
  filterUncategorizedCategories,
  formatCommentCounter,
  formatTransferResultLine,
  isCommentTooLong,
  isTransferCrossCurrency,
  MAX_COMMENT_LENGTH,
  nowMaskedDateInTashkent,
  resolveDefaultWalletId,
  resolveEditSheetLabel,
  shouldShowTransferRateField,
  transferRateFieldSuffix,
  UNCATEGORIZED_CATEGORY_NAME,
  walletCurrencySuffix,
} from './transactionFormFields'

describe('formatCommentCounter', () => {
  it('formats length out of max', () => {
    expect(formatCommentCounter(18)).toBe('18 / 200')
    expect(formatCommentCounter(0)).toBe('0 / 200')
  })
})

describe('isCommentTooLong', () => {
  it('rejects comments over 200 characters', () => {
    expect(isCommentTooLong('a'.repeat(200))).toBe(false)
    expect(isCommentTooLong('a'.repeat(201))).toBe(true)
  })
})

describe('filterUncategorizedCategories', () => {
  it('removes Без категории from lists', () => {
    const categories = [
      { id: '1', name: 'Еда' },
      { id: '2', name: UNCATEGORIZED_CATEGORY_NAME },
      { id: '3', name: 'Транспорт' },
    ]

    expect(filterUncategorizedCategories(categories)).toEqual([
      { id: '1', name: 'Еда' },
      { id: '3', name: 'Транспорт' },
    ])
  })
})

describe('buildExpenseCategoryDisplayLabel', () => {
  it('joins parent and subcategory with middle dot', () => {
    expect(buildExpenseCategoryDisplayLabel('Еда', 'Продукты')).toBe('Еда · Продукты')
  })

  it('returns parent name alone when no subcategory', () => {
    expect(buildExpenseCategoryDisplayLabel('Еда', null)).toBe('Еда')
    expect(buildExpenseCategoryDisplayLabel('Еда', undefined)).toBe('Еда')
  })
})

describe('walletCurrencySuffix', () => {
  it('maps wallet currency to design labels', () => {
    expect(walletCurrencySuffix('UZS')).toBe('сум')
    expect(walletCurrencySuffix('USD')).toBe('$')
  })
})

describe('resolveDefaultWalletId', () => {
  const wallets = [{ id: 'w1' }, { id: 'w2' }]

  it('prefers default wallet when present in list', () => {
    expect(resolveDefaultWalletId(wallets, 'w2')).toBe('w2')
  })

  it('falls back to first wallet when default is missing', () => {
    expect(resolveDefaultWalletId(wallets, 'missing')).toBe('w1')
    expect(resolveDefaultWalletId(wallets, null)).toBe('w1')
  })
})

describe('nowMaskedDateInTashkent', () => {
  it('returns masked date for Asia/Tashkent', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-03T10:00:00.000Z'))

    expect(nowMaskedDateInTashkent()).toBe('03.08.2026')

    vi.useRealTimers()
  })
})

describe('MAX_COMMENT_LENGTH', () => {
  it('is 200', () => {
    expect(MAX_COMMENT_LENGTH).toBe(200)
  })
})

describe('isTransferCrossCurrency', () => {
  it('is false when currencies match', () => {
    expect(isTransferCrossCurrency('UZS', 'UZS')).toBe(false)
    expect(isTransferCrossCurrency('USD', 'USD')).toBe(false)
  })

  it('is true when currencies differ', () => {
    expect(isTransferCrossCurrency('USD', 'UZS')).toBe(true)
    expect(isTransferCrossCurrency('UZS', 'USD')).toBe(true)
  })

  it('is false when either currency is missing', () => {
    expect(isTransferCrossCurrency(null, 'UZS')).toBe(false)
    expect(isTransferCrossCurrency('UZS', undefined)).toBe(false)
  })
})

describe('shouldShowTransferRateField', () => {
  it('mirrors cross-currency detection', () => {
    expect(shouldShowTransferRateField('USD', 'UZS')).toBe(true)
    expect(shouldShowTransferRateField('UZS', 'UZS')).toBe(false)
  })
})

describe('formatTransferResultLine', () => {
  it('formats USD to UZS like design', () => {
    expect(formatTransferResultLine(100, 'USD', 1_280_000, 'UZS')).toBe(
      '100 $ → 1 280 000 сум',
    )
  })

  it('formats UZS to USD', () => {
    expect(formatTransferResultLine(1_280_000, 'UZS', 100, 'USD')).toBe(
      '1 280 000 сум → 100 $',
    )
  })
})

describe('transferRateFieldSuffix', () => {
  it('returns design label', () => {
    expect(transferRateFieldSuffix()).toBe('сум за $1')
  })
})

describe('buildEditSheetTitle', () => {
  it('prefixes record label', () => {
    expect(buildEditSheetTitle('Продукты на неделю')).toBe('Запись · Продукты на неделю')
  })
})

describe('resolveEditSheetLabel', () => {
  it('prefers trimmed comment', () => {
    expect(resolveEditSheetLabel('  Такси  ', 'Транспорт')).toBe('Такси')
  })

  it('falls back to category label when comment empty', () => {
    expect(resolveEditSheetLabel('', 'Транспорт · Такси')).toBe('Транспорт · Такси')
    expect(resolveEditSheetLabel(null, 'Зарплата')).toBe('Зарплата')
  })
})
