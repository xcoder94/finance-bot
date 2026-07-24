import { useCallback, useEffect, useState } from 'react'
import { Button, SegmentedControl, Spinner, Text, Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import {
  fetchRecentHistory,
  fetchSummary,
  fetchWalletBalances,
  type HistoryItem,
  type SummaryResponse,
  type WalletBalancesResponse,
} from '../api/home'
import i18n from '../i18n'
import { useAuthStore } from '../store/authStore'
import {
  getCachedHomeSummary,
  getCachedRecentHistory,
  getCachedWalletBalances,
  peekHomeSummary,
  peekRecentHistory,
  peekWalletBalances,
} from '../store/dataCacheStore'
import { formatCurrency, type Currency } from '../utils/formatCurrency'
import { getHistoryItemTitle } from '../utils/getDisplayName'

const CURRENCIES = ['UZS', 'USD'] as const

type SelectedMonth = {
  year: number
  month: number
}

type FetchState<T> =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; data: T }

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

function getBalanceForCurrency(balances: WalletBalancesResponse, currency: Currency): number {
  return balances.balances.find((row) => row.currency === currency)?.balance ?? 0
}

function getTransactionTypeLabel(
  item: HistoryItem,
  labels: { income: string; expense: string; transfer: string; exchange: string },
): string {
  if (item.type === 'income') {
    return labels.income
  }
  if (item.type === 'expense') {
    return labels.expense
  }
  if (item.currency !== item.to_currency) {
    return labels.exchange
  }
  return labels.transfer
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

function transactionTitleClass(type: string): string {
  if (type === 'expense') {
    return 'home-recent-item__title home-recent-item__title--expense'
  }
  if (type === 'income') {
    return 'home-recent-item__title home-recent-item__title--income'
  }
  return 'home-recent-item__title'
}

function transactionAmountClass(type: string): string {
  if (type === 'expense') {
    return 'home-recent-item__amount home-recent-item__amount--expense'
  }
  if (type === 'income') {
    return 'home-recent-item__amount home-recent-item__amount--income'
  }
  return 'home-recent-item__amount'
}

function useFetchBlock<T>(fetcher: () => Promise<T>, trigger: unknown, initialData: T | null = null) {
  const [state, setState] = useState<FetchState<T>>(
    initialData ? { status: 'success', data: initialData } : { status: 'loading' },
  )
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState(initialData ? { status: 'success', data: initialData } : { status: 'loading' })

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
  }, [fetcher, trigger, retryCount, initialData])

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

