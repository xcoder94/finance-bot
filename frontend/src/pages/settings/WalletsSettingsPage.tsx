import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  createWallet,
  deleteWallet,
  getWallets,
  patchWallet,
  type WalletResponse,
} from '../../api/wallets'
import { EntityDeleteConfirmSheet } from '../../components/settings/EntityDeleteConfirmSheet'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsSectionLoadError, SettingsSectionLoading } from '../../components/settings/EditableEntityList'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import { SwipeableSettingsRow } from '../../components/settings/SwipeableSettingsRow'
import { WalletFormSheet, type WalletFormMode } from '../../components/settings/WalletFormSheet'
import { useAuthStore } from '../../store/authStore'
import {
  getCachedWallets,
  invalidateWalletData,
  peekWallets,
} from '../../store/dataCacheStore'
import {
  countPersonalWallets,
  countSharedWallets,
  formatWalletSettingsSubtitle,
} from '../../utils/settingsSubtitles'
import { getDisplayName } from '../../utils/getDisplayName'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; items: WalletResponse[] }

type SheetState =
  | { kind: 'closed' }
  | { kind: 'form'; mode: WalletFormMode; walletId: string | null }
  | { kind: 'delete'; walletId: string }

export function WalletsSettingsPage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'
  const familyId = user?.familyBudgetId ?? ''

  const [loadState, setLoadState] = useState<LoadState>(() => {
    const cached = peekWallets(familyId)
    return cached ? { status: 'success', items: cached } : { status: 'loading' }
  })
  const [reloadCount, setReloadCount] = useState(0)
  const [sheetState, setSheetState] = useState<SheetState>({ kind: 'closed' })
  const [currencyPickerOpen, setCurrencyPickerOpen] = useState(false)
  const [walletTypePickerOpen, setWalletTypePickerOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(false)

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

  const wallets = loadState.status === 'success' ? loadState.items : []
  const sharedWallets = useMemo(
    () => wallets.filter((wallet) => !wallet.is_personal),
    [wallets],
  )
  const personalWallets = useMemo(
    () => wallets.filter((wallet) => wallet.is_personal),
    [wallets],
  )
  const sharedCount = countSharedWallets(wallets)
  const personalCount = countPersonalWallets(wallets)

  const selectedWallet =
    sheetState.kind === 'form' && sheetState.walletId
      ? wallets.find((wallet) => wallet.id === sheetState.walletId) ?? null
      : null

  const formWallet =
    sheetState.kind === 'form'
      ? sheetState.walletId
        ? wallets.find((wallet) => wallet.id === sheetState.walletId) ?? null
        : null
      : null

  const deleteWalletTarget =
    sheetState.kind === 'delete'
      ? wallets.find((wallet) => wallet.id === sheetState.walletId) ?? null
      : null

  const formEditable =
    sheetState.kind === 'form' &&
    (sheetState.mode === 'create' ||
      (formWallet !== null && (formWallet.is_personal || isOwner)))

  const openCreateForm = () => {
    setCurrencyPickerOpen(false)
    setWalletTypePickerOpen(false)
    setSheetState({ kind: 'form', mode: 'create', walletId: null })
  }

  const openEditForm = (walletId: string) => {
    setCurrencyPickerOpen(false)
    setWalletTypePickerOpen(false)
    setSheetState({ kind: 'form', mode: 'edit', walletId })
  }

  const closeSheets = () => {
    setSheetState({ kind: 'closed' })
    setCurrencyPickerOpen(false)
    setWalletTypePickerOpen(false)
    setDeleteError(false)
  }

  const refreshAfterMutation = () => {
    invalidateWalletData(familyId)
    setReloadCount((count) => count + 1)
  }

  const handleSave = async (payload: {
    name: string
    currency: 'UZS' | 'USD'
    is_personal: boolean
  }) => {
    if (sheetState.kind !== 'form') {
      return
    }

    if (sheetState.mode === 'create') {
      await createWallet({
        name: payload.name,
        currency: payload.currency,
        is_personal: payload.is_personal,
      })
    } else if (sheetState.walletId) {
      await patchWallet(sheetState.walletId, { name: payload.name })
    }
    refreshAfterMutation()
  }

  const handleConfirmDelete = async () => {
    if (!deleteWalletTarget) {
      return
    }

    setDeleting(true)
    setDeleteError(false)
    try {
      await deleteWallet(deleteWalletTarget.id)
      closeSheets()
      refreshAfterMutation()
    } catch {
      setDeleteError(true)
    } finally {
      setDeleting(false)
    }
  }

  const sharedGroupTitle = isOwner
    ? t('settings.walletGroups.sharedOwner')
    : t('settings.walletGroups.sharedMember')

  return (
    <>
      <SettingsSubPageShell
        title={t('settings.wallets')}
        backLabel={t('settings.toc.back')}
        backTo="/settings"
        actionLabel={t('settings.addWallet')}
        onAction={openCreateForm}
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
          <>
            <SettingsEntityGroup title={sharedGroupTitle}>
              {sharedWallets.map((wallet) => (
                <SwipeableSettingsRow
                  key={wallet.id}
                  name={getDisplayName(wallet, t)}
                  subtitle={formatWalletSettingsSubtitle(
                    wallet.currency,
                    wallet.balance,
                    wallet.has_active_goal,
                  )}
                  onOpen={() => {
                    if (isOwner) {
                      openEditForm(wallet.id)
                    }
                  }}
                  swipeDeleteEnabled={isOwner}
                  onDelete={() => setSheetState({ kind: 'delete', walletId: wallet.id })}
                />
              ))}
            </SettingsEntityGroup>

            <SettingsEntityGroup
              title={t('settings.walletGroups.personal')}
              note={t('settings.walletGroups.personalNote')}
            >
              {personalWallets.map((wallet) => (
                <SwipeableSettingsRow
                  key={wallet.id}
                  name={getDisplayName(wallet, t)}
                  subtitle={formatWalletSettingsSubtitle(
                    wallet.currency,
                    wallet.balance,
                    wallet.has_active_goal,
                  )}
                  onOpen={() => openEditForm(wallet.id)}
                  swipeDeleteEnabled
                  onDelete={() => setSheetState({ kind: 'delete', walletId: wallet.id })}
                />
              ))}
            </SettingsEntityGroup>
          </>
        ) : null}
      </SettingsSubPageShell>

      {sheetState.kind === 'form' ? (
        <WalletFormSheet
          open
          mode={sheetState.mode}
          wallet={formWallet}
          displayName={selectedWallet ? getDisplayName(selectedWallet, t) : undefined}
          sharedWalletCount={sharedCount}
          personalWalletCount={personalCount}
          canPickWalletType={isOwner}
          editable={formEditable}
          onClose={closeSheets}
          onSave={handleSave}
          currencyPickerOpen={currencyPickerOpen}
          onCurrencyPickerOpenChange={setCurrencyPickerOpen}
          walletTypePickerOpen={walletTypePickerOpen}
          onWalletTypePickerOpenChange={setWalletTypePickerOpen}
        />
      ) : null}

      {deleteWalletTarget ? (
        <EntityDeleteConfirmSheet
          open={sheetState.kind === 'delete'}
          entityName={getDisplayName(deleteWalletTarget, t)}
          transactionCount={deleteWalletTarget.transaction_count}
          onClose={closeSheets}
          onConfirm={() => void handleConfirmDelete()}
          confirming={deleting}
          error={deleteError}
          errorMessage={t('settings.submitError')}
          retryLabel={t('auth.retry')}
        />
      ) : null}
    </>
  )
}
