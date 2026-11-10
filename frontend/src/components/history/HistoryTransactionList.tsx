import { Button } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import type { HistoryItem } from '../../api/history'
import { BlockError } from '../BlockError'
import {
  formatHistoryTransactionAmount,
  formatTransactionDateShort,
  historyAmountClass,
} from './historyTransactionDisplay'
import { HistoryListSkeleton } from './HistoryListSkeleton'
import {
  getHistoryItemMeta,
  getHistoryItemTitle,
} from '../../utils/getDisplayName'
import { EmptyStateIcon } from '../EmptyStateIcon'
import { formatChipDate, todayTashkent } from '../../utils/dateChips'
import { formatCurrency, type Currency } from '../../utils/formatCurrency'
import { dayHeaderKind, groupHistoryByDay } from '../../utils/groupHistoryByDay'
import { getLocale } from '../../utils/periodFilter'

type HistoryTransactionListProps = {
  status: 'idle' | 'loading' | 'error' | 'success'
  items: HistoryItem[]
  totalCount: number
  onItemClick: (item: HistoryItem) => void
  onRetry: () => void
  loadingMore?: boolean
  loadMoreError?: boolean
  onLoadMore?: () => void
  /** Replaces the default amount text (used by the wallet screen). */
  formatAmount?: (item: HistoryItem) => string
  /** Replaces the default empty-list hint. */
  emptyHint?: string
  /** Day headers («Сегодня», «Вчера», «8 ноября») with the day's expense total. */
  groupByDay?: boolean
}

export function HistoryTransactionList({
  status,
  items,
  totalCount,
  onItemClick,
  onRetry,
  loadingMore = false,
  loadMoreError = false,
  onLoadMore,
  formatAmount = formatHistoryTransactionAmount,
  emptyHint,
  groupByDay = false,
}: HistoryTransactionListProps) {
  const { t } = useTranslation()

  const transferLabels = {
    transfer: t('history.transfer'),
    exchange: t('history.exchange'),
  }

  const today = todayTashkent()

  const renderRow = (item: HistoryItem) => (
    <button
      key={item.id}
      type="button"
      className="home-ops-row home-ops-row--clickable"
      onClick={() => onItemClick(item)}
    >
      <div className="home-ops-row__main">
        <div className="home-ops-row__title">
          {getHistoryItemTitle(item, transferLabels, t)}
        </div>
        <div className="home-ops-row__meta">{getHistoryItemMeta(item, t)}</div>
      </div>
      <div className="home-ops-row__aside">
        <div className={historyAmountClass(item)}>
          {formatAmount(item)}
        </div>
        <div className="home-ops-row__date">
          {formatTransactionDateShort(item.transaction_date)}
        </div>
      </div>
    </button>
  )

  return (
    <>
      {status === 'loading' ? <HistoryListSkeleton /> : null}

      {status === 'error' ? <BlockError onRetry={onRetry} /> : null}

      {status === 'success' && items.length === 0 ? (
        <div className="home-empty-card">
          <EmptyStateIcon className="home-empty-card__icon" />
          <div className="home-empty-card__title">{t('history.emptyTitle')}</div>
          <div className="home-empty-card__hint">{emptyHint ?? t('history.emptyHint')}</div>
        </div>
      ) : null}

      {status === 'success' && items.length > 0 ? (
        <>
          <div className="home-ops-card">
            {groupByDay
              ? groupHistoryByDay(items).map((group) => {
                  const kind = dayHeaderKind(group.day, today)
                  const title =
                    kind === 'other'
                      ? formatChipDate(group.day, today, getLocale())
                      : t(kind === 'today' ? 'dateChips.today' : 'dateChips.yesterday')
                  const total = group.expenseTotals
                    .map((row) => `−${formatCurrency(row.amount, row.currency as Currency)}`)
                    .join(' · ')
                  return (
                    <div key={group.day} className="history-day-group" data-day={group.day}>
                      <div className="history-day">
                        <span className="history-day__title">{title}</span>
                        {total ? <span className="history-day__total">{total}</span> : null}
                      </div>
                      {group.items.map(renderRow)}
                    </div>
                  )
                })
              : items.map(renderRow)}
          </div>

          {onLoadMore && items.length < totalCount ? (
            <div className="history-page__load-more">
              {loadMoreError ? <BlockError onRetry={() => void onLoadMore()} /> : null}
              <Button
                mode="bezeled"
                size="m"
                stretched
                loading={loadingMore}
                onClick={() => void onLoadMore()}
              >
                {t('history.loadMore')}
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  )
}
