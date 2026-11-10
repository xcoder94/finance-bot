import { MonthArrow } from '../components/MonthArrow'
import { openHistoryFromHome } from '../utils/historyEntry'
import { useCallback, useEffect, useLayoutEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { UserAvatar } from '../components/UserAvatar'
import {
  HomeFailBox,
  HomeLeftBlock,
  HomeLeftSkeleton,
  balanceSizeClass,
  HomeOnboardingCard,
} from '../components/home/homeBlocks'
import { fetchWallets } from '../api/transactions'
import { sharedUzsWalletsTotal } from '../utils/homeWallets'
import { fetchOnboarding, type OnboardingState } from '../api/me'

import {
  fetchRecentHistory,
  fetchSummary,
  fetchPersonalSummary,
  fetchPersonalWalletBalances,
  type HistoryItem,
} from '../api/home'
import { useAuthStore } from '../store/authStore'
import {
  getCachedHomeSummary,
  getCachedRecentHistory,
  getCachedWallets,
  useDataCacheStore,
  getCachedPersonalSummary,
  getCachedPersonalWalletBalances,
  invalidateHomeData,
  peekHomeSummary,
  peekRecentHistory,
  peekWallets,
  peekPersonalSummary,
  peekPersonalWalletBalances,
} from '../store/dataCacheStore'
import { resolveFetchState, type FetchState, type KeyedFetchState } from '../utils/homeFetchState'
import { daysLeftInMonth, monthHasIncome, perDayAllowance, remainingFromSummary } from '../utils/homeLeft'
import {
  loadDismissedAt,
  readDismissedAtSync,
  saveDismissedAt,
  shouldShowOnboardingCard,
} from '../utils/onboardingDismiss'
import { editRouteForItem } from '../utils/editRouteForItem'
import { CountUp } from '../components/CountUp'
import { formatCurrency, type Currency } from '../utils/formatCurrency'
import {
  getHomeBudgetHeading,
  getSummaryForCurrency,
} from '../utils/homeFigures'
import {
  getPersonalBalanceForCurrency,
  getPersonalSummaryForCurrency,
  shouldShowPersonalBlock,
} from '../utils/homePersonal'
import {
  composeBalancesFetchTrigger,
  composeHomeFetchTrigger,
  shouldRefreshHomeOnVisibility,
} from '../utils/homeVisibility'
import {
  getHistoryItemMeta,
  getHistoryItemTitle,
} from '../utils/getDisplayName'
import { forgetHomeMonth, openWalletsFromHome, peekHomeMonth } from '../utils/homeMonthMemory'
import {
  balanceMonthLabel,
  currentMonthInTashkent,
  emptyMonthTitle,
  formatMonthTitle,
  monthShortLabel,
  shiftHomeMonth,
  type HomeMonth,
} from '../utils/homeMonth'
import { EmptyStateIcon } from '../components/EmptyStateIcon'
import { BlockError } from '../components/BlockError'

const PRIMARY_CURRENCY: Currency = 'UZS'

const ACTION_ICONS = {
  income: 'M11 5v12m0-12l-4 4m4-4l4 4',
  expense: 'M11 17V5m0 12l-4-4m4 4l4-4',
  transfer: 'M4 8h13l-3-3m3 9H4l3 3',
} as const

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

function useFetchBlock<T>(
  fetcher: () => Promise<T>,
  trigger: unknown,
  initialData: T | null = null,
  dataKey = 'static',
) {
  const [stored, setStored] = useState<KeyedFetchState<T>>(() => ({
    key: dataKey,
    state: initialData ? { status: 'success', data: initialData } : { status: 'loading' },
  }))
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    setStored({
      key: dataKey,
      state: initialData ? { status: 'success', data: initialData } : { status: 'loading' },
    })

    void fetcher()
      .then((data) => {
        if (!cancelled) {
          setStored({ key: dataKey, state: { status: 'success', data } })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStored({ key: dataKey, state: { status: 'error' } })
        }
      })

    return () => {
      cancelled = true
    }
  }, [fetcher, trigger, retryCount, initialData, dataKey])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  const state: FetchState<T> = resolveFetchState(stored, dataKey, initialData)
  return { state, retry }
}

