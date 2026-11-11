import { useDataCacheStore } from '../../store/dataCacheStore'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { fetchHistoryPage, fetchSummaryForRange, type HistoryItem, type SummaryResponse } from '../../api/history'
import { fetchWallets } from '../../api/transactions'
import { HistoryTransactionList } from '../../components/history/HistoryTransactionList'
import { useAnalyticsContext } from '../../contexts/AnalyticsContext'
import {
  buildAnalyticsHistoryFetchKey,
  getAnalyticsHistoryExpenseCategoryId,
  excludePersonalWalletRows,
  historyListStatus,
  historyCurrencyParam,
  isAnalyticsHistoryUncategorized,
  isQuietHistoryRefresh,
  planSilentHistoryRefresh,
  summaryAfterResult,
  summaryForRequest,
  type KeyedSummary,
} from '../../utils/analyticsHistoryTab'
import { applyClearHistoryFilter } from '../../utils/analyticsTabState'
import { HistorySummaryLine } from './HistorySummaryLine'
import { editRouteForItem } from '../../utils/editRouteForItem'

const HISTORY_PAGE_SIZE = 50

export function AnalyticsHistoryTab() {
  const homeEpoch = useDataCacheStore((state) => state.homeEpoch)
  const { t } = useTranslation()
  const navigate = useNavigate()
  const {
    range,
    rangeFetchEnabled,
    rangeKey,
    historyCategoryFilter,
    setHistoryCategoryFilter,
    setActiveTab,
    drillParent,
    activeTab,
    periodTab,
    selectedMonth,
    rangeFrom,
    rangeTo,
    rangeFromTouched,
    rangeToTouched,
    currency,
  } = useAnalyticsContext()

  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyStatus, setHistoryStatus] = useState<'idle' | 'loading' | 'error' | 'success'>(
    'idle',
  )
  const [historyRetryCount, setHistoryRetryCount] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadMoreError, setLoadMoreError] = useState(false)
  const lastIdentity = useRef<string | null>(null)
  const loadedCount = useRef(0)
  loadedCount.current = historyItems.length

  const [summaryState, setSummaryState] = useState<KeyedSummary<SummaryResponse> | null>(null)
  const summary = summaryState?.data ?? null

  useEffect(() => {
    if (!range || !rangeFetchEnabled) {
      setSummaryState(null)
      return
    }
    let cancelled = false
    const key = `${range.dateFrom}|${range.dateTo}`
    setSummaryState((shown) => summaryForRequest(shown, key))
    void fetchSummaryForRange(range.dateFrom, range.dateTo)
      .then((data) => {
        if (!cancelled) {
          setSummaryState((shown) => summaryAfterResult(shown, key, data))
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSummaryState((shown) => summaryAfterResult(shown, key, null))
        }
      })
    return () => {
      cancelled = true
    }
  }, [range, rangeFetchEnabled, homeEpoch])

  const historyFetchKey = useMemo(
    () => buildAnalyticsHistoryFetchKey(rangeKey, historyCategoryFilter),
    [rangeKey, historyCategoryFilter],
  )

  const expenseCategoryId = useMemo(
    () => getAnalyticsHistoryExpenseCategoryId(historyCategoryFilter),
    [historyCategoryFilter],
  )

  const uncategorized = isAnalyticsHistoryUncategorized(historyCategoryFilter)
  const currencyParam = historyCurrencyParam(historyCategoryFilter, currency)

  const [personalWalletIds, setPersonalWalletIds] = useState<ReadonlySet<string>>(new Set())
  const [walletsReady, setWalletsReady] = useState(false)
  const filterActive = historyCategoryFilter !== null
  useEffect(() => {
    if (!filterActive) {
      setWalletsReady(false)
      return
    }
    let cancelled = false
    void fetchWallets()
      .then((wallets) => {
        if (!cancelled) {
          setPersonalWalletIds(new Set(wallets.filter((w) => w.is_personal).map((w) => w.id)))
          setWalletsReady(true)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setWalletsReady(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [filterActive])

  useEffect(() => {
    if (!range || !rangeFetchEnabled) {
      setHistoryItems([])
      setHistoryTotal(0)
      setHistoryStatus('idle')
      lastIdentity.current = null
      return
    }

    let cancelled = false
    const identity = [
      range.dateFrom,
      range.dateTo,
      historyFetchKey,
      expenseCategoryId ?? '',
      String(uncategorized),
      currencyParam ?? '',
      historyRetryCount,
    ].join('|')
    const quiet = isQuietHistoryRefresh(
      lastIdentity.current,
      identity,
      loadedCount.current > 0,
    )
    lastIdentity.current = identity

    if (quiet) {
      // Return to the app: re-read every row already shown and swap them in at once; the list
      // never empties, so the scroll position and the loaded pages stay.
      const plan = planSilentHistoryRefresh(loadedCount.current, HISTORY_PAGE_SIZE)
      void Promise.all(
        plan.map((step) =>
          fetchHistoryPage(
            range.dateFrom,
            range.dateTo,
            step.limit,
            step.offset,
            expenseCategoryId,
            undefined,
            uncategorized,
            currencyParam,
          ),
        ),
      )
        .then((pages) => {
          if (cancelled) return
          setHistoryItems(pages.flatMap((page) => page.items))
          setHistoryTotal(pages[pages.length - 1]?.total_count ?? 0)
        })
        .catch(() => {
          // keep the rows on screen; the next return tries again
        })
      return () => {
        cancelled = true
      }
    }

    setHistoryStatus('loading')
    setHistoryItems([])
    setHistoryTotal(0)
    setLoadMoreError(false)

    void fetchHistoryPage(
      range.dateFrom,
      range.dateTo,
      HISTORY_PAGE_SIZE,
      0,
      expenseCategoryId,
      undefined,
      uncategorized,
      currencyParam,
    )
      .then((data) => {
        if (!cancelled) {
          setHistoryItems(data.items)
          setHistoryTotal(data.total_count)
          setHistoryStatus('success')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHistoryStatus('error')
        }
      })

    return () => {
      cancelled = true
    }
  }, [range, rangeFetchEnabled, historyFetchKey, expenseCategoryId, uncategorized, currencyParam, historyRetryCount, homeEpoch])

  const shownItems = useMemo(
    () => (filterActive ? excludePersonalWalletRows(historyItems, personalWalletIds) : historyItems),
    [historyItems, personalWalletIds, filterActive],
  )

  const handleLoadMore = async () => {
    if (!range || loadingMore || historyItems.length >= historyTotal) {
      return
    }

    setLoadingMore(true)
    setLoadMoreError(false)
    try {
      const data = await fetchHistoryPage(
        range.dateFrom,
        range.dateTo,
        HISTORY_PAGE_SIZE,
        historyItems.length,
        expenseCategoryId,
        undefined,
        uncategorized,
        currencyParam,
      )
      setHistoryItems((current) => [...current, ...data.items])
      setHistoryTotal(data.total_count)
    } catch {
      setLoadMoreError(true)
    } finally {
      setLoadingMore(false)
    }
  }

  const handleClearFilter = useCallback(() => {
    const next = applyClearHistoryFilter(
      {
        activeTab,
        periodTab,
        selectedMonth,
        rangeFrom,
        rangeTo,
        rangeFromTouched,
        rangeToTouched,
        currency,
        drillParent,
        historyCategoryFilter,
      },
      { returnToDrill: true },
    )
    setHistoryCategoryFilter(next.historyCategoryFilter)
    setActiveTab(next.activeTab)
  }, [
    activeTab,
    currency,
    drillParent,
    historyCategoryFilter,
    periodTab,
    rangeFrom,
    rangeFromTouched,
    rangeTo,
    rangeToTouched,
    selectedMonth,
    setActiveTab,
    setHistoryCategoryFilter,
  ])

  const handleItemClick = useCallback(
    (item: HistoryItem) => {
      navigate(editRouteForItem(item), { state: { from: 'analytics' } })
    },
    [navigate],
  )

  return (
    <div className="analytics-history-tab">
      {historyCategoryFilter ? null : <HistorySummaryLine summary={summary} />}

      {historyCategoryFilter ? (
        <div className="analytics-history-filter">
          <span
            className="analytics-history-filter__dot"
            style={{ background: historyCategoryFilter.color }}
            aria-hidden="true"
          />
          <span className="analytics-history-filter__name">{historyCategoryFilter.name}</span>
          <button type="button" className="analytics-history-filter__reset" onClick={handleClearFilter}>
            {t('analytics.resetFilter')}
          </button>
        </div>
      ) : null}

      <HistoryTransactionList
        status={historyListStatus(historyStatus, filterActive, walletsReady)}
        items={shownItems}
        groupByDay
        totalCount={shownItems.length + Math.max(0, historyTotal - historyItems.length)}
        onItemClick={handleItemClick}
        onRetry={() => setHistoryRetryCount((count) => count + 1)}
        loadingMore={loadingMore}
        loadMoreError={loadMoreError}
        onLoadMore={() => void handleLoadMore()}
      />
    </div>
  )
}
