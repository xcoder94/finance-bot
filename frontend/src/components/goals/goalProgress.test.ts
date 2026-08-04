import { describe, expect, it } from 'vitest'

import {
  formatGoalMoney,
  goalDueLabel,
  goalLeftLine,
  goalShowCloseButton,
  goalShowOwnerNote,
} from './goalProgress'

describe('formatGoalMoney', () => {
  it('formats UZS with grouped digits and сум suffix', () => {
    expect(formatGoalMoney(40_000_000, 'UZS')).toBe('40 000 000 сум')
    expect(formatGoalMoney(200_000, 'UZS')).toBe('200 000 сум')
  })

  it('formats USD with grouped digits and $ suffix', () => {
    expect(formatGoalMoney(1_500, 'USD')).toBe('1 500 $')
    expect(formatGoalMoney(100, 'USD')).toBe('100 $')
  })
})

describe('goalLeftLine', () => {
  it('returns frozen label for closed goals', () => {
    expect(
      goalLeftLine({ done: true, balance: 9_500_000, target: 9_500_000, currency: 'UZS' }),
    ).toBe('Показатели заморожены')
  })

  it('returns remaining amount when under target', () => {
    expect(
      goalLeftLine({ done: false, balance: 24_000_000, target: 40_000_000, currency: 'UZS' }),
    ).toBe('Осталось 16 000 000 сум')
  })

  it('returns null when exactly at target', () => {
    expect(
      goalLeftLine({ done: false, balance: 9_500_000, target: 9_500_000, currency: 'UZS' }),
    ).toBeNull()
  })

  it('returns excess label when over target', () => {
    expect(
      goalLeftLine({ done: false, balance: 15_200_000, target: 15_000_000, currency: 'UZS' }),
    ).toBe('Накоплено на 200 000 сум больше')
  })
})

describe('goalDueLabel', () => {
  it('formats closed date', () => {
    expect(goalDueLabel(null, '2026-06-14T10:00:00.000Z', true)).toBe('закрыта 14.06.2026')
  })

  it('returns no-deadline label', () => {
    expect(goalDueLabel(null, null, false)).toBe('без срока')
  })

  it('formats active deadline', () => {
    expect(goalDueLabel('2027-06-01', null, false)).toBe('до 01.06.2027')
  })
})

describe('goalShowCloseButton', () => {
  it('shows for owner over target on active goal', () => {
    expect(
      goalShowCloseButton({
        isOwner: true,
        canClose: true,
        excessAmount: 200_000,
        isExactlyComplete: false,
        status: 'active',
      }),
    ).toBe(true)
  })

  it('shows for owner at exactly 100%', () => {
    expect(
      goalShowCloseButton({
        isOwner: true,
        canClose: true,
        excessAmount: null,
        isExactlyComplete: true,
        status: 'active',
      }),
    ).toBe(true)
  })

  it('hides for member at exactly 100%', () => {
    expect(
      goalShowCloseButton({
        isOwner: false,
        canClose: false,
        excessAmount: null,
        isExactlyComplete: true,
        status: 'active',
      }),
    ).toBe(false)
  })

  it('hides when under target even if can_close', () => {
    expect(
      goalShowCloseButton({
        isOwner: true,
        canClose: true,
        excessAmount: null,
        isExactlyComplete: false,
        status: 'active',
      }),
    ).toBe(false)
  })

  it('hides for member', () => {
    expect(
      goalShowCloseButton({
        isOwner: false,
        canClose: false,
        excessAmount: 200_000,
        isExactlyComplete: false,
        status: 'active',
      }),
    ).toBe(false)
  })

  it('hides for closed goals', () => {
    expect(
      goalShowCloseButton({
        isOwner: true,
        canClose: false,
        excessAmount: 200_000,
        isExactlyComplete: false,
        status: 'closed',
      }),
    ).toBe(false)
  })
})

describe('goalShowOwnerNote', () => {
  it('shows for member over target on active goal', () => {
    expect(
      goalShowOwnerNote({
        isOwner: false,
        excessAmount: 200_000,
        status: 'active',
      }),
    ).toBe(true)
  })

  it('hides for owner', () => {
    expect(
      goalShowOwnerNote({
        isOwner: true,
        excessAmount: 200_000,
        status: 'active',
      }),
    ).toBe(false)
  })

  it('hides when not over target', () => {
    expect(
      goalShowOwnerNote({
        isOwner: false,
        excessAmount: null,
        status: 'active',
      }),
    ).toBe(false)
  })
})
