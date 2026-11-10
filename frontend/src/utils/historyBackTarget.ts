export type HistoryNavigationState = {
  from?: 'home' | 'analytics'
}

export function historyBackTarget(state: unknown): '/' | '/analytics' | null {
  if (state === null || typeof state !== 'object' || !('from' in state)) {
    return null
  }

  const from = (state as HistoryNavigationState).from
  if (from === 'home') {
    return '/'
  }
  if (from === 'analytics') {
    return '/analytics'
  }
  return null
}

const ROOT_PATHS = new Set(['/', '/shopping', '/analytics', '/goals'])

/** Bottom-tab screens have no Back button; Analytics opened from Home does (it returns Home). */
export function isRootPath(pathname: string, state: unknown): boolean {
  if (pathname === '/analytics' && historyBackTarget(state) === '/') {
    return false
  }
  return ROOT_PATHS.has(pathname)
}
