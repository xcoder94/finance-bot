import { Text, Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import type { HistoryItem } from '../../api/history'
import { formatCurrency, type Currency } from '../../utils/formatCurrency'
import { getDisplayName } from '../../utils/getDisplayName'
import type { HomeMonth } from '../../utils/homeMonth'
import { formatMonthLabel } from '../../utils/periodFilter'
import { walletOpAmount, type WalletOpsState } from '../../utils/walletOps'
import type { WalletsOverviewItem } from '../../utils/walletsOverview'
import { HistoryTransactionList } from '../history/HistoryTransactionList'

export type WalletOpsViewProps = {
  wallet: WalletsOverviewItem
  month: HomeMonth
  ops: WalletOpsState
  onPrevMonth: () => void
  onNextMonth: () => void
  onOpenItem: (item: HistoryItem) => void
  onRetry: () => void
  onLoadMore: () => void
}

export function WalletOpsView({
  wallet,
  month,
  ops,
  onPrevMonth,
  onNextMonth,
  onOpenItem,
  onRetry,
  onLoadMore,
}: WalletOpsViewProps) {
  const { t } = useTranslation()

  return (
    <div className="page-content home-page wallets-page">
      <Title level="1" weight="2" className="home-page__title">
        {getDisplayName(wallet, t)}
      </Title>

      <div className="home-figures-card wallets-total">
        <div className="home-figures-card__label">{t('wallets.balanceNow')}</div>
        <div className="home-figures-card__balance wallets-total__value">
          {formatCurrency(wallet.balance, wallet.currency as Currency)}
        </div>
      </div>

      <div className="home-page__month-selector">
        <button
          type="button"
          className="home-month-nav__button"
          aria-label={t('home.previousMonth')}
          onClick={onPrevMonth}
        >
          ‹
        </button>
        <Text weight="2" className="home-page__month-label">
          {formatMonthLabel(month)}
        </Text>
        <button
          type="button"
          className="home-month-nav__button"
          aria-label={t('home.nextMonth')}
          onClick={onNextMonth}
        >
          ›
        </button>
      </div>

      <div className="history-page__list">
        <HistoryTransactionList
          status={ops.status}
          items={ops.items}
          totalCount={ops.total}
          onItemClick={onOpenItem}
          onRetry={onRetry}
          loadingMore={ops.loadingMore}
          loadMoreError={ops.loadMoreError}
          onLoadMore={onLoadMore}
          formatAmount={(item) => walletOpAmount(item, wallet.id)}
          emptyHint={t('wallets.opsEmptyHint')}
        />
      </div>
    </div>
  )
}
