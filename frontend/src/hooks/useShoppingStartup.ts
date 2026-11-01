import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchPendingPurchase } from '../api/shopping'
import { browserStorage, resolveStartup } from '../utils/shoppingPending'

/** Once per app start: bring the user back to a remembered shopping result / wait. */
export function useShoppingStartup(): void {
  const navigate = useNavigate()
  const startedRef = useRef(false)

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    void resolveStartup(browserStorage(), fetchPendingPurchase, {
      pathname: window.location.pathname,
      search: window.location.search,
    }).then((r) => {
      if (r.kind === 'open') navigate(`/shopping/trip?purchase=${r.id}`, { replace: true })
      else if (r.kind === 'waiting') navigate('/shopping', { replace: true })
    })
  }, [navigate])
}
