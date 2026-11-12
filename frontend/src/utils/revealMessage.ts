/**
 * Ref callback for an error message under the fields of a form: on a 320 px screen it sits below
 * the visible part of the sheet, so it scrolls itself into view. Stable identity: it runs once,
 * when the message appears, not on every render.
 */
export function revealMessage(element: HTMLElement | null): void {
  element?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
}
