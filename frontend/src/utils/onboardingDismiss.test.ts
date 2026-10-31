import { beforeEach, describe, expect, it, vi } from 'vitest'

const cloud = vi.hoisted(() => ({ store: new Map<string, string>() }))
vi.mock('../telegram/themeStorage', () => ({
  cloudGet: async (k: string) => cloud.store.get(k) ?? null,
  cloudSet: async (k: string, v: string) => {
    cloud.store.set(k, v)
  },
}))

import {
  ONBOARDING_DISMISSED_KEY,
  ONBOARDING_SNOOZE_DAYS,
  isOnboardingSnoozed,
  shouldShowOnboardingCard,
  loadDismissedAt,
  readDismissedAtSync,
  saveDismissedAt,
} from './onboardingDismiss'

const DAY = 24 * 60 * 60 * 1000
const mem = new Map<string, string>()

beforeEach(() => {
  mem.clear()
  cloud.store.clear()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => mem.get(k) ?? null,
    setItem: (k: string, v: string) => void mem.set(k, v),
    removeItem: (k: string) => void mem.delete(k),
  })
})

describe('onboarding dismiss (owner decision 11)', () => {
  it('key and period', () => {
    expect(ONBOARDING_DISMISSED_KEY).toBe('onboarding_dismissed_at')
    expect(ONBOARDING_SNOOZE_DAYS).toBe(10)
  })

  it('never dismissed -> not snoozed', () => {
    expect(isOnboardingSnoozed(null, Date.now())).toBe(false)
  })

  it('hidden for 10 days after dismissal, back at exactly 10 days', () => {
    const t0 = Date.UTC(2026, 9, 1)
    expect(isOnboardingSnoozed(t0, t0 + 1)).toBe(true)
    expect(isOnboardingSnoozed(t0, t0 + 10 * DAY - 1)).toBe(true)
    expect(isOnboardingSnoozed(t0, t0 + 10 * DAY)).toBe(false)
    expect(isOnboardingSnoozed(t0, t0 + 11 * DAY)).toBe(false)
  })

  it('a timestamp from the future (clock skew) still counts as snoozed, garbage as never dismissed', () => {
    const now = Date.UTC(2026, 9, 1)
    expect(isOnboardingSnoozed(now + DAY, now)).toBe(true)
    expect(isOnboardingSnoozed(Number.NaN, now)).toBe(false)
  })

  it('save writes localStorage and CloudStorage; sync read returns it', async () => {
    await saveDismissedAt(12345)
    expect(mem.get('onboarding_dismissed_at')).toBe('12345')
    expect(cloud.store.get('onboarding_dismissed_at')).toBe('12345')
    expect(readDismissedAtSync()).toBe(12345)
  })

  it('load takes the latest of localStorage and CloudStorage and mirrors it back', async () => {
    mem.set('onboarding_dismissed_at', '100')
    cloud.store.set('onboarding_dismissed_at', '200')
    expect(await loadDismissedAt()).toBe(200)
    expect(mem.get('onboarding_dismissed_at')).toBe('200')
  })

  it('load with nothing stored or junk -> null', async () => {
    expect(await loadDismissedAt()).toBeNull()
    mem.set('onboarding_dismissed_at', 'abc')
    expect(await loadDismissedAt()).toBeNull()
  })
})

describe('shouldShowOnboardingCard', () => {
  const now = Date.UTC(2026, 9, 31)
  const state = (show: boolean) => ({ show, steps: { firstOperation: false, defaultWalletChecked: false, familyInvited: false } })
  it('needs backend show=true and not snoozed', () => {
    expect(shouldShowOnboardingCard(state(true), null, now)).toBe(true)
    expect(shouldShowOnboardingCard(state(false), null, now)).toBe(false)
    expect(shouldShowOnboardingCard(null, null, now)).toBe(false)
    expect(shouldShowOnboardingCard(state(true), now - DAY, now)).toBe(false)
    expect(shouldShowOnboardingCard(state(true), now - 10 * DAY, now)).toBe(true)
  })
})
