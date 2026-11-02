export type PageDirection = 'forward' | 'back' | 'tab-next' | 'tab-prev' | 'fade'
export type NavKind = 'POP' | 'PUSH' | 'REPLACE'

// Order of the bottom-menu tabs (see components/mainTabs.ts).
const TAB_AREAS = ['', 'shopping', 'analytics', 'goals']

function normalize(pathname: string): string {
  return pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
}

function segments(pathname: string): string[] {
  return normalize(pathname).split('/').filter(Boolean)
}

/** One key per visible screen. Analytics inner routes live in one screen (no remount). */
export function pageScreenKey(pathname: string): string {
  const p = normalize(pathname)
  return segments(p)[0] === 'analytics' ? '/analytics' : p
}

function tabIndex(pathname: string): number {
  return TAB_AREAS.indexOf(segments(pathname)[0] ?? '')
}

/** Direction of the enter animation for a change from `from` to `to`; null = same screen. */
export function transitionDirection(
  from: string | null,
  to: string,
  navKind: NavKind,
): PageDirection | null {
  if (from === null) return 'fade'
  if (pageScreenKey(from) === pageScreenKey(to)) return null

  const a = tabIndex(from)
  const b = tabIndex(to)
  if (a !== -1 && b !== -1 && a !== b) return b > a ? 'tab-next' : 'tab-prev'
  if (a === -1 && b !== -1 && segments(to).length <= 1) return 'back'

  const da = segments(from).length
  const db = segments(to).length
  if (db > da) return 'forward'
  if (db < da) return 'back'
  return navKind === 'POP' ? 'back' : 'forward'
}
