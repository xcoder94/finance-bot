import {
  type ClipboardEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { Button, Input, SegmentedControl, Text, Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { monthDateRange } from '../api/home'
import { fetchHistoryPage, fetchSummaryForRange, type SummaryResponse } from '../api/history'
import { HistoryTransactionList } from '../components/history/HistoryTransactionList'
import { formatMonthLabel } from '../utils/periodFilter'
import { editRouteForItem } from '../utils/editRouteForItem'
import { formatCurrency, type Currency } from '../utils/formatCurrency'
import {
  extractDigits,
  formatDateDigits,
  isoDateToMaskedDate,
  isValidMaskedDate,
  maskedDateToUtcEndIso,
  maskedDateToUtcStartIso,
} from '../utils/transactionForm'
import {
  createWalletOpsController,
  type WalletOpsController,
  type WalletOpsState,
} from '../utils/walletOps'
import { createBlockFetcher, type BlockFetcher, type BlockState } from '../utils/blockFetch'
import { subscribeWalletsRefresh } from '../utils/walletsOverview'

const CURRENCIES = ['UZS'] as const

const LOADING_LIST: WalletOpsState = {
  status: 'loading',
  items: [],
  total: 0,
  loadingMore: false,
  loadMoreError: false,
}

type PeriodTab = 'month' | 'range'

type SelectedMonth = {
  year: number
  month: number
}

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

/** Fetched block bound to a key: reloads on key change, `refresh` is silent (old data stays visible). */
function useFetchBlock<T>(fetcher: () => Promise<T>, trigger: unknown, enabled: boolean) {
  const [state, setState] = useState<BlockState<T>>({ status: 'loading' })
  const block = useRef<BlockFetcher | null>(null)

  useEffect(() => {
    if (!enabled) {
      return
    }
    const next = createBlockFetcher({ fetcher, onChange: setState })
    block.current = next
    void next.load()
    return () => {
      next.dispose()
      block.current = null
    }
  }, [fetcher, trigger, enabled])

  const retry = useCallback(() => void block.current?.retry(), [])
  const refresh = useCallback(() => void block.current?.refresh(), [])

  return { state, retry, refresh }
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
    return <span className="motion-skel-line" role="status" aria-busy="true" />
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
  const navigate = useNavigate()
  const [periodTab, setPeriodTab] = useState<PeriodTab>('month')
  const [selectedMonth, setSelectedMonth] = useState<SelectedMonth>(currentMonth)
  const [rangeFrom, setRangeFrom] = useState('')
  const [rangeTo, setRangeTo] = useState('')
  const [rangeInitialized, setRangeInitialized] = useState(false)
  const [rangeFromTouched, setRangeFromTouched] = useState(false)
  const [rangeToTouched, setRangeToTouched] = useState(false)

  const [list, setList] = useState<WalletOpsState>(LOADING_LIST)
  const controller = useRef<WalletOpsController | null>(null)

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

  // The list lives in a controller: pages are merged by id (a record added between two pages does
  // not make a duplicate) and a refresh on return replaces the data without clearing the list.
  useEffect(() => {
    const next = createWalletOpsController({
      fetchPage: (period, limit, offset) =>
        fetchHistoryPage(period.dateFrom, period.dateTo, limit, offset),
      onChange: setList,
    })
    controller.current = next
    return () => {
      next.dispose()
      controller.current = null
    }
  }, [])

  const periodFrom = range?.dateFrom
  const periodTo = range?.dateTo
  useEffect(() => {
    if (periodFrom === undefined || periodTo === undefined) {
      setList(LOADING_LIST)
      return
    }
    void controller.current?.setPeriod({ dateFrom: periodFrom, dateTo: periodTo })
  }, [periodFrom, periodTo])

  // Return from the bot: the browser event or the Telegram bridge signal, selected period kept.
  // The summary above the list is refreshed by the same signal, silently.
  const refreshSummary = summaryFetch.refresh
  useEffect(
    () =>
      subscribeWalletsRefresh(document, () => {
        void controller.current?.refresh()
        refreshSummary()
      }),
    [refreshSummary],
  )

  const historyStatus = range ? list.status : 'idle'

  const summaryLoading = summaryFetch.state.status === 'loading'
  const summaryUnavailable = summaryFetch.state.status === 'error'
  const summaryData =
    summaryFetch.state.status === 'success' ? summaryFetch.state.data : null

  const showSummaryCard =
    summaryFetch.state.status === 'success' || summaryFetch.state.status === 'error'

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
            <span className="motion-skel-line motion-skel-line--block" aria-hidden="true" />
            <span className="visually-hidden">{t('home.loading')}</span>
          </div>
        ) : null}
      </div>

      <div className="history-page__list">
        <HistoryTransactionList
          status={historyStatus}
          items={list.items}
          totalCount={list.total}
          onItemClick={(item) => navigate(editRouteForItem(item))}
          onRetry={() => void controller.current?.retry()}
          loadingMore={list.loadingMore}
          loadMoreError={list.loadMoreError}
          onLoadMore={() => void controller.current?.loadMore()}
        />
      </div>
    </div>
  )
}
