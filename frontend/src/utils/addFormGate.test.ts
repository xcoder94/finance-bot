import { describe, expect, it } from 'vitest'

import { evaluateAddSubmit } from './addFormGate'

const base = { parsedAmount: 1000, walletId: 'w1', categoryId: 'c1', amountOverLimit: false }

describe('evaluateAddSubmit', () => {
  it('allows saving when everything is filled', () => {
    expect(evaluateAddSubmit(base)).toBe('ok')
  })

  it('refuses with a category message when only the category is missing (nothing is pre-selected)', () => {
    expect(evaluateAddSubmit({ ...base, categoryId: '' })).toBe('category')
  })

  it('stays silent-invalid for a missing amount or wallet, even with no category', () => {
    expect(evaluateAddSubmit({ ...base, parsedAmount: null })).toBe('invalid')
    expect(evaluateAddSubmit({ ...base, walletId: '', categoryId: '' })).toBe('invalid')
    expect(evaluateAddSubmit({ ...base, amountOverLimit: true })).toBe('invalid')
  })
})
