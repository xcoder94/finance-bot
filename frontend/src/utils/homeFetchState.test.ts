import { describe, expect, it } from 'vitest'

import { resolveFetchState } from './homeFetchState'

describe('resolveFetchState (no figures of one month under another month title)', () => {
  it('returns the stored state when it belongs to the current key', () => {
    const stored = { key: '2026-8', state: { status: 'success' as const, data: 'aug' } }
    expect(resolveFetchState(stored, '2026-8', null)).toEqual({ status: 'success', data: 'aug' })
  })

  it('after paging to another month the old data is NOT shown: loading', () => {
    const stored = { key: '2026-8', state: { status: 'success' as const, data: 'aug' } }
    expect(resolveFetchState(stored, '2026-7', null)).toEqual({ status: 'loading' })
  })

  it('after paging, cached data of the new month is shown immediately', () => {
    const stored = { key: '2026-8', state: { status: 'success' as const, data: 'aug' } }
    expect(resolveFetchState(stored, '2026-7', 'jul')).toEqual({ status: 'success', data: 'jul' })
  })

  it('an error of another month is not carried over either', () => {
    const stored = { key: '2026-8', state: { status: 'error' as const } }
    expect(resolveFetchState(stored, '2026-7', null)).toEqual({ status: 'loading' })
  })
})
