import type { AdminUser, AdminUsersPage } from '../api/admin'
import { appendUsersPage } from './adminFormat'

export type AdminUsersState = {
  status: 'loading' | 'ready' | 'error'
  /** Query the current list belongs to; late responses for another query are ignored. */
  q: string
  items: AdminUser[]
  total: number
  nextCursor: string | null
  loadingMore: boolean
  moreFailed: boolean
}

export const initialUsersState: AdminUsersState = {
  status: 'loading',
  q: '',
  items: [],
  total: 0,
  nextCursor: null,
  loadingMore: false,
  moreFailed: false,
}

export type AdminUsersAction =
  | { type: 'search'; q: string }
  | { type: 'more' }
  | { type: 'loaded'; q: string; page: AdminUsersPage; append?: boolean }
  | { type: 'failed'; q: string }

export function adminUsersReducer(state: AdminUsersState, action: AdminUsersAction): AdminUsersState {
  switch (action.type) {
    case 'search':
      return { ...initialUsersState, q: action.q }
    case 'more':
      return { ...state, loadingMore: true, moreFailed: false }
    case 'loaded': {
      if (action.q !== state.q) return state
      return {
        status: 'ready',
        q: state.q,
        items: action.append ? appendUsersPage(state.items, action.page.items) : action.page.items,
        total: action.page.total,
        nextCursor: action.page.next_cursor,
        loadingMore: false,
        moreFailed: false,
      }
    }
    case 'failed': {
      if (action.q !== state.q) return state
      if (state.loadingMore) return { ...state, loadingMore: false, moreFailed: true }
      return { ...state, status: 'error' }
    }
  }
}
