import { Button, Text, Title } from '@telegram-apps/telegram-ui'
import { Spinner } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import { formatCurrency, type Currency } from '../../utils/formatCurrency'
import { getDisplayName } from '../../utils/getDisplayName'
import {
  groupWallets,
  totalsByCurrency,
  type WalletsOverviewItem,
} from '../../utils/walletsOverview'

export type WalletsViewProps = {
  status: 'loading' | 'error' | 'success'
  wallets: WalletsOverviewItem[]
  onRetry: () => void
}

function WalletGroup({ title, wallets }: { title: string; wallets: WalletsOverviewItem[] }) {
  const { t } = useTranslation()
  return (
    <section className="wallets-group">
      <Text weight="2" className="history-summary__currency-label">
        {title}
      </Text>
      <div className="home-ops-card">
        {wallets.map((wallet) => (
          <div key={wallet.id} className="home-ops-row">
            <div className="home-ops-row__main">
              <div className="home-ops-row__title">{getDisplayName(wallet, t)}</div>
            </div>
            <div className="home-ops-row__amount home-ops-row__amount--neutral">
              {formatCurrency(wallet.balance, wallet.currency as Currency)}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

export function WalletsView({ status, wallets, onRetry }: WalletsViewProps) {
  const { t } = useTranslation()
  const { shared, personal } = groupWallets(wallets)

  return (
    <div className="page-content home-page wallets-page">
      <Title level="1" weight="2" className="home-page__title">
        {t('wallets.title')}
      </Title>

      {status === 'loading' ? (
        <div className="home-block-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      ) : status === 'error' ? (
        <div className="home-block-error" role="alert">
          <Text>{t('home.loadError')}</Text>
          <Button mode="plain" size="s" onClick={onRetry}>
            {t('auth.retry')}
          </Button>
        </div>
      ) : wallets.length === 0 ? (
        <Text className="wallets-page__empty">{t('wallets.empty')}</Text>
      ) : (
        <>
          <div className="home-figures-card wallets-total">
            <div className="home-figures-card__label">{t('wallets.total')}</div>
            {totalsByCurrency(wallets).map(({ currency, total }) => (
              <div key={currency} className="home-figures-card__balance wallets-total__value">
                {formatCurrency(total, currency as Currency)}
              </div>
            ))}
          </div>
          <Text className="wallets-page__hint">{t('wallets.hint')}</Text>
          {shared.length > 0 ? <WalletGroup title={t('wallets.shared')} wallets={shared} /> : null}
          {personal.length > 0 ? (
            <WalletGroup title={t('wallets.personal')} wallets={personal} />
          ) : null}
        </>
      )}
    </div>
  )
}
