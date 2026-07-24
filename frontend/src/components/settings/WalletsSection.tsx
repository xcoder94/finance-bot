import { useCallback, useEffect, useState } from 'react'
import { Section } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import { createWallet, deleteWallet, getWallets, type WalletResponse } from '../../api/wallets'
import { useAuthStore } from '../../store/authStore'
import {
  getCachedWallets,
  invalidateWalletData,
  peekWallets,
} from '../../store/dataCacheStore'
import {
  EditableEntityList,
  SettingsSectionLoadError,
  SettingsSectionLoading,
} from './EditableEntityList'
import { getDisplayName } from '../../utils/getDisplayName'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; items: WalletResponse[] }

const WALLET_CURRENCY_OPTIONS = [
  { value: 'UZS', label: 'UZS' },
  { value: 'USD', label: 'USD' },
] as const

export function WalletsSection() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'
  const familyId = user?.familyBudgetId ?? ''

  const [loadState, setLoadState] = useState<LoadState>(() => {
    const cached = peekWallets(familyId)
    return cached ? { status: 'success', items: cached } : { status: 'loading' }
  })
  const [reloadCount, setReloadCount] = useState(0)

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
  }, [loadWallets, reloadCount])

  const handleAdd = async (payload: { name: string } & Record<string, string>) => {
    await createWallet({
      name: payload.name,
      currency: payload.currency as 'UZS' | 'USD',
    })
    invalidateWalletData(familyId)
    setReloadCount((count) => count + 1)
  }

  const handleDelete = async (walletId: string) => {
    await deleteWallet(walletId)
    invalidateWalletData(familyId)
    setReloadCount((count) => count + 1)
  }

  return (
    <Section header={t('settings.wallets')}>
      {loadState.status === 'loading' ? <SettingsSectionLoading /> : null}
      {loadState.status === 'error' ? (
        <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
      ) : null}
      {loadState.status === 'success' ? (
        <EditableEntityList
          items={loadState.items}
          editable={isOwner}
          addLabelKey="settings.addWallet"
          getItemDisplayName={(wallet) => getDisplayName(wallet, t)}
          getSubtitle={(wallet) => wallet.currency}
          selectFields={[
            {
              key: 'currency',
              labelKey: 'settings.currencyLabel',
              options: WALLET_CURRENCY_OPTIONS,
              defaultValue: 'UZS',
            },
          ]}
          onAdd={handleAdd}
          onDelete={handleDelete}
        />
      ) : null}
    </Section>
  )
}
