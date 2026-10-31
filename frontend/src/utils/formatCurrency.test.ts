import { describe, expect, it } from 'vitest'

import i18n from '../i18n'

import { formatCurrency } from './formatCurrency'
import { groupThousands } from './groupThousands'

describe('formatCurrency wrapping', () => {
  it('keeps the digits of one number together (NBSP) and breaks only before the unit', async () => {
    await i18n.changeLanguage('uz')
    const text = formatCurrency(12_400_000, 'UZS')
    expect(text).toBe("12 400 000 so'm")
    expect(text.split(' ')).toEqual(["12 400 000", "so'm"])
  })
  it('RU and negative numbers behave the same', async () => {
    await i18n.changeLanguage('ru')
    expect(formatCurrency(-3_450_000, 'UZS')).toBe('-3 450 000 сум')
    expect(formatCurrency(1_500, 'USD')).toBe('$1 500')
  })
  it('groupThousands leaves short numbers alone', () => {
    expect(groupThousands(999)).toBe('999')
    expect(groupThousands('1000')).toBe('1 000')
  })
})
