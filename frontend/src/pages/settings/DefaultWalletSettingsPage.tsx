import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { patchMe } from '../../api/me'
import { getWallets, type WalletResponse } from '../../api/wallets'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsSectionLoadError, SettingsSectionLoading } from '../../components/settings/EditableEntityList'
import { SettingsRadioRow } from '../../components/settings/SettingsRadioRow'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import { useAuthStore } from '../../store/authStore'
import { getCachedWallets, peekWallets } from '../../store/dataCacheStore'
import { getDisplayName } from '../../utils/getDisplayName'
import { formatDefaultWalletRowSubtitle } from '../../utils/settingsSubtitles'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; items: WalletResponse[] }

export function DefaultWalletSettingsPage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const setLocalDefaultWallet = useAuthStore((state) => state.setLocalDefaultWallet)
  const familyId = user?.familyBudgetId ?? ''

  const [loadState, setLoadState] = useState<LoadState>(() => {
    const cached = peekWallets(familyId)
    return cached ? { status: 'success', items: cached } : { status: 'loading' }
  })
  const [reloadCount, setReloadCount] = useState(0)
  const [selectedWalletId, setSelectedWalletId] = useState<string | null>(
    user?.defaultWalletId ?? null,
  )

  const loadWallets = useCallback(async () => {
    setLoadState((current) => (current.status === 'success' ? current : { status: 'loading' }))
    try {
      const items = await getCachedWallets(familyId, getWallets, reloadCount > 0)
      setLoadState({ status: 'success', items })
    } catch {
      setLoadState((current) => (current.status === 'success' ? current : { status: 'error' }))
    }
  }, [familyId, reloadCount])

  useEffect(() => {
    void loadWallets()
  }, [loadWallets])

  useEffect(() => {
    setSelectedWalletId(user?.defaultWalletId ?? null)
  }, [user?.defaultWalletId])

  const wallets = loadState.status === 'success' ? loadState.items : []
  const orderedWallets = useMemo(() => {
    const shared = wallets.filter((wallet) => !wallet.is_personal)
    const personal = wallets.filter((wallet) => wallet.is_personal)
    return [...shared, ...personal]
  }, [wallets])

  const handleSelect = (walletId: string) => {
    if (walletId === selectedWalletId) {
      return
    }

    const previousWalletId = selectedWalletId
    setSelectedWalletId(walletId)
    setLocalDefaultWallet(walletId)

    void patchMe({ default_wallet_id: walletId }).catch(() => {
      setSelectedWalletId(previousWalletId)
      setLocalDefaultWallet(previousWalletId)
    })
  }

  return (
    <SettingsSubPageShell
      title={t('settings.toc.defaultWallet')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    >
      {loadState.status === 'loading' ? (
        <div className="settings-entity-page__loading">
          <SettingsSectionLoading />
        </div>
      ) : null}
      {loadState.status === 'error' ? (
        <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
      ) : null}
      {loadState.status === 'success' ? (
        <SettingsEntityGroup
          title={t('settings.defaultWallet.groupTitle')}
          note={t('settings.defaultWallet.note')}
        >
          <div className="category-picker">
            {orderedWallets.map((wallet) => (
              <SettingsRadioRow
                key={wallet.id}
                label={getDisplayName(wallet, t)}
                subtitle={formatDefaultWalletRowSubtitle(
                  wallet.is_personal,
                  wallet.currency,
                  t('settings.walletType.shared'),
                  t('settings.walletType.personal'),
                )}
                selected={selectedWalletId === wallet.id}
                onSelect={() => handleSelect(wallet.id)}
              />
            ))}
          </div>
        </SettingsEntityGroup>
      ) : null}
    </SettingsSubPageShell>
  )
}
