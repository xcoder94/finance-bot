import { describe, expect, it } from 'vitest'

import {
  composeBalancesFetchTrigger,
  composeHomeFetchTrigger,
  shouldRefreshHomeOnVisibility,
} from './homeVisibility'

describe('shouldRefreshHomeOnVisibility', () => {
  it('refreshes when document becomes visible', () => {
    expect(shouldRefreshHomeOnVisibility('visible')).toBe(true)
  })

  it('does not refresh while hidden', () => {
    expect(shouldRefreshHomeOnVisibility('hidden')).toBe(false)
  })
})

describe('composeHomeFetchTrigger', () => {
  it('changes trigger when visibility refresh count increments', () => {
    expect(composeHomeFetchTrigger('2026-8', 0)).toBe('2026-8:0')
    expect(composeHomeFetchTrigger('2026-8', 1)).toBe('2026-8:1')
    expect(composeHomeFetchTrigger('2026-8', 0)).not.toBe(composeHomeFetchTrigger('2026-8', 1))
  })
})

describe('composeBalancesFetchTrigger', () => {
  it('changes balances trigger when visibility refresh count increments', () => {
    expect(composeBalancesFetchTrigger(0)).toBe('balances:0')
    expect(composeBalancesFetchTrigger(1)).toBe('balances:1')
    expect(composeBalancesFetchTrigger(0)).not.toBe(composeBalancesFetchTrigger(1))
  })
})
