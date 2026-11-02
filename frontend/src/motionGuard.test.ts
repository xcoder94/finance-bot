import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, 'index.css'), 'utf8')

function reducedMotionBlocks(): string[] {
  const blocks: string[] = []
  const re = /@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{/g
  while (re.exec(css)) {
    let depth = 1
    let i = re.lastIndex
    while (i < css.length && depth > 0) {
      if (css[i] === '{') depth++
      else if (css[i] === '}') depth--
      i++
    }
    blocks.push(css.slice(re.lastIndex, i - 1))
  }
  return blocks
}

describe('prefers-reduced-motion guard', () => {
  it('has a universal rule that switches all animation and transition off', () => {
    const universal = reducedMotionBlocks().find((b) => /\*\s*,\s*\*::before\s*,\s*\*::after\s*\{/.test(b))
    expect(universal).toBeDefined()
    expect(universal).toMatch(/animation:\s*none\s*!important/)
    expect(universal).toMatch(/transition:\s*none\s*!important/)
  })

  it('draw-in tick keyframes only animate from a hidden state (final state is the drawn one)', () => {
    const tick = css.match(/@keyframes motion-draw\s*\{[^}]*\}[^}]*\}/)
    expect(tick).not.toBeNull()
    expect(tick![0]).not.toMatch(/\bto\s*\{[^}]*stroke-dashoffset/)
  })

  it('every keyframes animation lives in a stylesheet that also honours reduced motion', () => {
    expect(css).toMatch(/@keyframes/)
    expect(reducedMotionBlocks().length).toBeGreaterThan(0)
  })
})

describe('dev-fix7: motion that the owner could not see / that made pages jump', () => {
  it('plain page fade-in does not move the page (no transform in app-page-in)', () => {
    const kf = css.match(/@keyframes app-page-in\s*\{([\s\S]*?\n\})/)
    expect(kf).not.toBeNull()
    expect(kf![1]).not.toMatch(/transform/)
  })

  // dev-fix10: transform is allowed only in the explicit directional transitions. The dev-fix7 ban
  // existed because a translateY on EVERY page (incl. Home on return) made it jump; here the move
  // is horizontal, chosen by direction, and only opacity + transform are animated.
  it('directional page transitions animate only opacity and transform, horizontally', () => {
    const names = ['forward', 'back', 'tab-next', 'tab-prev'].map((d) => `app-page-${d}`)
    for (const name of names) {
      const m = css.match(new RegExp(`@keyframes ${name}\\s*\\{([\\s\\S]*?\\n\\})`))
      expect(m, name).not.toBeNull()
      const props = [...m![1].matchAll(/([a-z-]+)\s*:/g)].map((x) => x[1])
      expect(props.every((p) => p === 'opacity' || p === 'transform'), name).toBe(true)
      for (const t of m![1].matchAll(/translate3d\(([^)]*)\)/g)) {
        const [, y, z] = t[1].split(',').map((v) => v.trim())
        expect([y, z], name).toEqual(['0', '0'])
      }
      expect(m![1], name).not.toMatch(/translate[YZ]\(/)
    }
  })

  it('page animation has no fill-mode (no lingering transform that would capture position:fixed)', () => {
    const rules = [...css.matchAll(/\.app-shell__page[^{]*\{([^}]*)\}/g)].map((r) => r[1])
    for (const r of rules.filter((x) => /animation:/.test(x))) {
      expect(r).not.toMatch(/forwards|both|backwards/)
    }
  })

  it('page transitions last 200-280 ms and reduced motion switches them off', () => {
    const times = [...css.matchAll(/animation:\s*app-page-[a-z-]+\s+([\d.]+)s/g)].map((m) => Number(m[1]) * 1000)
    expect(times.length).toBe(5)
    for (const t of times) {
      expect(t).toBeGreaterThanOrEqual(200)
      expect(t).toBeLessThanOrEqual(280)
    }
    expect(reducedMotionBlocks().some((b) => /\.app-shell__page\[data-direction\]/.test(b))).toBe(true)
  })

  it('SuccessFlash is mounted in the app shell (it was built but never rendered)', () => {
    const shell = readFileSync(join(__dirname, 'components/AppShell.tsx'), 'utf8')
    expect(shell).toMatch(/<SuccessFlash\s*\/>/)
  })
})
