import { describe, expect, it } from 'vitest'

import { adminUsersReducer, initialUsersState } from './adminUsersState'

const u = (id: string) => ({ id, first_name: id }) as never
const page = (ids: string[], next: string | null, total = 5) => ({
  items: ids.map(u),
  total,
  next_cursor: next,
})

describe('adminUsersReducer', () => {
  it('starts loading, then holds the first page', () => {
    let s = adminUsersReducer(initialUsersState, { type: 'search', q: '' })
    expect(s.status).toBe('loading')
    s = adminUsersReducer(s, { type: 'loaded', q: '', page: page(['1', '2'], 'c1') })
    expect(s.status).toBe('ready')
    expect(s.items).toHaveLength(2)
    expect(s.nextCursor).toBe('c1')
    expect(s.total).toBe(5)
  })

  it('"more" appends the next page without duplicates and ends with no cursor', () => {
    let s = adminUsersReducer(initialUsersState, { type: 'search', q: '' })
    s = adminUsersReducer(s, { type: 'loaded', q: '', page: page(['1', '2'], 'c1') })
    s = adminUsersReducer(s, { type: 'more' })
    expect(s.loadingMore).toBe(true)
    s = adminUsersReducer(s, { type: 'loaded', q: '', append: true, page: page(['2', '3'], null) })
    expect(s.items.map((x: { id: string }) => x.id)).toEqual(['1', '2', '3'])
    expect(s.nextCursor).toBeNull()
    expect(s.loadingMore).toBe(false)
  })

  it('a new search replaces the list and drops the old cursor', () => {
    let s = adminUsersReducer(initialUsersState, { type: 'search', q: '' })
    s = adminUsersReducer(s, { type: 'loaded', q: '', page: page(['1'], 'c1') })
    s = adminUsersReducer(s, { type: 'search', q: 'ali' })
    expect(s.items).toEqual([])
    expect(s.nextCursor).toBeNull()
    expect(s.status).toBe('loading')
  })

  it('ignores a late response for an outdated query', () => {
    let s = adminUsersReducer(initialUsersState, { type: 'search', q: 'ali' })
    s = adminUsersReducer(s, { type: 'loaded', q: 'al', page: page(['9'], null) })
    expect(s.status).toBe('loading')
    expect(s.items).toEqual([])
  })

  it('an error on the first page shows error; on "more" keeps the list', () => {
    let s = adminUsersReducer(initialUsersState, { type: 'search', q: '' })
    expect(adminUsersReducer(s, { type: 'failed', q: '' }).status).toBe('error')
    s = adminUsersReducer(s, { type: 'loaded', q: '', page: page(['1'], 'c1') })
    s = adminUsersReducer(s, { type: 'more' })
    s = adminUsersReducer(s, { type: 'failed', q: '' })
    expect(s.status).toBe('ready')
    expect(s.items).toHaveLength(1)
    expect(s.loadingMore).toBe(false)
    expect(s.moreFailed).toBe(true)
  })
})