function HomeSkeleton() {
  return (
    <div className="home-skeleton" aria-hidden="true">
      <HomeLeftSkeleton />
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

/** Add/Edit forms are separate routes, so Home unmounts; put the scroll back when it returns. */
let savedHomeScrollY = 0

function useHomeScrollRestore() {
  useLayoutEffect(() => {
    if (savedHomeScrollY > 0) window.scrollTo(0, savedHomeScrollY)
    const onScroll = () => {
      savedHomeScrollY = window.scrollY
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
}

export function HomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const homeEpoch = useDataCacheStore((state) => state.homeEpoch)
  // Forms open as an overlay on top of this (still mounted) page, see AppShell `background`.
  const openForm = (path: string) => navigate(path, { state: { background: location } })
  const user = useAuthStore((state) => state.user)
  const familyId = user?.familyBudgetId ?? ''
  const [selectedMonth, setSelectedMonth] = useState<HomeMonth>(
    () => peekHomeMonth() ?? currentMonthInTashkent(),
  )
  const primaryCurrency = PRIMARY_CURRENCY
  const [visibilityRefreshCount, setVisibilityRefreshCount] = useState(0)

  const { year, month } = selectedMonth
  const monthKey = `${year}-${month}`
  const homeFetchTrigger = composeHomeFetchTrigger(monthKey, visibilityRefreshCount + homeEpoch)
  const balancesFetchTrigger = composeBalancesFetchTrigger(visibilityRefreshCount + homeEpoch)

  // The month parked for the /wallets round trip has been picked up; later visits start fresh.
  useEffect(() => {
    forgetHomeMonth()
  }, [])

  useEffect(() => {
    const onVisibilityChange = () => {
      if (!familyId || !shouldRefreshHomeOnVisibility(document.visibilityState)) {
        return
      }
      invalidateHomeData(familyId)
      setVisibilityRefreshCount((count) => count + 1)
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [familyId])

  const summaryFetch = useFetchBlock(
    useCallback(
      () => getCachedHomeSummary(familyId, year, month, () => fetchSummary(year, month)),
      [familyId, year, month],
    ),
    homeFetchTrigger,
    peekHomeSummary(familyId, year, month),
    monthKey,
  )
  const personalSummaryFetch = useFetchBlock(
    useCallback(
      () =>
        getCachedPersonalSummary(familyId, year, month, () =>
          fetchPersonalSummary(year, month),
        ),
      [familyId, year, month],
    ),
    homeFetchTrigger,
    peekPersonalSummary(familyId, year, month),
    monthKey,
  )
  const personalBalancesFetch = useFetchBlock(
    useCallback(
      () => getCachedPersonalWalletBalances(familyId, fetchPersonalWalletBalances),
      [familyId],
    ),
    balancesFetchTrigger,
    peekPersonalWalletBalances(familyId),
  )
  const historyFetch = useFetchBlock(
    useCallback(
      () =>
        getCachedRecentHistory(familyId, year, month, () => fetchRecentHistory(year, month)),
      [familyId, year, month],
    ),
    homeFetchTrigger,
    peekRecentHistory(familyId, year, month),
    monthKey,
  )

  // Forced on every trigger: balances change with each operation and the reference cache is long-lived.
  const walletsFetch = useFetchBlock(
    useCallback(
      () => getCachedWallets(familyId, fetchWallets, true),
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [familyId, homeEpoch, visibilityRefreshCount],
    ),
    balancesFetchTrigger,
    peekWallets(familyId),
  )
  useHomeScrollRestore()
  const [dismissedAt, setDismissedAt] = useState<number | null>(readDismissedAtSync)
  useEffect(() => {
    let cancelled = false
    void loadDismissedAt().then((ts) => {
      if (!cancelled && ts !== null) setDismissedAt((cur) => Math.max(cur ?? 0, ts))
    })
    return () => {
      cancelled = true
    }
  }, [])
  const onboardingFetch = useFetchBlock<OnboardingState>(
    fetchOnboarding,
    visibilityRefreshCount + homeEpoch,
  )

  const summaryData =
    summaryFetch.state.status === 'success' ? summaryFetch.state.data : null
  const personalSummaryData =
    personalSummaryFetch.state.status === 'success' ? personalSummaryFetch.state.data : null
  const personalBalancesData =
    personalBalancesFetch.state.status === 'success' ? personalBalancesFetch.state.data : null
  const historyData =
    historyFetch.state.status === 'success' ? historyFetch.state.data : null

  const { income, expense } = summaryData
    ? getSummaryForCurrency(summaryData, primaryCurrency)
    : { income: 0, expense: 0 }
  const remaining = summaryData ? remainingFromSummary(summaryData) : 0
  const daysLeft = daysLeftInMonth(new Date(), selectedMonth)
  const perDay = perDayAllowance(remaining, daysLeft)
  const walletsTotal =
    walletsFetch.state.status === 'success' ? sharedUzsWalletsTotal(walletsFetch.state.data) : null
  const showNoIncomeHint = !!summaryData && expense > 0 && income === 0
  const onboardingState =
    onboardingFetch.state.status === 'success' ? onboardingFetch.state.data : null
  const showOnboarding = shouldShowOnboardingCard(onboardingState, dismissedAt, Date.now())
  const closeOnboarding = () => {
    const ts = Date.now()
    setDismissedAt(ts)
    void saveDismissedAt(ts)
  }
  const anyBlockFailed =
    summaryFetch.state.status === 'error' ||
    historyFetch.state.status === 'error'
  const retryFailed = () => {
    if (summaryFetch.state.status === 'error') summaryFetch.retry()
    if (historyFetch.state.status === 'error') historyFetch.retry()
  }
  const currenciesWithPersonalWallets =
    personalSummaryData?.currencies_with_wallets ??
    personalBalancesData?.currencies_with_wallets ??
    []
  const showPersonalBlock = shouldShowPersonalBlock(
    currenciesWithPersonalWallets,
    primaryCurrency,
  )
  const personalIncome = personalSummaryData
    ? getPersonalSummaryForCurrency(personalSummaryData, primaryCurrency).income
    : 0
  const personalExpense = personalSummaryData
    ? getPersonalSummaryForCurrency(personalSummaryData, primaryCurrency).expense
    : 0
  const personalBalance = personalBalancesData
    ? getPersonalBalanceForCurrency(personalBalancesData, primaryCurrency)
    : 0
  const totalCount = historyData?.total_count ?? 0
  const historyItems = historyData?.items ?? []

  const summaryLoading = summaryFetch.state.status === 'loading'
  const summaryUnavailable = summaryFetch.state.status === 'error'
  // Owner decision 13: month income - expense, same figure as the «Осталось» plate.
  const balanceText =
    summaryUnavailable || summaryLoading ? '—' : formatCurrency(remaining, primaryCurrency)
  const personalSummaryLoading = personalSummaryFetch.state.status === 'loading'
  const personalSummaryUnavailable = personalSummaryFetch.state.status === 'error'
  const personalBalancesLoading = personalBalancesFetch.state.status === 'loading'
  const personalBalancesUnavailable = personalBalancesFetch.state.status === 'error'
  const historyLoading = historyFetch.state.status === 'loading'
  const historySuccess = historyFetch.state.status === 'success'

  const hasCachedContent =
    peekHomeSummary(familyId, year, month) !== null ||
    peekPersonalSummary(familyId, year, month) !== null ||
    peekPersonalWalletBalances(familyId) !== null ||
    peekRecentHistory(familyId, year, month) !== null

  const showSkeleton =
    !hasCachedContent &&
    (summaryLoading || historyLoading) &&
    summaryFetch.state.status !== 'error' &&
    historyFetch.state.status !== 'error'

  const participantLabel = t('home.participant', { count: user?.memberCount ?? 0 })
  const personalDisplayName = user?.firstName ?? '—'
  const roleLine =
    user?.role === 'owner'
      ? t('home.roleLineOwner', { count: participantLabel })
      : t('home.roleLineMember', { count: participantLabel })

  const opsCountLabel = historySuccess
    ? totalCount === 0
      ? t('home.opsNone')
      : t('home.opsCount', { count: totalCount, monthShort: monthShortLabel(month) })
    : null

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
        <Link
          to="/settings"
          state={{ from: '/' }}
          className="home-header__avatar"
          aria-label={t('nav.settings')}
        >
          <UserAvatar />
        </Link>
        <div className="home-header__info">
          <h1 className="home-header__title">{getHomeBudgetHeading(user)}</h1>
          <p className="home-header__role">{roleLine}</p>
        </div>
      </div>

      <div className="home-month-bar">
        <MonthArrow direction="prev" label={t('home.previousMonth')} onClick={() => setSelectedMonth((current) => shiftHomeMonth(current, -1))} />
        <div className="home-month-bar__label">{formatMonthTitle(year, month)}</div>
        <MonthArrow direction="next" label={t('home.nextMonth')} onClick={() => setSelectedMonth((current) => shiftHomeMonth(current, 1))} />
      </div>

      {showSkeleton ? <HomeSkeleton /> : null}

      {!showSkeleton ? (
        <>
          {anyBlockFailed ? <HomeFailBox onRetry={retryFailed} /> : null}
          {personalSummaryFetch.state.status === 'error' ? (
            <BlockError onRetry={personalSummaryFetch.retry} />
          ) : null}
          {personalBalancesFetch.state.status === 'error' ? (
            <BlockError onRetry={personalBalancesFetch.retry} />
          ) : null}

          {anyBlockFailed || !showOnboarding || !onboardingState ? null : (
            <HomeOnboardingCard
              steps={onboardingState.steps}
              onStart={() => openForm('/add-expense')}
              onStartIncome={() => openForm('/add-income')}
              onClose={closeOnboarding}
            />
          )}

          {anyBlockFailed ? null : (
          <>
          <div className="home-figures-card">
            <div className="home-figures-card__label">{balanceMonthLabel(month)}</div>
            <div className={`home-figures-card__balance${balanceSizeClass(balanceText)}`}>
              {summaryUnavailable || summaryLoading ? (
                balanceText
              ) : (
                <CountUp
                  id="home-balance"
                  value={remaining}
                  format={(n) => formatCurrency(n, primaryCurrency)}
                />
              )}
            </div>
            {showNoIncomeHint ? (
              <div className="home-figures-card__hint">{t('home.noIncomeHint')}</div>
            ) : null}
            <div className="home-figures-card__stats">
              <div className="home-figures-card__stat">
                <div className="home-figures-card__stat-label">{t('home.income')}</div>
                <div className="home-figures-card__stat-value home-figures-card__stat-value--income">
                  {summaryUnavailable || summaryLoading ? (
                    '—'
                  ) : (
                    <CountUp
                      id="home-income"
                      value={income}
                      format={(n) => formatCurrency(n, primaryCurrency)}
                    />
                  )}
                </div>
              </div>
              <div className="home-figures-card__stat-divider" aria-hidden="true" />
              <div className="home-figures-card__stat">
                <div className="home-figures-card__stat-label">{t('home.expense')}</div>
                <div className="home-figures-card__stat-value home-figures-card__stat-value--expense">
                  {summaryUnavailable || summaryLoading ? (
                    '—'
                  ) : (
                    <CountUp
                      id="home-expense"
                      value={expense}
                      format={(n) => formatCurrency(n, primaryCurrency)}
                    />
                  )}
                </div>
              </div>
            </div>
            {walletsTotal !== null ? (
              <button
                type="button"
                className="home-figures-card__wallets"
                onClick={() => openWalletsFromHome(selectedMonth, (path) => navigate(path))}
              >
                {t('home.walletsLine', { sum: formatCurrency(walletsTotal, primaryCurrency) })}
                <span aria-hidden="true"> ›</span>
              </button>
            ) : null}
          </div>

          {summaryLoading ? (
            <HomeLeftSkeleton />
          ) : (
            <HomeLeftBlock
              perDay={perDay}
              days={daysLeft}
              noIncome={!!summaryData && !monthHasIncome(summaryData)}
            />
          )}

          <div className="home-actions">
            {quickActions.map((action) => (
              <button
                key={action.key}
                type="button"
                className="home-actions__btn"
                onClick={() => openForm(action.path)}
              >
                <ActionIcon path={action.icon} />
                {action.label}
              </button>
            ))}
          </div>

          <div className="home-recent-header">
            <div className="home-recent-header__main">
              <div className="home-recent-header__title">{t('home.recentTransactions')}</div>
              {opsCountLabel ? (
                <div className="home-recent-header__count">{opsCountLabel}</div>
              ) : null}
            </div>
            <button
              type="button"
              className="home-recent-header__link"
              onClick={() => openHistoryFromHome({ year, month }, navigate)}
            >
              {t('home.seeAll')}
              <span className="home-recent-header__chevron"> ›</span>
            </button>
          </div>

          {historySuccess && totalCount === 0 ? (
            <div className="home-empty-card">
              <EmptyStateIcon className="home-empty-card__icon" />
              <div className="home-empty-card__title">{emptyMonthTitle(month)}</div>
              <div className="home-empty-card__hint">{t('home.emptyMonthHint')}</div>
              <button
                type="button"
                className="home-empty-card__cta"
                onClick={() => openForm('/add-expense')}
              >
                {t('home.addExpense')}
              </button>
            </div>
          ) : historySuccess && totalCount > 0 ? (
            <div className="home-ops-card">
              {historyItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="home-ops-row home-ops-row--clickable"
                  onClick={() => openForm(editRouteForItem(item))}
                >
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
                </button>
              ))}
            </div>
          ) : historyLoading ? (
            <div className="home-skeleton__ops" aria-hidden="true">
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
          ) : null}

          {showPersonalBlock ? (
            <div className="home-personal-card">
              <div className="home-personal-card__header">
                <div className="home-personal-card__title">{t('home.personalTitle')}</div>
                <div className="home-personal-card__subtitle">
                  {t('home.personalSubtitle', { name: personalDisplayName })}
                </div>
              </div>
              <div className="home-personal-card__stats">
                <div className="home-personal-card__stat">
                  <div className="home-personal-card__stat-label">{t('home.income')}</div>
                  <div className="home-personal-card__stat-value home-personal-card__stat-value--income">
                    {personalSummaryUnavailable || personalSummaryLoading
                      ? '—'
                      : formatCurrency(personalIncome, primaryCurrency)}
                  </div>
                </div>
                <div className="home-personal-card__stat">
                  <div className="home-personal-card__stat-label">{t('home.expense')}</div>
                  <div className="home-personal-card__stat-value home-personal-card__stat-value--expense">
                    {personalSummaryUnavailable || personalSummaryLoading
                      ? '—'
                      : formatCurrency(personalExpense, primaryCurrency)}
                  </div>
                </div>
                <div className="home-personal-card__stat">
                  <div className="home-personal-card__stat-label">{t('home.balance')}</div>
                  <div className="home-personal-card__stat-value">
                    {personalBalancesUnavailable || personalBalancesLoading
                      ? '—'
                      : formatCurrency(personalBalance, primaryCurrency)}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
          </>
          )}
        </>
      ) : null}
    </div>
  )
}
