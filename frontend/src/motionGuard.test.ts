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
  it('page fade-in does not move the page (no transform in app-page-in)', () => {
    const kf = css.match(/@keyframes app-page-in\s*\{([\s\S]*?\n\})/)
    expect(kf).not.toBeNull()
    expect(kf![1]).not.toMatch(/transform/)
  })

  it('SuccessFlash is mounted in the app shell (it was built but never rendered)', () => {
    const shell = readFileSync(join(__dirname, 'components/AppShell.tsx'), 'utf8')
    expect(shell).toMatch(/<SuccessFlash\s*\/>/)
  })
})
