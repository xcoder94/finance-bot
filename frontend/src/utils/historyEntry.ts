import { rememberHomeMonth } from './homeMonthMemory'
import { useAnalyticsShellStore, createDefaultAnalyticsShellState } from '../store/analyticsShellStore'
import type { AnalyticsShellState } from './analyticsTabState'
import type { SelectedMonth } from './periodFilter'

/** Shell state that shows the History tab; a month, when given, becomes the shared period. */
export function historyShellFor(
  prev: AnalyticsShellState | null,
  month?: SelectedMonth,
): AnalyticsShellState {
  const base = prev ?? createDefaultAnalyticsShellState()
  return {
    ...base,
    activeTab: 'history',
    drillParent: null,
    historyCategoryFilter: null,
    ...(month ? { periodTab: 'month' as const, selectedMonth: month } : {}),
  }
}

export function openHistoryTab(month?: SelectedMonth): void {
  const { shell, setShell } = useAnalyticsShellStore.getState()
  setShell(historyShellFor(shell, month))
}

/** Home «Все ›»: History tab on the Home month; Home remembers its month for the way back. */
export function openHistoryFromHome(
  month: SelectedMonth,
  navigate: (path: string, options: { state: { from: 'home' } }) => void,
): void {
  rememberHomeMonth(month)
  openHistoryTab(month)
  navigate('/analytics', { state: { from: 'home' } })
}
