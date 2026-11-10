export const ENTITY_NAME_MAX_LENGTH = 30

export type EntityNameValidationError = 'required' | 'tooLong'

export function validateEntityName(name: string): EntityNameValidationError | null {
  const trimmed = name.trim()

  if (trimmed.length === 0) {
    return 'required'
  }

  if (trimmed.length > ENTITY_NAME_MAX_LENGTH) {
    return 'tooLong'
  }

  return null
}

/** Cut a name to the 30-char limit (pasted/IME text can slip past the input). */
export function clampEntityName(value: string): string {
  return value.length > ENTITY_NAME_MAX_LENGTH ? value.slice(0, ENTITY_NAME_MAX_LENGTH) : value
}

/** True when pasting `pasted` over the selection would exceed the limit (the browser then cuts it). */
export function pasteOverflows(
  current: string,
  selectionStart: number,
  selectionEnd: number,
  pasted: string,
): boolean {
  const kept = current.length - Math.max(0, selectionEnd - selectionStart)
  return kept + pasted.length > ENTITY_NAME_MAX_LENGTH
}
