import { create } from 'zustand'

import type { AnalyticsShellState } from '../utils/analyticsTabState'
import { currentMonth } from '../utils/periodFilter'

export function createDefaultAnalyticsShellState(): AnalyticsShellState {
  return {
    activeTab: 'charts',
    periodTab: 'month',
    selectedMonth: currentMonth(),
    rangeFrom: '',
    rangeTo: '',
    rangeFromTouched: false,
    rangeToTouched: false,
    currency: 'UZS',
    drillParent: null,
    historyCategoryFilter: null,
  }
}

type AnalyticsShellStore = {
  shell: AnalyticsShellState | null
  setShell: (shell: AnalyticsShellState) => void
}

export const useAnalyticsShellStore = create<AnalyticsShellStore>((set) => ({
  shell: null,
  setShell: (shell) => set({ shell }),
}))
