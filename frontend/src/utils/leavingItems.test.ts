import { describe, expect, it } from 'vitest'

import { findRemoved, withLeaving } from './leavingItems'

type It = { id: string }
const a = { id: 'a' }
const b = { id: 'b' }
const c = { id: 'c' }

describe('leavingItems', () => {
  it('finds removed items with their old index', () => {
    expect(findRemoved([a, b, c], [a, c])).toEqual([{ item: b, index: 1 }])
    expect(findRemoved([a], [a, b])).toEqual([])
    expect(findRemoved([], [a])).toEqual([])
  })

  it('merges leaving ghosts back at their position', () => {
    const merged = withLeaving<It>([a, c], [{ item: b, index: 1 }])
    expect(merged.map((m) => [m.item.id, m.leaving])).toEqual([
      ['a', false],
      ['b', true],
      ['c', false],
    ])
  })

  it('ignores a ghost that came back as a live item', () => {
    const merged = withLeaving<It>([a, b], [{ item: b, index: 1 }])
    expect(merged.filter((m) => m.item.id === 'b')).toHaveLength(1)
    expect(merged.every((m) => !m.leaving)).toBe(true)
  })
})
