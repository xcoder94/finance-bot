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

type HistoryTransactionListProps = {
  status: 'idle' | 'loading' | 'error' | 'success'
  items: HistoryItem[]
  totalCount: number
  onItemClick: (item: HistoryItem) => void
  onRetry: () => void
  loadingMore?: boolean
  loadMoreError?: boolean
  onLoadMore?: () => void
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
}: HistoryTransactionListProps) {
  const { t } = useTranslation()

  const transferLabels = {
    transfer: t('history.transfer'),
    exchange: t('history.exchange'),
  }

  return (
    <>
      {status === 'loading' ? <HistoryListSkeleton /> : null}

      {status === 'error' ? <BlockError onRetry={onRetry} /> : null}

      {status === 'success' && items.length === 0 ? (
        <div className="home-empty-card">
          <div className="home-empty-card__icon" aria-hidden="true" />
          <div className="home-empty-card__title">{t('history.emptyTitle')}</div>
          <div className="home-empty-card__hint">{t('history.emptyHint')}</div>
        </div>
      ) : null}

      {status === 'success' && items.length > 0 ? (
        <>
          <div className="home-ops-card">
            {items.map((item) => (
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
                    {formatHistoryTransactionAmount(item)}
                  </div>
                  <div className="home-ops-row__date">
                    {formatTransactionDateShort(item.transaction_date)}
                  </div>
                </div>
              </button>
            ))}
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
