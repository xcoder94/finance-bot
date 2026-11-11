import { afterEach, describe, expect, it } from 'vitest'

import i18n from '../i18n'

import { chooseTrendAxisScale, formatTrendAxisTick, trendAxisCaption } from './trendAxis'

afterEach(async () => {
  await i18n.changeLanguage('ru')
})

describe('12-month chart axis (B7)', () => {
  it('max 2.2e9 -> billions in caption and ticks', async () => {
    await i18n.changeLanguage('ru')
    const scale = chooseTrendAxisScale(2.2e9)
    expect(trendAxisCaption(scale, 'UZS')).toBe('млрд\u00A0сум')
    expect(formatTrendAxisTick(1_100_000_000, scale)).toBe('1,1')
    expect(formatTrendAxisTick(2_000_000_000, scale)).toBe('2')
    expect(formatTrendAxisTick(0, scale)).toBe('0')
  })
  it('millions and thousands', () => {
    expect(trendAxisCaption(chooseTrendAxisScale(45e6), 'UZS')).toBe('млн\u00A0сум')
    expect(trendAxisCaption(chooseTrendAxisScale(45e3), 'UZS')).toBe('тыс\u00A0сум')
    expect(trendAxisCaption(chooseTrendAxisScale(900), 'UZS')).toBe('сум')
    expect(formatTrendAxisTick(900, chooseTrendAxisScale(900))).toBe('900')
  })
  it('UZ caption and USD', async () => {
    await i18n.changeLanguage('uz')
    expect(trendAxisCaption(chooseTrendAxisScale(3e9), 'UZS')).toBe("mlrd\u00A0so'm")
    expect(trendAxisCaption(chooseTrendAxisScale(3e6), 'USD')).toBe('mln\u00A0$')
  })
  it('tick text has no space (one line)', () => {
    const scale = chooseTrendAxisScale(2.2e9)
    expect(formatTrendAxisTick(1_500_000_000, scale)).not.toMatch(/\s/)
  })
})
