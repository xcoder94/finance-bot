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
