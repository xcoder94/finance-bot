import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { fetchAdminOverview, fetchAdminUsers, type AdminOverview } from '../../api/admin'
import { AdminScreen } from '../../components/admin/AdminScreen'
import type { AdminTab } from '../../components/admin/AdminTabs'
import type { Loadable } from '../../components/admin/GrowthView'
import { useAuthStore } from '../../store/authStore'
import { adminRedirectTarget } from '../../utils/adminGuard'
import { adminUsersReducer, initialUsersState } from '../../utils/adminUsersState'

const SEARCH_DEBOUNCE_MS = 350
const PAGE_SIZE = 50

function AdminContainer() {
  const [tab, setTab] = useState<AdminTab>('growth')
  const [growth, setGrowth] = useState<Loadable<AdminOverview>>({ status: 'loading' })
  const [growthTry, setGrowthTry] = useState(0)
  const [users, dispatch] = useReducer(adminUsersReducer, initialUsersState)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [usersTry, setUsersTry] = useState(0)
  const usersOpened = useRef(false)
  if (tab === 'users') usersOpened.current = true

  // Growth loads when its tab is open (and again on retry).
  useEffect(() => {
    if (tab !== 'growth') return
    let cancelled = false
    setGrowth({ status: 'loading' })
    fetchAdminOverview()
      .then((data) => !cancelled && setGrowth({ status: 'ready', data }))
      .catch(() => !cancelled && setGrowth({ status: 'error' }))
    return () => {
      cancelled = true
    }
  }, [tab, growthTry])

  useEffect(() => {
    const id = setTimeout(() => setDebouncedQuery(query.trim()), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(id)
  }, [query])

  // The users list loads when its tab is open and reloads when the debounced query changes.
  useEffect(() => {
    if (tab !== 'users') return
    let cancelled = false
    dispatch({ type: 'search', q: debouncedQuery })
    fetchAdminUsers({ q: debouncedQuery, limit: PAGE_SIZE })
      .then((page) => !cancelled && dispatch({ type: 'loaded', q: debouncedQuery, page }))
      .catch(() => !cancelled && dispatch({ type: 'failed', q: debouncedQuery }))
    return () => {
      cancelled = true
    }
  }, [tab, debouncedQuery, usersTry])

  const onMore = useCallback(() => {
    if (!users.nextCursor || users.loadingMore) return
    const q = users.q
    dispatch({ type: 'more' })
    fetchAdminUsers({ q, cursor: users.nextCursor, limit: PAGE_SIZE })
      .then((page) => dispatch({ type: 'loaded', q, page, append: true }))
      .catch(() => dispatch({ type: 'failed', q }))
  }, [users.nextCursor, users.loadingMore, users.q])

  return (
    <AdminScreen
      tab={tab}
      onTab={setTab}
      growth={growth}
      onRetryGrowth={() => setGrowthTry((n) => n + 1)}
      users={users}
      query={query}
      onQuery={setQuery}
      onMore={onMore}
      onRetryUsers={() => setUsersTry((n) => n + 1)}
    />
  )
}

export function AdminPage() {
  const isAdmin = useAuthStore((state) => state.user?.isAdmin ?? false)
  const target = adminRedirectTarget(isAdmin)
  if (target) {
    return <Navigate to={target} replace />
  }
  return <AdminContainer />
}
