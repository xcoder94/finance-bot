import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = readFileSync(new URL('../../index.css', import.meta.url), 'utf8')

describe('weak (CSS text): layouts that only a real 320 px screen shows', () => {
  it('theme row below 360px stacks the switch under the label at full width', () => {
    const media = css.slice(css.indexOf('@media (max-width: 359px) {\n  .settings-toc-row--static'))
    expect(media).toMatch(/\.settings-toc-row--static \{[^}]*flex-wrap: wrap/)
    expect(media).toMatch(/\.settings-toc-row--static \.theme-switch \{[^}]*width: 100%/)
  })
  it('sheet footer is separated from scrolling content by a shadow', () => {
    const rule = css.match(/\.form-sheet-actions \{[^}]*\}/)?.[0] ?? ''
    expect(rule).toContain('box-shadow')
  })
})
