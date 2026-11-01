import { describe, expect, it } from 'vitest'

import { buildUsageUrl } from '../api/admin'
import { formatTokens, formatUsd, initialOpsState, opsReducer, unparsedValue } from './adminOps'

describe('formatUsd', () => {
  it('uses two decimals with a comma', () => {
    expect(formatUsd(1.234, false)).toBe('$1,23')
    expect(formatUsd(0, false)).toBe('$0,00')
    expect(formatUsd(12, false)).toBe('$12,00')
  })
  it('adds the approximation sign when the cost is incomplete', () => {
    expect(formatUsd(1.5, true)).toBe('≈ $1,50')
  })
})

describe('unparsedValue', () => {
  const fmt = (p: string, n: number, total: number) => `${p}% (${n} из ${total})`
  it('is a dash when there were no messages', () => {
    expect(unparsedValue(0, 0, fmt)).toBe('—')
  })
  it('shows percent with n of N', () => {
    expect(unparsedValue(1, 4, fmt)).toBe('25% (1 из 4)')
    expect(unparsedValue(1, 3, fmt)).toBe('33,3% (1 из 3)')
    expect(unparsedValue(0, 5, fmt)).toBe('0% (0 из 5)')
  })
})

describe('formatTokens', () => {
  it('groups thousands with a non-breaking space', () => {
    expect(formatTokens(1234567)).toBe('1 234 567')
    expect(formatTokens(12)).toBe('12')
  })
})

describe('usage url and reducer', () => {
  it('puts the period into the url', () => {
    expect(buildUsageUrl('week')).toBe('/api/v1/admin/usage?period=week')
  })
  it('changing the period resets to loading for the new period (re-request)', () => {
    const ready = opsReducer(initialOpsState, { type: 'loaded', period: 'day', data: {} as never })
    expect(ready.status).toBe('ready')
    const next = opsReducer(ready, { type: 'select', period: 'week' })
    expect(next).toEqual({ period: 'week', status: 'loading' })
  })
  it('ignores a stale response for a previous period', () => {
    const week = opsReducer(initialOpsState, { type: 'select', period: 'week' })
    const stale = opsReducer(week, { type: 'loaded', period: 'day', data: {} as never })
    expect(stale).toBe(week)
    expect(opsReducer(week, { type: 'failed', period: 'day' })).toBe(week)
    expect(opsReducer(week, { type: 'failed', period: 'week' }).status).toBe('error')
  })
  it('retry goes back to loading', () => {
    const failed = opsReducer(initialOpsState, { type: 'failed', period: 'day' })
    expect(opsReducer(failed, { type: 'select', period: 'day' }).status).toBe('loading')
  })
})
