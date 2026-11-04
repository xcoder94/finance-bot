import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { Wallet } from '../api/transactions'
import { WalletsView } from '../components/wallets/WalletsView'
import { useAuthStore } from '../store/authStore'
import { peekWallets, useDataCacheStore } from '../store/dataCacheStore'
import { walletOpsPath } from '../utils/walletOps'
import { loadFreshWallets, subscribeWalletsRefresh } from '../utils/walletsOverview'

type State = { status: 'loading' | 'error' | 'success'; wallets: Wallet[] }

export function WalletsPage() {
  const navigate = useNavigate()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId) ?? ''
  const homeEpoch = useDataCacheStore((state) => state.homeEpoch)
  const [state, setState] = useState<State>(() => {
    const cached = peekWallets(familyId)
    return cached ? { status: 'success', wallets: cached } : { status: 'loading', wallets: [] }
  })
  const [refreshCount, setRefreshCount] = useState(0)

  useEffect(
    () => subscribeWalletsRefresh(document, () => setRefreshCount((count) => count + 1)),
    [],
  )

  useEffect(() => {
    if (!familyId) return
    let cancelled = false
    void loadFreshWallets(familyId)
      .then((wallets) => {
        if (!cancelled) setState({ status: 'success', wallets })
      })
      .catch(() => {
        // keep what is already on screen on a background refresh failure
        if (!cancelled) {
          setState((prev) => (prev.status === 'success' ? prev : { status: 'error', wallets: [] }))
        }
      })
    return () => {
      cancelled = true
    }
  }, [familyId, homeEpoch, refreshCount])

  return (
    <WalletsView
      onOpenWallet={(id) => navigate(walletOpsPath(id))}
      status={state.status}
      wallets={state.wallets}
      onRetry={() => {
        setState({ status: 'loading', wallets: [] })
        setRefreshCount((count) => count + 1)
      }}
    />
  )
}
