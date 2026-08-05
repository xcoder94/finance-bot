import { describe, expect, it } from 'vitest'

import { goalDeadlineValidation, isMaskedDateOnOrAfterToday } from './goalFormDeadline'

const TASHKENT_NOON = new Date('2026-08-05T07:00:00.000Z')

describe('isMaskedDateOnOrAfterToday', () => {
  it('accepts today in Tashkent', () => {
    expect(isMaskedDateOnOrAfterToday('05.08.2026', TASHKENT_NOON)).toBe(true)
  })

  it('accepts future dates', () => {
    expect(isMaskedDateOnOrAfterToday('01.01.2027', TASHKENT_NOON)).toBe(true)
  })

  it('rejects dates before today in Tashkent', () => {
    expect(isMaskedDateOnOrAfterToday('04.08.2026', TASHKENT_NOON)).toBe(false)
  })

  it('rejects invalid masked dates', () => {
    expect(isMaskedDateOnOrAfterToday('32.08.2026', TASHKENT_NOON)).toBe(false)
  })
})

describe('goalDeadlineValidation', () => {
  it('accepts empty deadline', () => {
    expect(goalDeadlineValidation('', { mode: 'create', now: TASHKENT_NOON })).toEqual({
      valid: true,
      hintKey: null,
    })
  })

  it('rejects invalid format', () => {
    expect(goalDeadlineValidation('32.08.2026', { mode: 'create', now: TASHKENT_NOON })).toEqual({
      valid: false,
      hintKey: 'goals.form.deadlineInvalid',
    })
  })

  it('rejects backdated deadline on create', () => {
    expect(goalDeadlineValidation('04.08.2026', { mode: 'create', now: TASHKENT_NOON })).toEqual({
      valid: false,
      hintKey: 'addTransaction.invalidDate',
    })
  })

  it('accepts today and future deadlines on create', () => {
    expect(goalDeadlineValidation('05.08.2026', { mode: 'create', now: TASHKENT_NOON })).toEqual({
      valid: true,
      hintKey: null,
    })
    expect(goalDeadlineValidation('01.01.2027', { mode: 'create', now: TASHKENT_NOON })).toEqual({
      valid: true,
      hintKey: null,
    })
  })

  it('allows keeping an existing past deadline in edit mode', () => {
    expect(
      goalDeadlineValidation('01.08.2026', {
        mode: 'edit',
        existingDeadlineMasked: '01.08.2026',
        now: TASHKENT_NOON,
      }),
    ).toEqual({
      valid: true,
      hintKey: null,
    })
  })

  it('rejects changing deadline to a new past date in edit mode', () => {
    expect(
      goalDeadlineValidation('04.08.2026', {
        mode: 'edit',
        existingDeadlineMasked: '01.08.2026',
        now: TASHKENT_NOON,
      }),
    ).toEqual({
      valid: false,
      hintKey: 'addTransaction.invalidDate',
    })
  })
})
