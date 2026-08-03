export function shouldRefreshHomeOnVisibility(visibilityState: DocumentVisibilityState): boolean {
  return visibilityState === 'visible'
}

export function composeHomeFetchTrigger(monthKey: string, visibilityRefreshCount: number): string {
  return `${monthKey}:${visibilityRefreshCount}`
}

export function composeBalancesFetchTrigger(visibilityRefreshCount: number): string {
  return `balances:${visibilityRefreshCount}`
}
