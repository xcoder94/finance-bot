import { describe, expect, it, vi } from 'vitest'

import { revealMessage } from './revealMessage'

// The error message sits at the end of the fields; the Cancel/Save row is sticky over the panel's
// bottom edge. The message must end up above that row (visible without scrolling by hand).
function scene(messageBottom: number, footerTop: number | null) {
  const scrollBy = vi.fn()
  const footer = footerTop === null ? null : { getBoundingClientRect: () => ({ top: footerTop }) }
  const panel = { querySelector: () => footer, scrollBy }
  const element = {
    scrollIntoView: vi.fn(),
    closest: () => panel,
    getBoundingClientRect: () => ({ bottom: messageBottom }),
  }
  return { element: element as unknown as HTMLElement, scrollBy, scrollIntoView: element.scrollIntoView }
}

describe('revealMessage', () => {
  it('message under the sticky footer: panel is scrolled by the covered part', () => {
    const s = scene(706, 600)
    revealMessage(s.element)
    expect(s.scrollIntoView).toHaveBeenCalled()
    expect(s.scrollBy).toHaveBeenCalledWith({ top: 106 + 8 })
  })

  it('message already above the footer: no extra scrolling', () => {
    const s = scene(500, 600)
    revealMessage(s.element)
    expect(s.scrollBy).not.toHaveBeenCalled()
  })

  it('form without a footer: only scrolls into view', () => {
    const s = scene(706, null)
    revealMessage(s.element)
    expect(s.scrollIntoView).toHaveBeenCalled()
    expect(s.scrollBy).not.toHaveBeenCalled()
  })
})
