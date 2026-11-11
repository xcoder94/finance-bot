import { describe, expect, it, vi } from 'vitest'

import { createFilteredHistoryEntry } from './filteredHistoryEntry'

function setup() {
  const hooks = { push: vi.fn(), back: vi.fn(), leaveFilteredView: vi.fn() }
  return { hooks, entry: createFilteredHistoryEntry(hooks) }
}

describe('filtered History is a real browser-history entry (browser Back goes to the chart)', () => {
  it('opening the filtered view pushes exactly one entry (not a replace)', () => {
    const { hooks, entry } = setup()
    entry.onActiveChange(true)
    entry.onActiveChange(true)
    expect(hooks.push).toHaveBeenCalledTimes(1)
  })

  it('browser Back while filtered leaves the view and does not pop a second time', () => {
    const { hooks, entry } = setup()
    entry.onActiveChange(true)
    entry.onPopState()
    expect(hooks.leaveFilteredView).toHaveBeenCalledTimes(1)
    entry.onActiveChange(false)
    expect(hooks.back).not.toHaveBeenCalled()
  })

  it('leaving by the tab or the filter chip pops the pushed entry', () => {
    const { hooks, entry } = setup()
    entry.onActiveChange(true)
    entry.onActiveChange(false)
    expect(hooks.back).toHaveBeenCalledTimes(1)
  })

  it('Telegram Back goes through browser history: back() once, then the popstate clears the view', () => {
    const { hooks, entry } = setup()
    entry.onActiveChange(true)
    entry.requestBack()
    expect(hooks.back).toHaveBeenCalledTimes(1)
    entry.onPopState()
    entry.onActiveChange(false)
    expect(hooks.leaveFilteredView).toHaveBeenCalledTimes(1)
    expect(hooks.back).toHaveBeenCalledTimes(1)
  })

  it('popstate while not filtered is ignored; Back without an entry just leaves the view', () => {
    const { hooks, entry } = setup()
    entry.onPopState()
    expect(hooks.leaveFilteredView).not.toHaveBeenCalled()
    entry.requestBack()
    expect(hooks.leaveFilteredView).toHaveBeenCalledTimes(1)
    expect(hooks.back).not.toHaveBeenCalled()
  })
})
