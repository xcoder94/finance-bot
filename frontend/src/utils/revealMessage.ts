/**
 * Ref callback for an error message under the fields of a form: on a small screen it sits below
 * the visible part of the sheet, or right under the sticky Cancel/Save row, so it scrolls itself
 * into view above that row. Stable identity: it runs once, when the message appears, not on every render.
 * A sheet that has just been (re)opened is still sliding up, its rectangles are not final: wait for that.
 */
export function revealMessage(element: HTMLElement | null): void {
  if (!element) return
  const panel = element.closest?.('.form-sheet-panel') as HTMLElement | null
  const place = () => {
    element.scrollIntoView?.({ block: 'nearest' })
    const footer = panel?.querySelector?.('.form-sheet-actions') as HTMLElement | null
    if (!panel || !footer) return
    // nearest only reaches the panel's bottom edge, which the sticky row covers: lift the message above the row
    const hidden = element.getBoundingClientRect().bottom - footer.getBoundingClientRect().top
    if (hidden > 0) panel.scrollBy?.({ top: hidden + 8 })
  }
  const running = panel?.getAnimations?.() ?? []
  if (running.length === 0) {
    place()
    return
  }
  void Promise.all(running.map((animation) => animation.finished)).then(place, place)
}
