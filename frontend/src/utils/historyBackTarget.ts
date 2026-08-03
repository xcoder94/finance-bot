export type HistoryNavigationState = {
  from?: 'home'
}

export function historyBackTarget(state: unknown): '/' | null {
  if (
    state !== null &&
    typeof state === 'object' &&
    'from' in state &&
    (state as HistoryNavigationState).from === 'home'
  ) {
    return '/'
  }
  return null
}
