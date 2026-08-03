import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { fetchHistoryPage, type HistoryItem } from '../../api/history'
import { HistoryTransactionList } from '../../components/history/HistoryTransactionList'
import { useAnalyticsContext } from '../../contexts/AnalyticsContext'
import {
  buildAnalyticsHistoryFetchKey,
  getAnalyticsHistoryExpenseCategoryId,
} from '../../utils/analyticsHistoryTab'
import { applyClearHistoryFilter } from '../../utils/analyticsTabState'
import { editRouteForItem } from '../../utils/editRouteForItem'

const HISTORY_PAGE_SIZE = 50

export function AnalyticsHistoryTab() {
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

  const historyFetchKey = useMemo(
    () => buildAnalyticsHistoryFetchKey(rangeKey, historyCategoryFilter),
    [rangeKey, historyCategoryFilter],
  )

  const expenseCategoryId = useMemo(
    () => getAnalyticsHistoryExpenseCategoryId(historyCategoryFilter),
    [historyCategoryFilter],
  )

  useEffect(() => {
    if (!range || !rangeFetchEnabled) {
      setHistoryItems([])
      setHistoryTotal(0)
      setHistoryStatus('idle')
      return
    }

    let cancelled = false
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
  }, [range, rangeFetchEnabled, historyFetchKey, expenseCategoryId, historyRetryCount])

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
        status={historyStatus}
        items={historyItems}
        totalCount={historyTotal}
        onItemClick={handleItemClick}
        onRetry={() => setHistoryRetryCount((count) => count + 1)}
        loadingMore={loadingMore}
        loadMoreError={loadMoreError}
        onLoadMore={() => void handleLoadMore()}
      />
    </div>
  )
}
