import { describe, expect, it } from 'vitest'

import { groupThousands } from './groupThousands'

describe('groupThousands', () => {
  it('joins digit groups with NBSP, never a plain space', () => {
    expect(groupThousands(1234567)).toBe('1\u00a0234\u00a0567')
    expect(groupThousands(1234567)).not.toContain(' ')
    expect(groupThousands('999')).toBe('999')
  })
})
