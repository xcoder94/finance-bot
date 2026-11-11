/**
 * Browser history for the filtered History view (opened from a chart category). Opening it pushes
 * one entry, so the browser's Back (popstate) returns to the chart exactly like the Telegram Back
 * button; leaving the filtered view any other way pops that entry again so no dead entry is left.
 */
export type FilteredHistoryEntryHooks = {
  /** history.push of the current URL (a new entry). */
  push: () => void
  /** history.back(). */
  back: () => void
  /** Leave the filtered view (back to the charts, filter cleared). */
  leaveFilteredView: () => void
}

export function createFilteredHistoryEntry(hooks: FilteredHistoryEntryHooks) {
  let pushed = false
  let poppedByBrowser = false
  return {
    /** Call whenever "filtered History is shown" changes (and once on mount). */
    onActiveChange(active: boolean): void {
      if (active && !pushed) {
        pushed = true
        hooks.push()
      } else if (!active && pushed) {
        pushed = false
        if (poppedByBrowser) {
          poppedByBrowser = false
        } else {
          hooks.back()
        }
      }
    },
    /** Browser Back/Forward (popstate). */
    onPopState(): void {
      if (pushed) {
        poppedByBrowser = true
        hooks.leaveFilteredView()
      }
    },
    /** Telegram Back / in-app back while filtered: go through the browser history. */
    requestBack(): void {
      if (pushed) {
        hooks.back()
      } else {
        hooks.leaveFilteredView()
      }
    },
  }
}
