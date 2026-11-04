import { useEffect, useRef, useState } from 'react'
import { Spinner } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { monthDateRange } from '../api/home'
import { fetchHistoryPage, type HistoryItem } from '../api/history'
import type { Wallet } from '../api/transactions'
import { BlockError } from '../components/BlockError'
import { WalletOpsView } from '../components/wallets/WalletOpsView'
import { peekWallets, useDataCacheStore } from '../store/dataCacheStore'
import { useAuthStore } from '../store/authStore'
import { editRouteForItem } from '../utils/editRouteForItem'
import { currentMonthInTashkent, shiftHomeMonth, type HomeMonth } from '../utils/homeMonth'
import {
  createWalletOpsController,
  leaveIfWalletMissing,
  resolveWalletScreen,
  type WalletOpsController,
  type WalletOpsState,
} from '../utils/walletOps'
import { loadFreshWallets, subscribeWalletsRefresh } from '../utils/walletsOverview'

type WalletsState = { wallets: Wallet[] | null; fresh: boolean; failed: boolean }

const LOADING_OPS: WalletOpsState = {
  status: 'loading',
  items: [],
  total: 0,
  loadingMore: false,
  loadMoreError: false,
}

export function WalletDetailPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const { id: walletId = '' } = useParams()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId) ?? ''
  const homeEpoch = useDataCacheStore((state) => state.homeEpoch)

  const [month, setMonth] = useState<HomeMonth>(currentMonthInTashkent)
  const [refreshCount, setRefreshCount] = useState(0)
  const [walletsState, setWalletsState] = useState<WalletsState>(() => ({
    wallets: peekWallets(familyId),
    fresh: false,
    failed: false,
  }))
  const [ops, setOps] = useState<WalletOpsState>(LOADING_OPS)
  const controller = useRef<WalletOpsController | null>(null)

  useEffect(
    () => subscribeWalletsRefresh(document, () => setRefreshCount((count) => count + 1)),
    [],
  )

  // Balance and wallet list: refetched after every save/delete in a form and on return to the app.
  useEffect(() => {
    if (!familyId) return
    let cancelled = false
    void loadFreshWallets(familyId)
      .then((wallets) => {
        if (!cancelled) setWalletsState({ wallets, fresh: true, failed: false })
      })
      .catch(() => {
        if (!cancelled) setWalletsState((prev) => ({ ...prev, failed: true }))
      })
    return () => {
      cancelled = true
    }
  }, [familyId, homeEpoch, refreshCount])

  useEffect(() => {
    const next = createWalletOpsController({
      fetchPage: (range, limit, offset) =>
        fetchHistoryPage(range.dateFrom, range.dateTo, limit, offset, undefined, walletId),
      onChange: setOps,
    })
    controller.current = next
    return () => {
      next.dispose()
      controller.current = null
    }
  }, [walletId])

  const { year, month: monthNumber } = month
  useEffect(() => {
    void controller.current?.setPeriod(monthDateRange(year, monthNumber))
  }, [walletId, year, monthNumber])

  // Same list, same month, new data: skip the first run (the period effect already loads).
  const refreshTrigger = homeEpoch + refreshCount
  const seenTrigger = useRef(refreshTrigger)
  useEffect(() => {
    if (seenTrigger.current === refreshTrigger) return
    seenTrigger.current = refreshTrigger
    void controller.current?.refresh()
  }, [refreshTrigger])

  const screen = resolveWalletScreen(walletsState.wallets, walletsState.fresh, walletId)
  const missing = screen.kind === 'missing'
  useEffect(() => {
    leaveIfWalletMissing({ kind: missing ? 'missing' : 'loading' }, navigate)
  }, [missing, navigate])

  if (screen.kind !== 'ready') {
    if (screen.kind === 'loading' && walletsState.failed) {
      return (
        <div className="page-content home-page wallets-page">
          <BlockError onRetry={() => setRefreshCount((count) => count + 1)} />
        </div>
      )
    }
    return (
      <div className="page-content home-page wallets-page">
        <div className="home-block-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      </div>
    )
  }

  return (
    <WalletOpsView
      wallet={screen.wallet}
      month={month}
      ops={ops}
      onPrevMonth={() => setMonth((current) => shiftHomeMonth(current, -1))}
      onNextMonth={() => setMonth((current) => shiftHomeMonth(current, 1))}
      onOpenItem={(item: HistoryItem) =>
        navigate(editRouteForItem(item), { state: { background: location } })
      }
      onRetry={() => void controller.current?.retry()}
      onLoadMore={() => void controller.current?.loadMore()}
    />
  )
}
