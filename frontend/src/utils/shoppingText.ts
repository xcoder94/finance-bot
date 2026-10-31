/** Product ceiling, same as backend (1-60 characters, emoji count as one). */
export const MAX_SHOPPING_NAME = 60

export function clipShoppingName(raw: string): string {
  return Array.from(raw).slice(0, MAX_SHOPPING_NAME).join('')
}

/** Trim, collapse inner whitespace, clip to the limit. Mirrors the backend normalisation. */
export function normalizeShoppingName(raw: string): string {
  return clipShoppingName(raw.replace(/\s+/g, ' ').trim())
}

export function sameShoppingName(a: string, b: string): boolean {
  return a.toLocaleLowerCase() === b.toLocaleLowerCase()
}
