import { describe, expect, it } from 'vitest'

import { historyFilterAfterTabSwitch } from './analyticsTabState'

const filter = { id: 'sub-1', name: 'Taxi', color: '#fff' }

describe('historyFilterAfterTabSwitch', () => {
  it('keeps the filter just set by a drill-down tap when switching to history', () => {
    expect(historyFilterAfterTabSwitch(filter, 'history')).toBe(filter)
  })
  it('keeps null when switching to history without a filter', () => {
    expect(historyFilterAfterTabSwitch(null, 'history')).toBeNull()
  })
  it('clears the filter when going back to charts', () => {
    expect(historyFilterAfterTabSwitch(filter, 'charts')).toBeNull()
  })
})
