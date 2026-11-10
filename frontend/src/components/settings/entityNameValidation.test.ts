import { describe, expect, it } from 'vitest'

import { ENTITY_NAME_MAX_LENGTH, clampEntityName, pasteOverflows, validateEntityName } from './entityNameValidation'

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

describe('name clamp and paste overflow (B11)', () => {
  it('clamps 40 chars to 30', () => {
    expect(clampEntityName('a'.repeat(40))).toHaveLength(30)
    expect(clampEntityName('short')).toBe('short')
  })
  it('detects a paste that does not fit', () => {
    expect(pasteOverflows('', 0, 0, 'a'.repeat(40))).toBe(true)
    expect(pasteOverflows('a'.repeat(25), 25, 25, 'b'.repeat(6))).toBe(true)
    expect(pasteOverflows('a'.repeat(25), 25, 25, 'b'.repeat(5))).toBe(false)
    // replacing a selection frees room
    expect(pasteOverflows('a'.repeat(30), 0, 30, 'b'.repeat(30))).toBe(false)
  })
})
