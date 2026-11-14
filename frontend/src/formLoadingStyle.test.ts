import { readFileSync } from 'node:fs'
import postcss from 'postcss'
import { describe, expect, it } from 'vitest'

// WEAK test (reads the stylesheet, not a rendered page): REG-1 of ux-next5 — a new rule was pasted
// after the line `.form-sheet-loading,`, the selector list swallowed it and the loading state of the
// forms lost its centring and its 120 px height. The rendered check is in the browser shots.
const root = postcss.parse(readFileSync(new URL('./index.css', import.meta.url), 'utf8'))

/** Declarations that apply to exactly this class, merged over every rule whose selector list names it. */
function declarationsOf(selector: string): Record<string, string> {
  const out: Record<string, string> = {}
  root.walkRules((rule) => {
    if (!rule.selectors.includes(selector)) return
    rule.walkDecls((d) => {
      out[d.prop] = d.value
    })
  })
  return out
}

describe('form loading state style', () => {
  it('stays a centred column at least 120px tall', () => {
    const d = declarationsOf('.form-sheet-loading')
    expect(d['display']).toBe('flex')
    expect(d['flex-direction']).toBe('column')
    expect(d['align-items']).toBe('center')
    expect(d['justify-content']).toBe('center')
    expect(d['min-height']).toBe('120px')
  })

  it('a status message does not share the loading rule and keeps its own left alignment', () => {
    const d = declarationsOf('.form-notice')
    expect(d['text-align']).toBe('left')
    expect(d['min-height']).toBeUndefined()
    expect(d['justify-content']).toBeUndefined()
  })
})
