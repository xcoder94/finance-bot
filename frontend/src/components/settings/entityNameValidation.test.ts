import { describe, expect, it } from 'vitest'

import { ENTITY_NAME_MAX_LENGTH, validateEntityName } from './entityNameValidation'

describe('entityNameValidation', () => {
  it('caps name length at 30', () => {
    expect(ENTITY_NAME_MAX_LENGTH).toBe(30)
  })

  it('rejects empty and whitespace-only names', () => {
    expect(validateEntityName('')).toBe('required')
    expect(validateEntityName('   ')).toBe('required')
  })

  it('accepts names up to 30 characters', () => {
    expect(validateEntityName('a'.repeat(30))).toBeNull()
  })

  it('rejects names longer than 30 characters', () => {
    expect(validateEntityName('a'.repeat(31))).toBe('tooLong')
  })
})
