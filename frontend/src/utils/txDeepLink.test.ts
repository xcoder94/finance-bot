import { describe, expect, it } from 'vitest'

import {
  parseTxParam,
  resolveTxLaunchAction,
} from './txDeepLink'

const VALID_UUID = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'

describe('parseTxParam', () => {
  it('returns null when tx is missing', () => {
    expect(parseTxParam('')).toBeNull()
    expect(parseTxParam('?other=1')).toBeNull()
  })

  it('returns null for invalid tx values', () => {
    expect(parseTxParam('?tx=not-a-uuid')).toBeNull()
    expect(parseTxParam('?tx=123')).toBeNull()
    expect(parseTxParam(`?tx=${VALID_UUID.slice(0, -1)}`)).toBeNull()
  })

  it('accepts valid UUIDs regardless of case', () => {
    expect(parseTxParam(`?tx=${VALID_UUID}`)).toBe(VALID_UUID)
    expect(parseTxParam(`?tx=${VALID_UUID.toUpperCase()}`)).toBe(VALID_UUID.toUpperCase())
  })
})

describe('resolveTxLaunchAction', () => {
  it('returns none when tx is absent', () => {
    expect(resolveTxLaunchAction('')).toEqual({ kind: 'none' })
  })

  it('returns invalid when tx is present but not a UUID', () => {
    expect(resolveTxLaunchAction('?tx=bad')).toEqual({ kind: 'invalid' })
  })

  it('returns fetch for a valid tx param', () => {
    expect(resolveTxLaunchAction(`?tx=${VALID_UUID}`)).toEqual({
      kind: 'fetch',
      transactionId: VALID_UUID,
    })
  })
})
