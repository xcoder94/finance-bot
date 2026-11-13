import { describe, expect, it } from 'vitest'
import { matchCategoryInBudget } from './matchCategory'

const old = [
  { id: 'a', name: 'Еда', parent_id: null },
  { id: 'a1', name: 'Кафе', parent_id: 'a' },
  { id: 'b1', name: 'Кафе', parent_id: 'b' },
  { id: 'b', name: 'Отдых', parent_id: null },
]
const next = [
  { id: 'A', name: ' еда ', parent_id: null },
  { id: 'A1', name: 'Кафе', parent_id: 'A' },
  { id: 'B', name: 'Отдых', parent_id: null },
]
describe('matchCategoryInBudget', () => {
  it('finds a top-level category by name', () => expect(matchCategoryInBudget(old, next, 'a')).toBe('A'))
  it('a subcategory needs its parent to match too', () => {
    expect(matchCategoryInBudget(old, next, 'a1')).toBe('A1')
    expect(matchCategoryInBudget(old, next, 'b1')).toBeNull()
  })
  it('matches by translation key before name', () =>
    expect(matchCategoryInBudget([{ id: 'x', name: 'Food', translation_key: 'k' }], [{ id: 'y', name: 'Еда', translation_key: 'k' }], 'x')).toBe('y'))
  it('null when absent', () => expect(matchCategoryInBudget(old, [], 'a')).toBeNull())
})
