import { describe, expect, it } from 'vitest'

import ru from './locales/ru.json'
import uz from './locales/uz.json'

const KEYS = [
  'title', 'total', 'shared', 'personal', 'hint', 'empty', 'balanceNow', 'opsEmptyHint',
] as const

describe('wallets.* keys', () => {
  it.each(KEYS)('ru and uz have wallets.%s', (key) => {
    const r = (ru as unknown as { wallets?: Record<string, string> }).wallets?.[key]
    const u = (uz as unknown as { wallets?: Record<string, string> }).wallets?.[key]
    expect(typeof r).toBe('string')
    expect(r).not.toBe('')
    expect(typeof u).toBe('string')
    expect(u).not.toBe('')
  })
})
