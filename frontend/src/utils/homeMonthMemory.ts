import type { HomeMonth } from './homeMonth'

/**
 * Home unmounts when /wallets opens, and the selected month lives in its state. The month is
 * parked here on the way out and read back when Home mounts again (then forgotten).
 */
let remembered: HomeMonth | null = null

export function rememberHomeMonth(month: HomeMonth): void {
  remembered = { year: month.year, month: month.month }
}

export function peekHomeMonth(): HomeMonth | null {
  return remembered
}

export function forgetHomeMonth(): void {
  remembered = null
}

export const WALLETS_PATH = '/wallets'

/** Balance card tap: remember the month, then go to the wallets screen. */
export function openWalletsFromHome(month: HomeMonth, navigate: (path: string) => void): void {
  rememberHomeMonth(month)
  navigate(WALLETS_PATH)
}
