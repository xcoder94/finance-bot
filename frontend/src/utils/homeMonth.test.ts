import { describe, expect, it } from 'vitest'
import {
  MONTH_PREPOSITIONAL,
  MONTH_SHORT,
  balanceMonthLabel,
  emptyMonthTitle,
  formatMonthTitle,
  monthShortLabel,
  opsCountLabel,
} from './homeMonth'

describe('MONTH_SHORT', () => {
  it('has 12 Russian short month labels', () => {
    expect(MONTH_SHORT).toEqual([
      'янв',
      'фев',
      'март',
      'апр',
      'май',
      'июнь',
      'июль',
      'август',
      'сен',
      'окт',
      'ноя',
      'дек',
    ])
  })
})

describe('MONTH_PREPOSITIONAL', () => {
  it('has 12 Russian prepositional month labels', () => {
    expect(MONTH_PREPOSITIONAL).toEqual([
      'январе',
      'феврале',
      'марте',
      'апреле',
      'мае',
      'июне',
      'июле',
      'августе',
      'сентябре',
      'октябре',
      'ноябре',
      'декабре',
    ])
  })
})

describe('monthShortLabel', () => {
  it('returns short label for valid month', () => {
    expect(monthShortLabel(8)).toBe('август')
  })
})

describe('emptyMonthTitle', () => {
  it('formats empty month title with prepositional month', () => {
    expect(emptyMonthTitle(8)).toBe('В августе операций нет')
  })
})

describe('opsCountLabel', () => {
  it('returns none label when count is zero', () => {
    expect(opsCountLabel(0, 8)).toBe('нет операций')
  })

  it('returns count with short month when count is positive', () => {
    expect(opsCountLabel(32, 8)).toBe('32 за август')
  })
})

describe('balanceMonthLabel', () => {
  it('formats balance label with short month', () => {
    expect(balanceMonthLabel(8)).toBe('Остаток · август')
  })
})

describe('formatMonthTitle', () => {
  it('formats nominative long month with year', () => {
    expect(formatMonthTitle(2026, 8)).toBe('Август 2026')
  })
})
