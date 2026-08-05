import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchTransaction, TransactionsApiError } from '../api/transactions'
import { editRouteForItem } from '../utils/editRouteForItem'
import { clearTxParamFromUrl, resolveTxLaunchAction } from '../utils/txDeepLink'

export type TxDeepLinkPhase = 'resolving' | 'done'

function initialPhase(): TxDeepLinkPhase {
  const action = resolveTxLaunchAction(window.location.search)
  return action.kind === 'fetch' ? 'resolving' : 'done'
}

export function useTxDeepLink(): TxDeepLinkPhase {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<TxDeepLinkPhase>(initialPhase)
  const startedRef = useRef(false)

  useEffect(() => {
    if (startedRef.current) {
      return
    }
    startedRef.current = true

    const action = resolveTxLaunchAction(window.location.search)
    if (action.kind === 'none') {
      return
    }

    if (action.kind === 'invalid') {
      clearTxParamFromUrl()
      setPhase('done')
      return
    }

    void (async () => {
      try {
        const transaction = await fetchTransaction(action.transactionId)
        clearTxParamFromUrl()
        navigate(editRouteForItem({ id: transaction.id, type: transaction.type }), {
          replace: true,
        })
        setPhase('done')
      } catch (error) {
        clearTxParamFromUrl()
        if (error instanceof TransactionsApiError && error.status === 404) {
          navigate('/transaction-gone', { replace: true })
        }
        setPhase('done')
      }
    })()
  }, [navigate])

  return phase
}
