import { describe, expect, it } from 'vitest'

import i18n from '../i18n'

import { formatCurrency } from './formatCurrency'
import { sumUnit } from './currencyUnit'
import { walletCurrencySuffix, formatTransferResultLine } from './transactionFormFields'
import { formatGoalMoney } from '../components/goals/goalProgress'

describe('owner decision 12: сум / so\'m instead of UZS', () => {
  it('RU uses сум everywhere', async () => {
    await i18n.changeLanguage('ru')
    expect(sumUnit()).toBe('сум')
    expect(formatCurrency(3_450_000, 'UZS')).toBe('3 450 000 сум')
    expect(formatCurrency(-5, 'UZS')).toBe('−5 сум')
    expect(walletCurrencySuffix('UZS')).toBe('сум')
    expect(formatGoalMoney(200_000, 'UZS')).toBe('200 000 сум')
  })

  it('UZ uses so\'m everywhere', async () => {
    await i18n.changeLanguage('uz')
    expect(sumUnit()).toBe("so'm")
    expect(formatCurrency(3_450_000, 'UZS')).toBe("3 450 000 so'm")
    expect(walletCurrencySuffix('UZS')).toBe("so'm")
    expect(formatGoalMoney(200_000, 'UZS')).toBe("200 000 so'm")
    expect(formatTransferResultLine(100, 'USD', 1_280_000, 'UZS')).toBe("100 $ → 1 280 000 so'm")
  })

  it('USD keeps its own sign and never prints UZS', async () => {
    await i18n.changeLanguage('ru')
    expect(formatCurrency(100, 'USD')).toBe('$100')
    expect(formatCurrency(100, 'UZS')).not.toContain('UZS')
  })
})