export function HomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')
  const [selectedMonth, setSelectedMonth] = useState<SelectedMonth>(currentMonth)
  const [primaryCurrency, setPrimaryCurrency] = useState<Currency>('UZS')

  const { year, month } = selectedMonth
  const monthKey = `${year}-${month}`

  const summaryFetch = useFetchBlock(
    useCallback(
      () => getCachedHomeSummary(familyId, year, month, () => fetchSummary(year, month)),
      [familyId, year, month],
    ),
    monthKey,
    peekHomeSummary(familyId, year, month),
  )
  const balancesFetch = useFetchBlock(
    useCallback(
      () => getCachedWalletBalances(familyId, fetchWalletBalances),
      [familyId],
    ),
    'mount',
    peekWalletBalances(familyId),
  )
  const historyFetch = useFetchBlock(
    useCallback(
      () => getCachedRecentHistory(familyId, fetchRecentHistory),
      [familyId],
    ),
    'mount',
    peekRecentHistory(familyId),
  )

  const summaryData =
    summaryFetch.state.status === 'success' ? summaryFetch.state.data : null
  const balancesData =
    balancesFetch.state.status === 'success' ? balancesFetch.state.data : null

  const { income, expense } = summaryData
    ? getSummaryForCurrency(summaryData, primaryCurrency)
    : { income: 0, expense: 0 }
  const balance = balancesData ? getBalanceForCurrency(balancesData, primaryCurrency) : 0

  const summaryLoading = summaryFetch.state.status === 'loading'
  const summaryUnavailable = summaryFetch.state.status === 'error'
  const balancesLoading = balancesFetch.state.status === 'loading'
  const balancesUnavailable = balancesFetch.state.status === 'error'
  const showSummaryCard =
    summaryFetch.state.status === 'success' ||
    balancesFetch.state.status === 'success' ||
    summaryFetch.state.status === 'error' ||
    balancesFetch.state.status === 'error'

  const typeLabels = {
    income: t('home.income'),
    expense: t('home.expense'),
    transfer: t('history.transfer'),
    exchange: t('history.exchange'),
  }

  const transferLabels = {
    transfer: t('history.transfer'),
    exchange: t('history.exchange'),
  }

  return (
    <div className="page-content home-page">
      <Title level="1" weight="2" className="home-page__title">
        {t('home.title')}
      </Title>

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

      <div className="segmented-control-wrap home-page__currency-toggle">
        <SegmentedControl>
          {CURRENCIES.map((currency) => (
            <SegmentedControl.Item
              key={currency}
              selected={primaryCurrency === currency}
              onClick={() => setPrimaryCurrency(currency)}
            >
              {currency}
            </SegmentedControl.Item>
          ))}
        </SegmentedControl>
      </div>

      <div className="home-summary-section">
        {summaryFetch.state.status === 'error' ? (
          <BlockError onRetry={summaryFetch.retry} />
        ) : null}

        {balancesFetch.state.status === 'error' ? (
          <BlockError onRetry={balancesFetch.retry} />
        ) : null}

        {showSummaryCard ? (
          <div className="home-summary">
            <div className="home-summary__row">
              <div className="home-metric-card">
                <Text className="home-metric-card__label">{t('home.income')}</Text>
                <MetricValue
                  loading={summaryLoading}
                  unavailable={summaryUnavailable}
                  className="home-metric-card__value home-metric-card__value--income"
                >
                  {formatCurrency(income, primaryCurrency)}
                </MetricValue>
              </div>
              <div className="home-metric-card">
                <Text className="home-metric-card__label">{t('home.expense')}</Text>
                <MetricValue
                  loading={summaryLoading}
                  unavailable={summaryUnavailable}
                  className="home-metric-card__value home-metric-card__value--expense"
                >
                  {formatCurrency(expense, primaryCurrency)}
                </MetricValue>
              </div>
            </div>
            <div className="home-metric-card home-metric-card--wide">
              <Text className="home-metric-card__label">{t('home.balance')}</Text>
              <MetricValue
                loading={balancesLoading}
                unavailable={balancesUnavailable}
                className="home-metric-card__value home-metric-card__value--balance"
              >
                {formatCurrency(balance, primaryCurrency)}
              </MetricValue>
            </div>
          </div>
        ) : (
          <div className="home-block-loading" role="status" aria-live="polite">
            <Spinner size="m" aria-hidden="true" />
            <span className="visually-hidden">{t('home.loading')}</span>
          </div>
        )}
      </div>

      <div className="home-quick-actions">
        <button
          type="button"
          className="home-quick-action"
          onClick={() => navigate('/add-income')}
        >
          <span className="home-quick-action__icon home-quick-action__icon--income">+</span>
          <span className="home-quick-action__label">{t('home.income')}</span>
        </button>
        <button
          type="button"
          className="home-quick-action"
          onClick={() => navigate('/add-expense')}
        >
          <span className="home-quick-action__icon home-quick-action__icon--expense">−</span>
          <span className="home-quick-action__label">{t('home.expense')}</span>
        </button>
        <button
          type="button"
          className="home-quick-action"
          onClick={() => navigate('/add-transfer')}
        >
          <span className="home-quick-action__icon home-quick-action__icon--transfer">⇄</span>
          <span className="home-quick-action__label">{t('home.transfer')}</span>
        </button>
      </div>

      <div className="home-recent">
        <Text weight="2" className="home-recent__title">
          {t('home.recentTransactions')}
        </Text>

        {historyFetch.state.status === 'loading' ? (
          <div className="home-block-loading" role="status" aria-live="polite">
            <Spinner size="m" aria-hidden="true" />
            <span className="visually-hidden">{t('home.loading')}</span>
          </div>
        ) : null}

        {historyFetch.state.status === 'error' ? (
          <BlockError onRetry={historyFetch.retry} />
        ) : null}

        {historyFetch.state.status === 'success' && historyFetch.state.data.items.length === 0 ? (
          <div className="home-empty-state">
            <Text>{t('home.noTransactions')}</Text>
          </div>
        ) : null}

        {historyFetch.state.status === 'success' && historyFetch.state.data.items.length > 0 ? (
          <div className="home-recent__list">
            {historyFetch.state.data.items.map((item) => (
              <div key={item.id} className="home-recent-item">
                <div className="home-recent-item__main">
                  <Text className={transactionTitleClass(item.type)} weight="2">
                    {getHistoryItemTitle(item, transferLabels, t)}
                  </Text>
                  <Text className="home-recent-item__subtitle">
                    {getTransactionTypeLabel(item, typeLabels)}
                  </Text>
                </div>
                <div className="home-recent-item__aside">
                  <Text className={transactionAmountClass(item.type)} weight="2">
                    {formatSignedTransactionAmount(item)}
                  </Text>
                  <Text className="home-recent-item__date">
                    {formatTransactionDateTime(item.transaction_date)}
                  </Text>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}
