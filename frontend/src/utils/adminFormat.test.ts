import { describe, expect, it } from 'vitest'

import {
  appendUsersPage,
  formatLastSeen,
  formatRegisteredDate,
  formatSinceDate,
  retentionValue,
  telegramLink,
} from './adminFormat'

describe('retentionValue', () => {
  it('shows percent with n of N', () => {
    expect(retentionValue({ returned: 3, cohort: 12, percent: 25 }, (n, N) => `${n} of ${N}`)).toBe(
      '25% (3 of 12)',
    )
  })
  it('shows a dash when the cohort is empty', () => {
    expect(retentionValue({ returned: 0, cohort: 0, percent: null }, () => 'x')).toBe('—')
  })
  it('trims a trailing .0 and keeps one decimal', () => {
    expect(retentionValue({ returned: 1, cohort: 3, percent: 33.3 }, () => 'a')).toBe('33,3% (a)')
    expect(retentionValue({ returned: 1, cohort: 2, percent: 50.0 }, () => 'a')).toBe('50% (a)')
  })
})

describe('Tashkent dates (independent of the runtime TZ)', () => {
  it('formats registration date DD.MM.YYYY from an ISO +05:00 string', () => {
    expect(formatRegisteredDate('2026-10-31T23:30:00+05:00')).toBe('31.10.2026')
  })
  it('converts a UTC instant to Tashkent before formatting', () => {
    // 20:00 UTC on 30.10 is already 01:00 on 31.10 in Tashkent
    expect(formatRegisteredDate('2026-10-30T20:00:00Z')).toBe('31.10.2026')
    expect(formatLastSeen('2026-10-30T20:05:00Z')).toBe('31.10 01:05')
  })
  it('last seen is a dash for null', () => {
    expect(formatLastSeen(null)).toBe('—')
  })
  it('formats the since-date from a plain YYYY-MM-DD', () => {
    expect(formatSinceDate('2026-10-31')).toBe('31.10.2026')
  })
})

describe('telegramLink', () => {
  it('builds a t.me link and drops a leading @', () => {
    expect(telegramLink('@ali_v')).toBe('https://t.me/ali_v')
    expect(telegramLink('ali_v')).toBe('https://t.me/ali_v')
  })
  it('returns null for empty or unsafe usernames', () => {
    expect(telegramLink(null)).toBeNull()
    expect(telegramLink('')).toBeNull()
    expect(telegramLink('a/../b')).toBeNull()
  })
})

describe('appendUsersPage', () => {
  const u = (id: string) => ({ id }) as never
  it('appends a page without duplicates', () => {
    const merged = appendUsersPage([u('1'), u('2')], [u('2'), u('3')])
    expect(merged.map((x: { id: string }) => x.id)).toEqual(['1', '2', '3'])
  })
})

describe('chart tooltip label', () => {
  it('has a Russian series name and a colon separator', async () => {
    const ru = (await import('../i18n/locales/admin.ru.json')).default as { growth: Record<string, string> }
    const { CHART_TOOLTIP_SEPARATOR } = await import('./adminFormat')
    expect(ru.growth.activeSeries).toBe('Активных')
    expect(`${ru.growth.activeSeries}${CHART_TOOLTIP_SEPARATOR}2`).toBe('Активных: 2')
  })
})
