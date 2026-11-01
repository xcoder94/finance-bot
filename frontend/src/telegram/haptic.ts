import { hapticFeedback } from '@tma.js/sdk-react'

type ImpactStyle = 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'
type NotificationType = 'success' | 'error' | 'warning'

export type HapticDriver = {
  impact: (style: ImpactStyle) => void
  notification: (type: NotificationType) => void
}

const telegramDriver: HapticDriver = {
  impact(style) {
    if (hapticFeedback.impactOccurred.isAvailable()) hapticFeedback.impactOccurred(style)
  },
  notification(type) {
    if (hapticFeedback.notificationOccurred.isAvailable()) hapticFeedback.notificationOccurred(type)
  },
}

let driver: HapticDriver = telegramDriver

export function setHapticDriver(next: HapticDriver): void {
  driver = next
}

export function resetHapticDriver(): void {
  driver = telegramDriver
}

function safe(run: () => void): void {
  try {
    run()
  } catch {
    // outside Telegram or an old client: haptics are optional
  }
}

/** Telegram HapticFeedback. Always safe to call. */
export const haptic = {
  light: () => safe(() => driver.impact('light')),
  success: () => safe(() => driver.notification('success')),
  error: () => safe(() => driver.notification('error')),
}

export const HAPTIC_TAP_SELECTOR = 'button, a.tabbar-link'

type TapElement = {
  closest: (selector: string) => { disabled?: boolean; getAttribute: (name: string) => string | null } | null
}

/** True when a click landed on an enabled button / tab link (light impact on tap). */
export function isHapticTapTarget(target: TapElement | null): boolean {
  const hit = target?.closest(HAPTIC_TAP_SELECTOR)
  if (!hit) return false
  return !hit.disabled && hit.getAttribute('aria-disabled') !== 'true'
}
