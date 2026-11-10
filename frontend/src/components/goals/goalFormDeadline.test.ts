import { describe, expect, it } from 'vitest'

import { goalDeadlineValidation, isDeadlineOnOrAfterToday } from './goalFormDeadline'

const TASHKENT_NOON = new Date('2026-08-05T07:00:00.000Z')

describe('isDeadlineOnOrAfterToday', () => {
  it('accepts today in Tashkent', () => {
    expect(isDeadlineOnOrAfterToday('2026-08-05', TASHKENT_NOON)).toBe(true)
  })

  it('accepts future dates', () => {
    expect(isDeadlineOnOrAfterToday('2027-01-01', TASHKENT_NOON)).toBe(true)
  })

  it('rejects dates before today in Tashkent', () => {
    expect(isDeadlineOnOrAfterToday('2026-08-04', TASHKENT_NOON)).toBe(false)
  })

  it('rejects impossible dates', () => {
    expect(isDeadlineOnOrAfterToday('2026-08-32', TASHKENT_NOON)).toBe(false)
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
    expect(goalDeadlineValidation('2026-08-32', { mode: 'create', now: TASHKENT_NOON })).toEqual({
      valid: false,
      hintKey: 'goals.form.deadlineInvalid',
    })
  })

  it('rejects backdated deadline on create', () => {
    expect(goalDeadlineValidation('2026-08-04', { mode: 'create', now: TASHKENT_NOON })).toEqual({
      valid: false,
      hintKey: 'addTransaction.invalidDate',
    })
  })

  it('accepts today and future deadlines on create', () => {
    expect(goalDeadlineValidation('2026-08-05', { mode: 'create', now: TASHKENT_NOON })).toEqual({
      valid: true,
      hintKey: null,
    })
    expect(goalDeadlineValidation('2027-01-01', { mode: 'create', now: TASHKENT_NOON })).toEqual({
      valid: true,
      hintKey: null,
    })
  })

  it('allows keeping an existing past deadline in edit mode', () => {
    expect(
      goalDeadlineValidation('2026-08-01', {
        mode: 'edit',
        existingDeadline: '2026-08-01',
        now: TASHKENT_NOON,
      }),
    ).toEqual({
      valid: true,
      hintKey: null,
    })
  })

  it('rejects changing deadline to a new past date in edit mode', () => {
    expect(
      goalDeadlineValidation('2026-08-04', {
        mode: 'edit',
        existingDeadline: '2026-08-01',
        now: TASHKENT_NOON,
      }),
    ).toEqual({
      valid: false,
      hintKey: 'addTransaction.invalidDate',
    })
  })
})
