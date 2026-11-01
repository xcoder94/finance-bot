import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import type { ShoppingItem } from '../api/shopping'
import { cancelPendingPurchaseApi, fetchPendingPurchase } from '../api/shopping'
import { useNativeBackButtonOverlay } from '../components/nativeBackButtonContext'
import { EntityDeleteConfirmSheet } from '../components/settings/EntityDeleteConfirmSheet'
import { ShoppingEditSheet } from '../components/shopping/ShoppingEditSheet'
import { ShoppingWaitingBanner } from '../components/shopping/ShoppingWaitingBanner'
import { ShoppingListView } from '../components/shopping/ShoppingListView'
import { useAuthStore } from '../store/authStore'
import { useShoppingStore } from '../store/shoppingStore'
import { browserStorage, cancelPendingPurchase, loadWaiting, type WaitingState } from '../utils/shoppingPending'

export function ShoppingPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const scope = useAuthStore((state) => state.user?.familyBudgetId ?? '')
  const status = useShoppingStore((state) => state.status)
  const items = useShoppingStore((state) => state.items)
  const load = useShoppingStore((state) => state.load)
  const add = useShoppingStore((state) => state.add)
  const rename = useShoppingStore((state) => state.rename)
  const remove = useShoppingStore((state) => state.remove)

  const [editing, setEditing] = useState<ShoppingItem | null>(null)
  const [deleting, setDeleting] = useState<ShoppingItem | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState(false)
  const [waiting, setWaiting] = useState<WaitingState | null>(null)
  const [cancelBusy, setCancelBusy] = useState(false)
  const [cancelFailed, setCancelFailed] = useState(false)

  // Opening the tab and returning to the app both re-read the list.
  useEffect(() => {
    let alive = true
    const refresh = () => {
      void load(scope, { silent: true })
      // A bot wait the user left behind: still waiting -> show it with the manual way out.
      void loadWaiting(browserStorage(), fetchPendingPurchase).then((w) => {
        if (alive) setWaiting(w)
      })
    }
    refresh()
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        refresh()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      alive = false
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [load, scope])

  const closeDelete = useCallback(() => {
    if (!deleteBusy) {
      setDeleting(null)
      setDeleteError(false)
    }
  }, [deleteBusy])
  useNativeBackButtonOverlay(deleting !== null, closeDelete)

  const confirmDelete = async () => {
    if (!deleting) {
      return
    }
    setDeleteBusy(true)
    setDeleteError(false)
    const result = await remove(deleting.id)
    setDeleteBusy(false)
    if (result === 'ok') {
      setDeleting(null)
    } else {
      setDeleteError(true)
    }
  }

  return (
    <div className="page-content">
      {waiting ? (
        <ShoppingWaitingBanner
          method={waiting.method}
          status={waiting.status}
          onManual={() => navigate(`/shopping/trip?purchase=${waiting.id}`)}
          cancelBusy={cancelBusy}
          cancelFailed={cancelFailed}
          onCancelPurchase={async () => {
            setCancelBusy(true)
            setCancelFailed(false)
            const r = await cancelPendingPurchase(browserStorage(), cancelPendingPurchaseApi, waiting.id)
            setCancelBusy(false)
            if (r.kind === 'cancelled') setWaiting(null)
            else if (r.kind === 'closed') navigate(`/shopping/trip?purchase=${waiting.id}`)
            else setCancelFailed(true)
          }}
        />
      ) : null}
      <ShoppingListView
        status={status}
        items={items}
        onRetry={() => void load(scope)}
        onAdd={add}
        onEdit={setEditing}
        onDelete={(item) => {
          setDeleteError(false)
          setDeleting(item)
        }}
        onStart={() => navigate('/shopping/trip')}
      />
      <ShoppingEditSheet item={editing} onClose={() => setEditing(null)} onSave={rename} />
      <EntityDeleteConfirmSheet
        open={deleting !== null}
        entityName={deleting?.name ?? ''}
        transactionCount={0}
        intro=""
        dangerLabel={t('settings.delete')}
        confirming={deleteBusy}
        error={deleteError}
        retryLabel={t('auth.retry')}
        errorMessage={t('settings.submitError')}
        onClose={closeDelete}
        onConfirm={() => void confirmDelete()}
      />
    </div>
  )
}
