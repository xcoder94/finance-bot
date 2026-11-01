import { useEffect, useReducer, useState } from 'react'

import { fetchAdminUsage, type AdminUsagePeriod } from '../api/admin'
import { initialOpsState, opsReducer } from '../utils/adminOps'

/** State of the "Operations & AI" tab: loads when open, again on a period change or retry. */
export function useAdminOps(active: boolean) {
  const [ops, dispatch] = useReducer(opsReducer, initialOpsState)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!active) return
    let cancelled = false
    const period = ops.period
    fetchAdminUsage(period)
      .then((data) => !cancelled && dispatch({ type: 'loaded', period, data }))
      .catch(() => !cancelled && dispatch({ type: 'failed', period }))
    return () => {
      cancelled = true
    }
  }, [active, ops.period, attempt])

  return {
    ops,
    onPeriod: (period: AdminUsagePeriod) => dispatch({ type: 'select', period }),
    onRetry: () => {
      dispatch({ type: 'retry' })
      setAttempt((n) => n + 1)
    },
  }
}
