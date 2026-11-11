import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = readFileSync(new URL('../../index.css', import.meta.url), 'utf8')
const darkBlock = css.slice(css.indexOf(':root {'), css.indexOf(":root[data-theme='light']"))
const hex = (name: string) => darkBlock.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`))?.[1] ?? ''

function lum(h: string) {
  const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a: string, b: string) => {
  const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}

describe('dark theme donut greys (weak: computed from CSS values)', () => {
  const bg = hex('bg')
  const other = hex('app-category-color-other')
  const neutral = hex('app-category-color-neutral')
  it('both read against the background at 3:1 or better', () => {
    expect(ratio(other, bg)).toBeGreaterThanOrEqual(3)
    expect(ratio(neutral, bg)).toBeGreaterThanOrEqual(3)
  })
  it('«Другое» and «Без категории» differ in brightness by at least 2:1', () => {
    expect(ratio(other, neutral)).toBeGreaterThanOrEqual(2)
  })
})
