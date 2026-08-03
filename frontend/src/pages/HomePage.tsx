import { useCallback, useEffect, useState } from 'react'
import { Button, Text } from '@telegram-apps/telegram-ui'
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
import {
  getHistoryItemMeta,
  getHistoryItemTitle,
} from '../utils/getDisplayName'
import {
  balanceMonthLabel,
  currentMonthInTashkent,
  emptyMonthTitle,
  formatMonthTitle,
  monthShortLabel,
  shiftHomeMonth,
  type HomeMonth,
} from '../utils/homeMonth'

const CURRENCIES = ['UZS', 'USD'] as const

const ACTION_ICONS = {
  income: 'M11 5v12m0-12l-4 4m4-4l4 4',
  expense: 'M11 17V5m0 12l-4-4m4 4l4-4',
  transfer: 'M4 8h13l-3-3m3 9H4l3 3',
} as const

type FetchState<T> =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; data: T }

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

function isTransferLike(item: HistoryItem): boolean {
  return item.type === 'transfer'
}

function formatHomeTransactionAmount(item: HistoryItem): string {
  const formatted = formatCurrency(item.amount, item.currency as Currency)
  if (isTransferLike(item)) {
    return `↔\u2009${formatted}`
  }
  if (item.type === 'income') {
    return `+${formatted}`
  }
  if (item.type === 'expense') {
    return `−${formatted}`
  }
  return formatted
}

function homeAmountClass(type: string, item: HistoryItem): string {
  if (isTransferLike(item)) {
    return 'home-ops-row__amount home-ops-row__amount--neutral'
  }
  if (type === 'expense') {
    return 'home-ops-row__amount home-ops-row__amount--expense'
  }
  if (type === 'income') {
    return 'home-ops-row__amount home-ops-row__amount--income'
  }
  return 'home-ops-row__amount'
}

function formatTransactionDateShort(isoDate: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Asia/Tashkent',
    day: '2-digit',
    month: '2-digit',
  }).format(new Date(isoDate))
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

function HomeSkeleton() {
  return (
    <div className="home-skeleton" aria-hidden="true">
      <div className="home-skeleton__figures">
        <div className="home-skeleton__line home-skeleton__line--label" />
        <div className="home-skeleton__line home-skeleton__line--hero" />
        <div className="home-skeleton__divider" />
        <div className="home-skeleton__stats">
          <div className="home-skeleton__line home-skeleton__line--stat" />
          <div className="home-skeleton__line home-skeleton__line--stat" />
        </div>
      </div>
      <div className="home-skeleton__actions">
        <div className="home-skeleton__action" />
        <div className="home-skeleton__action" />
        <div className="home-skeleton__action" />
      </div>
      <div className="home-skeleton__ops">
        <div className="home-skeleton__ops-row">
          <div className="home-skeleton__line home-skeleton__line--ops-left" />
          <div className="home-skeleton__line home-skeleton__line--ops-right" />
        </div>
        <div className="home-skeleton__ops-row">
          <div className="home-skeleton__line home-skeleton__line--ops-left" />
          <div className="home-skeleton__line home-skeleton__line--ops-right" />
        </div>
        <div className="home-skeleton__ops-row">
          <div className="home-skeleton__line home-skeleton__line--ops-left" />
          <div className="home-skeleton__line home-skeleton__line--ops-right" />
        </div>
      </div>
      <span className="visually-hidden">Loading</span>
    </div>
  )
}

