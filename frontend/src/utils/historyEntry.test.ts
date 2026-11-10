import { beforeEach, describe, expect, it } from 'vitest'

import { useAnalyticsShellStore } from '../store/analyticsShellStore'
import { historyShellFor, openHistoryFromHome, openHistoryTab } from './historyEntry'
import { forgetHomeMonth, peekHomeMonth } from './homeMonthMemory'
import { isRootPath } from './historyBackTarget'

beforeEach(() => {
  useAnalyticsShellStore.setState({ shell: null })
})

describe('historyShellFor', () => {
  it('opens the History tab on the given month, month mode, no category filter', () => {
    const shell = historyShellFor(null, { year: 2026, month: 10 })
    expect(shell.activeTab).toBe('history')
    expect(shell.periodTab).toBe('month')
    expect(shell.selectedMonth).toEqual({ year: 2026, month: 10 })
    expect(shell.historyCategoryFilter).toBeNull()
    expect(shell.drillParent).toBeNull()
  })

  it('without a month keeps the shared period of the previous state', () => {
    const prev = historyShellFor(null, { year: 2026, month: 9 })
    const shell = historyShellFor({ ...prev, activeTab: 'charts' })
    expect(shell.activeTab).toBe('history')
    expect(shell.selectedMonth).toEqual({ year: 2026, month: 9 })
  })
})

describe('openHistoryTab', () => {
  it('writes the shell into the store', () => {
    openHistoryTab({ year: 2026, month: 10 })
    const shell = useAnalyticsShellStore.getState().shell
    expect(shell?.activeTab).toBe('history')
    expect(shell?.selectedMonth).toEqual({ year: 2026, month: 10 })
  })
})

describe('isRootPath', () => {
  it('Analytics opened from Home is not a root: Back leads to Home', () => {
    expect(isRootPath('/analytics', { from: 'home' })).toBe(false)
    expect(isRootPath('/analytics', null)).toBe(true)
    expect(isRootPath('/', { from: 'home' })).toBe(true)
    expect(isRootPath('/history', null)).toBe(false)
  })
})

describe('openHistoryFromHome (acceptance 1)', () => {
  it('October on Home -> History shows October; Home still gets October back', () => {
    const calls: unknown[][] = []
    openHistoryFromHome({ year: 2026, month: 10 }, (...args) => calls.push(args))
    expect(calls).toEqual([['/analytics', { state: { from: 'home' } }]])
    expect(useAnalyticsShellStore.getState().shell?.selectedMonth).toEqual({ year: 2026, month: 10 })
    expect(useAnalyticsShellStore.getState().shell?.activeTab).toBe('history')
    expect(peekHomeMonth()).toEqual({ year: 2026, month: 10 })
    forgetHomeMonth()
  })
})
