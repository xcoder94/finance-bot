import { describe, expect, it } from 'vitest'

import i18n from '../i18n'

import { formatCurrency } from './formatCurrency'
import { groupThousands } from './groupThousands'

describe('formatCurrency wrapping', () => {
  it('amount and unit are one unbreakable unit (no plain space)', async () => {
    await i18n.changeLanguage('uz')
    const text = formatCurrency(12_400_000, 'UZS')
    expect(text).toBe("12\u00a0400\u00a0000\u00a0so'm")
    expect(text).not.toContain(' ')
    await i18n.changeLanguage('ru')
    const big = formatCurrency(2_002_658_999, 'UZS')
    expect(big).toBe('2\u00a0002\u00a0658\u00a0999\u00a0сум')
    expect(big).not.toContain(' ')
  })
  it('RU and negative numbers behave the same', async () => {
    await i18n.changeLanguage('ru')
    expect(formatCurrency(-3_450_000, 'UZS')).toBe('-3 450 000 сум')
    expect(formatCurrency(1_500, 'USD')).toBe('$1 500')
  })
  it('groupThousands leaves short numbers alone', () => {
    expect(groupThousands(999)).toBe('999')
    expect(groupThousands('1000')).toBe('1 000')
  })
})
