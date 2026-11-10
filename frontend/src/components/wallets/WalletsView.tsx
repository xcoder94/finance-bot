import { Text } from '@telegram-apps/telegram-ui'
import { Spinner } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import { balanceSizeClass } from '../home/homeBlocks'
import { formatCurrency, type Currency } from '../../utils/formatCurrency'
import { getDisplayName } from '../../utils/getDisplayName'
import {
  groupWallets,
  totalsByCurrency,
  type WalletsOverviewItem,
} from '../../utils/walletsOverview'
import { BlockError } from '../BlockError'
import { ScreenTitle } from '../ScreenTitle'

export type WalletsViewProps = {
  status: 'loading' | 'error' | 'success'
  wallets: WalletsOverviewItem[]
  onRetry: () => void
  onOpenWallet: (id: string) => void
}

function WalletGroup({
  title,
  wallets,
  onOpenWallet,
}: {
  title: string
  wallets: WalletsOverviewItem[]
  onOpenWallet: (id: string) => void
}) {
  const { t } = useTranslation()
  return (
    <section className="wallets-group">
      <Text weight="2" className="history-summary__currency-label">
        {title}
      </Text>
      <div className="home-ops-card">
        {wallets.map((wallet) => (
          <button
            key={wallet.id}
            type="button"
            className="home-ops-row home-ops-row--clickable"
            onClick={() => onOpenWallet(wallet.id)}
          >
            <div className="home-ops-row__main">
              <div className="home-ops-row__title">{getDisplayName(wallet, t)}</div>
            </div>
            <div className="home-ops-row__amount home-ops-row__amount--neutral">
              {formatCurrency(wallet.balance, wallet.currency as Currency)}
            </div>
          </button>
        ))}
      </div>
    </section>
  )
}

export function WalletsView({ status, wallets, onRetry, onOpenWallet }: WalletsViewProps) {
  const { t } = useTranslation()
  const { shared, personal } = groupWallets(wallets)

  return (
    <div className="page-content home-page wallets-page">
      <ScreenTitle>{t('wallets.title')}</ScreenTitle>

      {status === 'loading' ? (
        <div className="home-block-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      ) : status === 'error' ? (
        <BlockError onRetry={onRetry} />
      ) : wallets.length === 0 ? (
        <Text className="wallets-page__empty">{t('wallets.empty')}</Text>
      ) : (
        <>
          <div className="home-figures-card wallets-total">
            <div className="home-figures-card__label">{t('wallets.total')}</div>
            {totalsByCurrency(wallets).map(({ currency, total }) => {
              const totalText = formatCurrency(total, currency as Currency)
              return (
                <div
                  key={currency}
                  className={`home-figures-card__balance wallets-total__value${balanceSizeClass(totalText)}`}
                >
                  {totalText}
                </div>
              )
            })}
          </div>
          <Text className="wallets-page__hint">{t('wallets.hint')}</Text>
          {shared.length > 0 ? (
            <WalletGroup title={t('wallets.shared')} wallets={shared} onOpenWallet={onOpenWallet} />
          ) : null}
          {personal.length > 0 ? (
            <WalletGroup
              title={t('wallets.personal')}
              wallets={personal}
              onOpenWallet={onOpenWallet}
            />
          ) : null}
        </>
      )}
    </div>
  )
}