function ActionIcon({ path }: { path: string }) {
  return (
    <svg
      className="home-actions__icon"
      width="15"
      height="15"
      viewBox="0 0 22 22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  )
}

export function HomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const familyId = user?.familyBudgetId ?? ''
  const [selectedMonth, setSelectedMonth] = useState<HomeMonth>(currentMonthInTashkent)
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
      () =>
        getCachedRecentHistory(familyId, year, month, () => fetchRecentHistory(year, month)),
      [familyId, year, month],
    ),
    monthKey,
    peekRecentHistory(familyId, year, month),
  )

  const summaryData =
    summaryFetch.state.status === 'success' ? summaryFetch.state.data : null
  const balancesData =
    balancesFetch.state.status === 'success' ? balancesFetch.state.data : null
  const historyData =
    historyFetch.state.status === 'success' ? historyFetch.state.data : null

  const { income, expense } = summaryData
    ? getSummaryForCurrency(summaryData, primaryCurrency)
    : { income: 0, expense: 0 }
  const balance = balancesData ? getBalanceForCurrency(balancesData, primaryCurrency) : 0
  const totalCount = historyData?.total_count ?? 0
  const historyItems = historyData?.items ?? []

  const summaryLoading = summaryFetch.state.status === 'loading'
  const summaryUnavailable = summaryFetch.state.status === 'error'
  const balancesLoading = balancesFetch.state.status === 'loading'
  const balancesUnavailable = balancesFetch.state.status === 'error'
  const historyLoading = historyFetch.state.status === 'loading'

  const hasCachedContent =
    peekHomeSummary(familyId, year, month) !== null ||
    peekWalletBalances(familyId) !== null ||
    peekRecentHistory(familyId, year, month) !== null

  const showSkeleton =
    !hasCachedContent &&
    (summaryLoading || balancesLoading || historyLoading) &&
    summaryFetch.state.status !== 'error' &&
    balancesFetch.state.status !== 'error' &&
    historyFetch.state.status !== 'error'

  const participantLabel = t('home.participant', { count: user?.memberCount ?? 0 })
  const roleLine =
    user?.role === 'owner'
      ? t('home.roleLineOwner', { count: participantLabel })
      : t('home.roleLineMember', { count: participantLabel })

  const opsCountLabel =
    totalCount === 0
      ? t('home.opsNone')
      : t('home.opsCount', { count: totalCount, monthShort: monthShortLabel(month) })

  const transferLabels = {
    transfer: t('history.transfer'),
    exchange: t('history.exchange'),
  }

  const quickActions = [
    { key: 'income', label: t('home.income'), path: '/add-income', icon: ACTION_ICONS.income },
    { key: 'expense', label: t('home.expense'), path: '/add-expense', icon: ACTION_ICONS.expense },
    {
      key: 'transfer',
      label: t('home.transfer'),
      path: '/add-transfer',
      icon: ACTION_ICONS.transfer,
    },
  ] as const

  return (
    <div className="page-content home-page">
      <div className="home-header">
        <div className="home-header__info">
          <h1 className="home-header__title">{user?.budgetName ?? ''}</h1>
          <p className="home-header__role">{roleLine}</p>
        </div>
        <div className="home-currency-chip" role="group" aria-label={t('home.summary')}>
          {CURRENCIES.map((currency) => (
            <button
              key={currency}
              type="button"
              className={
                primaryCurrency === currency
                  ? 'home-currency-chip__btn home-currency-chip__btn--active'
                  : 'home-currency-chip__btn'
              }
              onClick={() => setPrimaryCurrency(currency)}
            >
              {currency}
            </button>
          ))}
        </div>
      </div>

      <div className="home-month-bar">
        <button
          type="button"
          className="home-month-bar__nav"
          aria-label={t('home.previousMonth')}
          onClick={() => setSelectedMonth((current) => shiftHomeMonth(current, -1))}
        >
          ‹
        </button>
        <div className="home-month-bar__label">{formatMonthTitle(year, month)}</div>
        <button
          type="button"
          className="home-month-bar__nav"
          aria-label={t('home.nextMonth')}
          onClick={() => setSelectedMonth((current) => shiftHomeMonth(current, 1))}
        >
          ›
        </button>
      </div>

      {showSkeleton ? <HomeSkeleton /> : null}

      {!showSkeleton ? (
        <>
          {summaryFetch.state.status === 'error' ? (
            <BlockError onRetry={summaryFetch.retry} />
          ) : null}
          {balancesFetch.state.status === 'error' ? (
            <BlockError onRetry={balancesFetch.retry} />
          ) : null}
          {historyFetch.state.status === 'error' ? (
            <BlockError onRetry={historyFetch.retry} />
          ) : null}

          <div className="home-figures-card">
            <div className="home-figures-card__label">{balanceMonthLabel(month)}</div>
            <div className="home-figures-card__balance">
              {balancesUnavailable || balancesLoading
                ? '—'
                : formatCurrency(balance, primaryCurrency)}
            </div>
            <div className="home-figures-card__stats">
              <div className="home-figures-card__stat">
                <div className="home-figures-card__stat-label">{t('home.income')}</div>
                <div className="home-figures-card__stat-value home-figures-card__stat-value--income">
                  {summaryUnavailable || summaryLoading
                    ? '—'
                    : formatCurrency(income, primaryCurrency)}
                </div>
              </div>
              <div className="home-figures-card__stat-divider" aria-hidden="true" />
              <div className="home-figures-card__stat">
                <div className="home-figures-card__stat-label">{t('home.expense')}</div>
                <div className="home-figures-card__stat-value home-figures-card__stat-value--expense">
                  {summaryUnavailable || summaryLoading
                    ? '—'
                    : formatCurrency(expense, primaryCurrency)}
                </div>
              </div>
            </div>
          </div>

          <div className="home-actions">
            {quickActions.map((action) => (
              <button
                key={action.key}
                type="button"
                className="home-actions__btn"
                onClick={() => navigate(action.path)}
              >
                <ActionIcon path={action.icon} />
                {action.label}
              </button>
            ))}
          </div>

          <div className="home-recent-header">
            <button
              type="button"
              className="home-recent-header__link"
              onClick={() => navigate('/history')}
            >
              {t('home.recentTransactions')}
              <span className="home-recent-header__chevron"> ›</span>
            </button>
            <div className="home-recent-header__count">{opsCountLabel}</div>
          </div>

          {totalCount === 0 ? (
            <div className="home-empty-card">
              <div className="home-empty-card__icon" aria-hidden="true" />
              <div className="home-empty-card__title">{emptyMonthTitle(month)}</div>
              <div className="home-empty-card__hint">{t('home.emptyMonthHint')}</div>
            </div>
          ) : (
            <div className="home-ops-card">
              {historyItems.map((item) => (
                <div key={item.id} className="home-ops-row">
                  <div className="home-ops-row__main">
                    <div className="home-ops-row__title">
                      {getHistoryItemTitle(item, transferLabels, t)}
                    </div>
                    <div className="home-ops-row__meta">{getHistoryItemMeta(item, t)}</div>
                  </div>
                  <div className="home-ops-row__aside">
                    <div className={homeAmountClass(item.type, item)}>
                      {formatHomeTransactionAmount(item)}
                    </div>
                    <div className="home-ops-row__date">
                      {formatTransactionDateShort(item.transaction_date)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
