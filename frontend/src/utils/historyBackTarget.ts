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
