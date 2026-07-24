import {
  type ClipboardEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { Button, Input, SegmentedControl, Spinner, Text, Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import { monthDateRange } from '../api/home'
import { fetchHistoryPage, fetchSummaryForRange, type HistoryItem, type SummaryResponse } from '../api/history'
import { TransactionDetailModal } from '../components/TransactionDetailModal'
import i18n from '../i18n'
import { formatCurrency, type Currency } from '../utils/formatCurrency'
import {
  getHistoryItemSubtitle,
  getHistoryItemTitle,
} from '../utils/getDisplayName'
import {
  extractDigits,
  formatDateDigits,
  isoDateToMaskedDate,
  isValidMaskedDate,
  maskedDateToUtcEndIso,
  maskedDateToUtcStartIso,
} from '../utils/transactionForm'

const CURRENCIES = ['UZS', 'USD'] as const
const HISTORY_PAGE_SIZE = 50

type PeriodTab = 'month' | 'range'

type SelectedMonth = {
  year: number
  month: number
}

type FetchState<T> =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; data: T }

type ResolvedRange = {
  dateFrom: string
  dateTo: string
}

function currentMonth(): SelectedMonth {
  const now = new Date()
  return { year: now.getFullYear(), month: now.getMonth() + 1 }
}

function shiftMonth(selected: SelectedMonth, delta: number): SelectedMonth {
  const date = new Date(selected.year, selected.month - 1 + delta, 1)
  return { year: date.getFullYear(), month: date.getMonth() + 1 }
}

function getLocale(): string {
  return i18n.language.startsWith('uz') ? 'uz-UZ' : 'ru-RU'
}

function formatMonthLabel(selected: SelectedMonth): string {
  return new Intl.DateTimeFormat(getLocale(), {
    month: 'long',
    year: 'numeric',
  }).format(new Date(selected.year, selected.month - 1, 1))
}

function formatTransactionDateTime(isoDate: string): string {
  const date = new Date(isoDate)
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const year = date.getFullYear()
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${day}.${month}.${year} ${hours}:${minutes}`
}

function getSummaryForCurrency(
  summary: SummaryResponse,
  currency: Currency,
): { income: number; expense: number } {
  const entry = summary.by_currency.find((row) => row.currency === currency)
  return {
    income: entry?.income ?? 0,
    expense: entry?.expense ?? 0,
  }
}

function formatSignedTransactionAmount(item: HistoryItem): string {
  const formatted = formatCurrency(item.amount, item.currency as Currency)
  if (item.type === 'income') {
    return `+${formatted}`
  }
  if (item.type === 'expense') {
    return `-${formatted}`
  }
  return formatted
}

function historyItemTitleClass(item: HistoryItem): string {
  if (item.type === 'expense') {
    return 'home-recent-item__title home-recent-item__title--expense'
  }
  if (item.type === 'income') {
    return 'home-recent-item__title home-recent-item__title--income'
  }
  return 'home-recent-item__title'
}

function historyItemAmountClass(item: HistoryItem): string {
  if (item.type === 'expense') {
    return 'home-recent-item__amount home-recent-item__amount--expense'
  }
  if (item.type === 'income') {
    return 'home-recent-item__amount home-recent-item__amount--income'
  }
  return 'home-recent-item__amount'
}

function useFetchBlock<T>(fetcher: () => Promise<T>, trigger: unknown, enabled: boolean) {
  const [state, setState] = useState<FetchState<T>>({ status: 'loading' })
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (!enabled) {
      return
    }

    let cancelled = false
    setState({ status: 'loading' })

    void fetcher()
      .then((data) => {
        if (!cancelled) {
          setState({ status: 'success', data })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: 'error' })
        }
      })

    return () => {
      cancelled = true
    }
  }, [fetcher, trigger, retryCount, enabled])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  return { state, retry }
}

function BlockError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()

  return (
    <div className="home-block-error" role="alert">
      <Text>{t('home.loadError')}</Text>
      <Button mode="plain" size="s" onClick={onRetry}>
        {t('auth.retry')}
      </Button>
    </div>
  )
}

type MetricValueProps = {
  loading: boolean
  unavailable?: boolean
  className?: string
  children: string
}

function MetricValue({ loading, unavailable, className, children }: MetricValueProps) {
  if (loading) {
    return <Spinner size="s" />
  }
  if (unavailable) {
    return <Text>—</Text>
  }
  return (
    <Text className={className} weight="2">
      {children}
    </Text>
  )
}

type MaskedDateInputProps = {
  header: string
  value: string
  onChange: (value: string) => void
  hasError: boolean
  errorText?: string
  onBlur: () => void
  onEdit: () => void
}

function MaskedDateInput({
  header,
  value,
  onChange,
  hasError,
  errorText,
  onBlur,
  onEdit,
}: MaskedDateInputProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Backspace') {
      event.preventDefault()
      onChange(formatDateDigits(extractDigits(value).slice(0, -1)))
      onEdit()
      return
    }

    if (event.key.length === 1 && /\d/.test(event.key)) {
      event.preventDefault()
      const digits = extractDigits(value)
      if (digits.length >= 8) {
        return
      }
      onChange(formatDateDigits(digits + event.key))
      onEdit()
      return
    }

    if (
      event.key.length === 1 &&
      event.key !== 'Tab' &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.altKey
    ) {
      event.preventDefault()
    }
  }

  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault()
    const pasted = extractDigits(event.clipboardData.getData('text'))
    const combined = (extractDigits(value) + pasted).slice(0, 8)
    onChange(formatDateDigits(combined))
    onEdit()
  }

  return (
    <div className="history-range-field">
      <Input
        header={header}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        value={value}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={onBlur}
        onChange={(event) => {
          const digits = extractDigits(event.target.value).slice(0, 8)
          onChange(formatDateDigits(digits))
          onEdit()
        }}
        status={hasError ? 'error' : 'default'}
      />
      {hasError && errorText ? (
        <Text className="history-range-field__error" role="alert">{errorText}</Text>
      ) : null}
    </div>
  )
}

function resolveRange(
  periodTab: PeriodTab,
  selectedMonth: SelectedMonth,
  rangeFrom: string,
  rangeTo: string,
): { range: ResolvedRange | null; rangeOrderInvalid: boolean } {
  if (periodTab === 'month') {
    return { range: monthDateRange(selectedMonth.year, selectedMonth.month), rangeOrderInvalid: false }
  }

  if (!isValidMaskedDate(rangeFrom) || !isValidMaskedDate(rangeTo)) {
    return { range: null, rangeOrderInvalid: false }
  }

  const dateFrom = maskedDateToUtcStartIso(rangeFrom)
  const dateTo = maskedDateToUtcEndIso(rangeTo)
  if (!dateFrom || !dateTo) {
    return { range: null, rangeOrderInvalid: false }
  }

  if (dateFrom > dateTo) {
    return { range: null, rangeOrderInvalid: true }
  }

  return { range: { dateFrom, dateTo }, rangeOrderInvalid: false }
}

export function HistoryPage() {
  const { t } = useTranslation()
  const [periodTab, setPeriodTab] = useState<PeriodTab>('month')
  const [selectedMonth, setSelectedMonth] = useState<SelectedMonth>(currentMonth)
  const [rangeFrom, setRangeFrom] = useState('')
  const [rangeTo, setRangeTo] = useState('')
  const [rangeInitialized, setRangeInitialized] = useState(false)
  const [rangeFromTouched, setRangeFromTouched] = useState(false)
  const [rangeToTouched, setRangeToTouched] = useState(false)

  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyStatus, setHistoryStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [historyRetryCount, setHistoryRetryCount] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadMoreError, setLoadMoreError] = useState(false)
  const [selectedListItem, setSelectedListItem] = useState<HistoryItem | null>(null)

  const { range, rangeOrderInvalid } = useMemo(
    () => resolveRange(periodTab, selectedMonth, rangeFrom, rangeTo),
    [periodTab, selectedMonth, rangeFrom, rangeTo],
  )

  const rangeKey = range ? `${range.dateFrom}|${range.dateTo}` : 'invalid'
  const rangeFetchEnabled = range !== null

  const summaryFetch = useFetchBlock(
    useCallback(() => {
      if (!range) {
        return Promise.reject(new Error('invalid range'))
      }
      return fetchSummaryForRange(range.dateFrom, range.dateTo)
    }, [range]),
    rangeKey,
    rangeFetchEnabled,
  )

  const rangeFromInvalid = periodTab === 'range' && rangeFromTouched && !isValidMaskedDate(rangeFrom)
  const rangeToInvalid = periodTab === 'range' && rangeToTouched && !isValidMaskedDate(rangeTo)
  const showRangeOrderError = periodTab === 'range' && rangeOrderInvalid && rangeFromTouched && rangeToTouched

  const handlePeriodTabChange = (tab: PeriodTab) => {
    if (tab === 'range' && !rangeInitialized) {
      const monthRange = monthDateRange(selectedMonth.year, selectedMonth.month)
      setRangeFrom(isoDateToMaskedDate(monthRange.dateFrom))
      setRangeTo(isoDateToMaskedDate(monthRange.dateTo))
      setRangeInitialized(true)
    }
    setPeriodTab(tab)
  }

  useEffect(() => {
    if (!range) {
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

    void fetchHistoryPage(range.dateFrom, range.dateTo, HISTORY_PAGE_SIZE, 0)
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
  }, [range, rangeKey, historyRetryCount])

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
      )
      setHistoryItems((current) => [...current, ...data.items])
      setHistoryTotal(data.total_count)
    } catch {
      setLoadMoreError(true)
    } finally {
      setLoadingMore(false)
    }
  }

  const summaryLoading = summaryFetch.state.status === 'loading'
  const summaryUnavailable = summaryFetch.state.status === 'error'
  const summaryData =
    summaryFetch.state.status === 'success' ? summaryFetch.state.data : null

  const showSummaryCard =
    summaryFetch.state.status === 'success' || summaryFetch.state.status === 'error'

  const transferLabels = {
    transfer: t('history.transfer'),
    exchange: t('history.exchange'),
  }

  return (
    <div className="page-content home-page history-page">
      <Title level="1" weight="2" className="home-page__title">
        {t('history.title')}
      </Title>

      <div className="segmented-control-wrap history-page__period-tabs">
        <SegmentedControl>
          <SegmentedControl.Item
            selected={periodTab === 'month'}
            onClick={() => handlePeriodTabChange('month')}
          >
            {t('history.tabMonth')}
          </SegmentedControl.Item>
          <SegmentedControl.Item
            selected={periodTab === 'range'}
            onClick={() => handlePeriodTabChange('range')}
          >
            {t('history.tabRange')}
          </SegmentedControl.Item>
        </SegmentedControl>
      </div>

      {periodTab === 'month' ? (
        <div className="home-page__month-selector">
          <button
            type="button"
            className="home-month-nav__button"
            aria-label={t('home.previousMonth')}
            onClick={() => setSelectedMonth((current) => shiftMonth(current, -1))}
          >
            ‹
          </button>
          <Text weight="2" className="home-page__month-label">
            {formatMonthLabel(selectedMonth)}
          </Text>
          <button
            type="button"
            className="home-month-nav__button"
            aria-label={t('home.nextMonth')}
            onClick={() => setSelectedMonth((current) => shiftMonth(current, 1))}
          >
            ›
          </button>
        </div>
      ) : (
        <div className="history-page__range-fields">
          <MaskedDateInput
            header={t('history.dateFrom')}
            value={rangeFrom}
            onChange={setRangeFrom}
            hasError={rangeFromInvalid}
            errorText={rangeFromInvalid ? t('history.invalidDate') : undefined}
            onBlur={() => setRangeFromTouched(true)}
            onEdit={() => {
              setRangeFromTouched(true)
              if (rangeToTouched) {
                setRangeToTouched(true)
              }
            }}
          />
          <MaskedDateInput
            header={t('history.dateTo')}
            value={rangeTo}
            onChange={setRangeTo}
            hasError={rangeToInvalid || showRangeOrderError}
            errorText={
              rangeToInvalid
                ? t('history.invalidDate')
                : showRangeOrderError
                  ? t('history.invalidRange')
                  : undefined
            }
            onBlur={() => setRangeToTouched(true)}
            onEdit={() => {
              setRangeToTouched(true)
              if (rangeFromTouched) {
                setRangeFromTouched(true)
              }
            }}
          />
        </div>
      )}

      <div className="home-summary-section">
        {!rangeFetchEnabled ? null : summaryFetch.state.status === 'error' ? (
          <BlockError onRetry={summaryFetch.retry} />
        ) : null}

        {rangeFetchEnabled && showSummaryCard ? (
          <div className="history-summary">
            {CURRENCIES.map((currency) => {
              const { income, expense } = summaryData
                ? getSummaryForCurrency(summaryData, currency)
                : { income: 0, expense: 0 }

              return (
                <div key={currency} className="history-summary__currency-group">
                  <Text weight="2" className="history-summary__currency-label">
                    {currency}
                  </Text>
                  <div className="home-summary__row">
                    <div className="home-metric-card">
                      <Text className="home-metric-card__label">{t('home.income')}</Text>
                      <MetricValue
                        loading={summaryLoading}
                        unavailable={summaryUnavailable}
                        className="home-metric-card__value home-metric-card__value--income"
                      >
                        {formatCurrency(income, currency)}
                      </MetricValue>
                    </div>
                    <div className="home-metric-card">
                      <Text className="home-metric-card__label">{t('home.expense')}</Text>
                      <MetricValue
                        loading={summaryLoading}
                        unavailable={summaryUnavailable}
                        className="home-metric-card__value home-metric-card__value--expense"
                      >
                        {formatCurrency(expense, currency)}
                      </MetricValue>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : rangeFetchEnabled ? (
          <div className="home-block-loading" role="status" aria-live="polite">
            <Spinner size="m" aria-hidden="true" />
            <span className="visually-hidden">{t('home.loading')}</span>
          </div>
        ) : null}
      </div>

      <div className="home-recent history-page__list">
        {historyStatus === 'loading' ? (
          <div className="home-block-loading" role="status" aria-live="polite">
            <Spinner size="m" aria-hidden="true" />
            <span className="visually-hidden">{t('home.loading')}</span>
          </div>
        ) : null}

        {historyStatus === 'error' ? (
          <BlockError onRetry={() => setHistoryRetryCount((count) => count + 1)} />
        ) : null}

        {historyStatus === 'success' && historyItems.length === 0 ? (
          <div className="home-empty-state">
            <Text>{t('home.noTransactions')}</Text>
          </div>
        ) : null}

        {historyStatus === 'success' && historyItems.length > 0 ? (
          <>
            <div className="home-recent__list">
              {historyItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="home-recent-item home-recent-item--clickable"
                  onClick={() => setSelectedListItem(item)}
                >
                  <div className="home-recent-item__main">
                    <Text className={historyItemTitleClass(item)} weight="2">
                      {getHistoryItemTitle(item, transferLabels, t)}
                    </Text>
                    <Text className="home-recent-item__subtitle">
                      {getHistoryItemSubtitle(item, t('home.income'), t)}
                    </Text>
                    {item.created_by ? (
                      <Text className="home-recent-item__meta">{item.created_by}</Text>
                    ) : null}
                    {item.comment ? (
                      <Text className="home-recent-item__comment">{item.comment}</Text>
                    ) : null}
                  </div>
                  <div className="home-recent-item__aside">
                    <Text className={historyItemAmountClass(item)} weight="2">
                      {formatSignedTransactionAmount(item)}
                    </Text>
                    <Text className="home-recent-item__date">
                      {formatTransactionDateTime(item.transaction_date)}
                    </Text>
                  </div>
                </button>
              ))}
            </div>

            {historyItems.length < historyTotal ? (
              <div className="history-page__load-more">
                {loadMoreError ? (
                  <BlockError onRetry={() => void handleLoadMore()} />
                ) : null}
                <Button
                  mode="bezeled"
                  size="m"
                  stretched
                  loading={loadingMore}
                  onClick={() => void handleLoadMore()}
                >
                  {t('history.loadMore')}
                </Button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      <TransactionDetailModal
        listItem={selectedListItem}
        onClose={() => setSelectedListItem(null)}
        onDeleted={() => {
          setHistoryRetryCount((count) => count + 1)
          setSelectedListItem(null)
        }}
      />
    </div>
  )
}
