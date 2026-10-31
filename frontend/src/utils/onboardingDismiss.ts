import { cloudGet, cloudSet } from '../telegram/themeStorage'

export const ONBOARDING_DISMISSED_KEY = 'onboarding_dismissed_at'
export const ONBOARDING_SNOOZE_DAYS = 10

const DAY_MS = 24 * 60 * 60 * 1000

function parseTs(raw: string | null): number | null {
  if (!raw) return null
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
}

/** Card hidden for 10 days after the owner pressed «×». */
export function isOnboardingSnoozed(dismissedAt: number | null, now: number): boolean {
  if (dismissedAt === null || !Number.isFinite(dismissedAt)) return false
  return now - dismissedAt < ONBOARDING_SNOOZE_DAYS * DAY_MS
}

export function readDismissedAtSync(): number | null {
  try {
    return parseTs(localStorage.getItem(ONBOARDING_DISMISSED_KEY))
  } catch {
    return null
  }
}

export async function saveDismissedAt(ts: number): Promise<void> {
  try {
    localStorage.setItem(ONBOARDING_DISMISSED_KEY, String(ts))
  } catch {
    // CloudStorage below may still keep it
  }
  await cloudSet(ONBOARDING_DISMISSED_KEY, String(ts))
}

/** Latest of localStorage and Telegram CloudStorage; mirrors the winner back to localStorage. */
export async function loadDismissedAt(): Promise<number | null> {
  const local = readDismissedAtSync()
  const cloud = parseTs(await cloudGet(ONBOARDING_DISMISSED_KEY))
  const best = Math.max(local ?? 0, cloud ?? 0)
  if (best === 0) return null
  if (best !== local) {
    try {
      localStorage.setItem(ONBOARDING_DISMISSED_KEY, String(best))
    } catch {
      // ignore
    }
  }
  return best
}

export function shouldShowOnboardingCard(
  state: { show: boolean } | null,
  dismissedAt: number | null,
  now: number,
): boolean {
  return state?.show === true && !isOnboardingSnoozed(dismissedAt, now)
}
