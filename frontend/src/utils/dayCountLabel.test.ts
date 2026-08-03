import { describe, expect, it } from 'vitest'

import { dayCountLabel } from './dayCountLabel'

describe('dayCountLabel', () => {
  it('uses Russian day plural forms', () => {
    expect(dayCountLabel(1)).toBe('1 день')
    expect(dayCountLabel(2)).toBe('2 дня')
    expect(dayCountLabel(3)).toBe('3 дня')
    expect(dayCountLabel(4)).toBe('4 дня')
    expect(dayCountLabel(5)).toBe('5 дней')
    expect(dayCountLabel(21)).toBe('21 день')
    expect(dayCountLabel(31)).toBe('31 день')
  })
})
