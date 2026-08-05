import { describe, expect, it } from 'vitest'

import ru from '../i18n/locales/ru.json'
import { editRouteForItem } from './editRouteForItem'

describe('tx deep link route mapping', () => {
  it('maps transaction types to edit routes', () => {
    expect(editRouteForItem({ id: 'tx-1', type: 'expense' })).toBe('/edit-expense/tx-1')
    expect(editRouteForItem({ id: 'tx-2', type: 'income' })).toBe('/edit-income/tx-2')
    expect(editRouteForItem({ id: 'tx-3', type: 'transfer' })).toBe('/edit-transfer/tx-3')
    expect(editRouteForItem({ id: 'tx-4', type: 'exchange' })).toBe('/edit-transfer/tx-4')
  })
})

describe('transaction gone copy', () => {
  it('uses the exact bot MSG_GONE string', () => {
    expect(ru.transaction.gone).toBe('Запись больше не существует.')
  })
})
