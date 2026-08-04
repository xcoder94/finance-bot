import { describe, expect, it } from 'vitest'

import { LIMIT_PERSONAL_WALLETS, LIMIT_SHARED_WALLETS } from '../../constants/entityLimits'
import {
  walletCreateAtLimit,
  walletCreateIsPersonal,
  walletCreateLimitHint,
} from './walletFormLimits'

describe('walletFormLimits', () => {
  it('shows shared limit hint at 10 shared wallets', () => {
    expect(walletCreateLimitHint('shared', 10, 0)).toBe(LIMIT_SHARED_WALLETS)
    expect(walletCreateAtLimit('shared', 10, 0)).toBe(true)
  })

  it('shows personal limit hint at 5 personal wallets', () => {
    expect(walletCreateLimitHint('personal', 0, 5)).toBe(LIMIT_PERSONAL_WALLETS)
    expect(walletCreateAtLimit('personal', 0, 5)).toBe(true)
  })

  it('does not block shared create when only personal limit reached', () => {
    expect(walletCreateLimitHint('shared', 0, 5)).toBeUndefined()
    expect(walletCreateAtLimit('shared', 0, 5)).toBe(false)
  })

  it('maps wallet type to is_personal for create payload', () => {
    expect(walletCreateIsPersonal('shared')).toBe(false)
    expect(walletCreateIsPersonal('personal')).toBe(true)
  })
})
