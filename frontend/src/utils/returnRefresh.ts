/** Minimum gap between two refreshes caused by returning to the app (designer review, point e). */
export const RETURN_REFRESH_THROTTLE_MS = 30_000

type Deps = {
  now: () => number
  onRefresh: () => void
}

/**
 * Throttle for "the user came back to the app". No timers: the only trigger is an explicit
 * onReturn() call. The clock starts at creation (the data was just loaded), and one return that
 * fires several events (visibilitychange + Telegram activated + bridge) refreshes once.
 */
export function createReturnRefresher({ now, onRefresh }: Deps) {
  let last = now()
  return {
    onReturn() {
      const current = now()
      if (current - last < RETURN_REFRESH_THROTTLE_MS) return
      last = current
      onRefresh()
    },
  }
}
