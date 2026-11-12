import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'

import type { ExpenseCategory, Wallet } from '../api/transactions'
import { fetchExpenseCategories, fetchWallets } from '../api/transactions'
import type { PendingMethod, ShoppingPurchase } from '../api/shopping'
import {
  createPendingPurchase,
  fetchPendingPurchase,
  cancelPendingPurchaseApi,
  fetchPurchase,
  submitPendingAmount,
} from '../api/shopping'
import { useNativeBackButtonOverlay } from '../components/nativeBackButtonContext'
import { ShoppingAmountView } from '../components/shopping/ShoppingAmountView'
import { ShoppingManualView } from '../components/shopping/ShoppingManualView'
import { refreshPersonOnReturn } from '../api/familyChanged'
import { ShoppingResultView } from '../components/shopping/ShoppingResultView'
import { ShoppingTripView } from '../components/shopping/ShoppingTripView'
import { closeMiniApp } from '../telegram/closeMiniApp'
import { useAuthStore } from '../store/authStore'
import { useHideTabbar } from '../store/chromeStore'
import {
  getCachedExpenseCategories,
  getCachedWallets,
  invalidateHomeData,
  invalidateWalletData,
} from '../store/dataCacheStore'
import { useShoppingStore } from '../store/shoppingStore'
import { haptic } from '../telegram/haptic'
import { getDisplayName } from '../utils/getDisplayName'
import {
  canFinishTrip,
  newClientToken,
  checkedIdsInListOrder,
  createTripSubmitter,
  finishTrip,
  pickTripWallet,
  resultWalletLabel,
  toggleChecked,
} from '../utils/shoppingTrip'
import {
  browserStorage,
  cancelPendingPurchase,
  clearPendingIfMatches,
  createBotStarter,
  parseLaunchParam,
  readPending,
  rememberPending,
  resolveLaunch,
  submitManualAmount,
} from '../utils/shoppingPending'
import { parsePositiveInt } from '../utils/transactionForm'
import { walletCurrencySuffix } from '../utils/transactionFormFields'
import { FailBox } from '../components/FailBox'
import { revealMessage } from '../utils/revealMessage'

type Stage = 'launch' | 'trip' | 'amount' | 'manual' | 'result'

/** Best guess of what the backend picks: «Еда · Продукты», else «Еда», else none. */
function guessCategoryLabel(
  categories: ExpenseCategory[],
  t: (key: string) => string,
): string | null {
  const groceries = categories.find((c) => c.translation_key === 'groceries')
  const food = categories.find((c) => c.translation_key === 'food')
  if (groceries && food) {
    return `${getDisplayName(food, t as never)} · ${getDisplayName(groceries, t as never)}`
  }
  return food ? getDisplayName(food, t as never) : null
}

export function ShoppingTripPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { search } = useLocation()
  const launchId = parseLaunchParam(search)

  const scope = useAuthStore((state) => state.user?.familyBudgetId ?? '')
  const defaultWalletId = useAuthStore((state) => state.user?.defaultWalletId ?? null)
  const photoEnabled = useAuthStore((state) => state.user?.receiptPhotoEnabled ?? false)
  const items = useShoppingStore((state) => state.items)
  const load = useShoppingStore((state) => state.load)
  const purchaseAction = useShoppingStore((state) => state.purchase)

  const [stage, setStage] = useState<Stage>(launchId ? 'launch' : 'trip')
  const [checked, setChecked] = useState<ReadonlySet<string>>(() => new Set())
  const [popId, setPopId] = useState<string | null>(null)
  const [amount, setAmount] = useState('')
  const [overLimit, setOverLimit] = useState(false)
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const [noWallet, setNoWallet] = useState(false)
  const [familyChanged, setFamilyChanged] = useState(false)
  const [staleList, setStaleList] = useState(false)
  const [result, setResult] = useState<{ purchase: ShoppingPurchase; requested: number } | null>(
    null,
  )
  const [botMethod, setBotMethod] = useState<PendingMethod | null>(null)
  const [manual, setManual] = useState<{
    id: string
    method: PendingMethod
    status: 'awaiting' | 'unrecognized'
  } | null>(null)
  const [cancelBusy, setCancelBusy] = useState(false)
  const [cancelFailed, setCancelFailed] = useState(false)
  const [launchFailed, setLaunchFailed] = useState(false)
  const [launchTry, setLaunchTry] = useState(0)
  const [wallets, setWallets] = useState<Wallet[] | null>(null)
  const [categories, setCategories] = useState<ExpenseCategory[] | null>(null)

  // One client_token per trip, kept until a definite answer (decision 17).
  const submitter = useRef<ReturnType<typeof createTripSubmitter> | null>(null)
  if (submitter.current === null) {
    submitter.current = createTripSubmitter((body) => purchaseAction(body))
  }
  const botStarter = useRef<ReturnType<typeof createBotStarter> | null>(null)
  if (botStarter.current === null) {
    botStarter.current = createBotStarter(
      {
        create: createPendingPurchase,
        remember: (value) => rememberPending(browserStorage(), value),
        close: closeMiniApp,
      },
      newClientToken,
    )
  }
  const submitting = useRef(false)
  // Manual entry / launch must not lock the user in: the bottom menu stays, the wait is kept.
  useHideTabbar(stage !== 'manual' && stage !== 'launch')

  useEffect(() => {
    void load(scope, { silent: true })
  }, [load, scope])

  // The person moved to another family (joined, left, removed) while the trip was open: the ticks
  // and the amount sheet belong to the old list, so go back to the list and say why.
  const tripScope = useRef(scope)
  useEffect(() => {
    if (tripScope.current === scope) return
    tripScope.current = scope
    setChecked(new Set())
    setPopId(null)
    setFailed(false)
    setNoWallet(false)
    setStage((current) => (current === 'amount' ? 'trip' : current))
    setStaleList(false)
    setFamilyChanged(true)
  }, [scope])

  // Opened from the bot's button: show the result, or the manual entry when the bot did not get it.
  useEffect(() => {
    if (!launchId) return
    let alive = true
    setLaunchFailed(false)
    void resolveLaunch(launchId, { fetchPending: fetchPendingPurchase, fetchPurchase }).then((r) => {
      if (!alive) return
      if (r.kind === 'result') {
        clearPendingIfMatches(browserStorage(), launchId)
        invalidateWalletData(scope)
        invalidateHomeData(scope)
        setResult({ purchase: r.purchase, requested: r.purchase.items_recorded })
        setStage('result')
      } else if (r.kind === 'manual') {
        setManual({ id: r.id, method: r.method, status: r.status })
        setStage('manual')
      } else if (r.kind === 'gone') {
        clearPendingIfMatches(browserStorage(), launchId)
        navigate('/shopping', { replace: true })
      } else {
        setLaunchFailed(true)
      }
    })
    return () => {
      alive = false
    }
  }, [launchId, launchTry, navigate, scope])

  useEffect(() => {
    let alive = true
    void (async () => {
      try {
        const [w, c] = await Promise.all([
          getCachedWallets(scope, fetchWallets),
          getCachedExpenseCategories(scope, fetchExpenseCategories),
        ])
        if (alive) {
          setWallets(w)
          setCategories(c)
        }
      } catch {
        // The summary rows fall back to the API text on the result screen.
      }
    })()
    return () => {
      alive = false
    }
  }, [scope])

  const wallet = useMemo(
    () => (wallets ? pickTripWallet(wallets, defaultWalletId) : null),
    [wallets, defaultWalletId],
  )
  const walletLabel = wallet ? getDisplayName(wallet, t) : null
  const categoryLabel = useMemo(
    () => (categories ? guessCategoryLabel(categories, t as never) : null),
    [categories, t],
  )

  const leave = useCallback(() => {
    if (typeof window.history.state?.idx === 'number' && window.history.state.idx > 0) {
      navigate(-1)
      return
    }
    navigate('/shopping', { replace: true })
  }, [navigate])

  const leaveToList = useCallback(() => {
    if (!busy) navigate('/shopping', { replace: true })
  }, [busy, navigate])

  const done = useCallback(() => {
    finishTrip({ load, navigate, scope })
  }, [load, navigate, scope])

  const backToTrip = useCallback(() => {
    if (!busy) setStage('trip')
  }, [busy])
  const backFromStage = stage === 'amount' ? backToTrip : stage === 'manual' || stage === 'launch' ? leaveToList : done
  useNativeBackButtonOverlay(stage !== 'trip', backFromStage)

  const onToggle = (id: string) => {
    if (!checked.has(id)) setPopId(id)
    setFamilyChanged(false)
    setStaleList(false)
    setChecked((prev) => toggleChecked(prev, id))
  }

  const ids = checkedIdsInListOrder(items, checked)

  // Every ticked item vanished from the list (a mate bought/deleted it): nothing to finish.
  useEffect(() => {
    if (stage === 'amount' && ids.length === 0) setStage('trip')
  }, [stage, ids.length])

  const onSubmit = async () => {
    const parsed = parsePositiveInt(amount)
    if (submitting.current || parsed === null || ids.length === 0) return
    submitting.current = true
    setBusy(true)
    setFailed(false)
    setNoWallet(false)
    setFamilyChanged(false)
    setStaleList(false)
    const outcome = await submitter.current!.submit(ids, parsed)
    submitting.current = false
    setBusy(false)
    if (outcome.kind === 'ok') {
      invalidateWalletData(scope)
      invalidateHomeData(scope)
      // none of the items was ours: the person may have moved to another family — reread who they are
      if (outcome.requested > 0 && outcome.purchase.items_recorded === 0) void refreshPersonOnReturn()
      setResult({ purchase: outcome.purchase, requested: outcome.requested })
      setStage('result')
    } else if (outcome.kind === 'no_wallet') {
      setNoWallet(true)
    } else if (outcome.kind === 'stale') {
      haptic.error()
      setStaleList(true)
    } else if (outcome.kind === 'family_changed') {
      haptic.error()
      setFamilyChanged(true)
    } else {
      haptic.error()
      setFailed(true)
    }
  }

  const startBot = async (method: PendingMethod, ids: string[]) => {
    if (submitting.current || ids.length === 0) return
    submitting.current = true
    setBusy(true)
    setFailed(false)
    setBotMethod(method)
    const outcome = await botStarter.current!.start(method, ids)
    submitting.current = false
    setBusy(false)
    if (outcome !== 'closed') {
      setBotMethod(null)
      haptic.error()
      setFailed(true)
    }
  }

  const onManualSubmit = async () => {
    const parsed = parsePositiveInt(amount)
    if (submitting.current || parsed === null || !manual) return
    submitting.current = true
    setBusy(true)
    setFailed(false)
    const outcome = await submitManualAmount(browserStorage(), submitPendingAmount, manual.id, parsed)
    submitting.current = false
    setBusy(false)
    if (outcome.kind === 'ok') {
      invalidateWalletData(scope)
      invalidateHomeData(scope)
      void load(scope, { silent: true })
      setResult({ purchase: outcome.purchase, requested: outcome.purchase.items_recorded })
      setStage('result')
    } else {
      haptic.error()
      setFailed(true)
    }
  }

  const onCancelPurchase = async () => {
    if (!manual || cancelBusy) return
    setCancelBusy(true)
    setCancelFailed(false)
    const r = await cancelPendingPurchase(browserStorage(), cancelPendingPurchaseApi, manual.id)
    setCancelBusy(false)
    if (r.kind === 'cancelled') {
      void load(scope, { silent: true })
      navigate('/', { replace: true })
    } else if (r.kind === 'closed') {
      setManual(null)
      setStage('launch')
      setLaunchTry((n) => n + 1) // recorded meanwhile: show its result
    } else {
      setCancelFailed(true)
    }
  }

  const remembered = manual ? readPending(browserStorage()) : null
  const retryIds = remembered && manual && remembered.id === manual.id ? remembered.ids : []

  const finishSheet =
    stage === 'amount' ? (
      <ShoppingAmountView
        count={ids.length}
        amount={amount}
        overLimit={overLimit}
        currencySuffix={walletCurrencySuffix(wallet?.currency ?? 'UZS')}
        categoryLabel={categoryLabel ?? t('shopping.noCategory')}
        walletLabel={walletLabel ?? t('shopping.walletAuto')}
        busy={busy}
        failed={failed}
        noWallet={noWallet}
        familyChanged={familyChanged}
        staleList={staleList}
        photoEnabled={photoEnabled}
        botMethod={botMethod}
        onBotMethod={(method) => void startBot(method, ids)}
        onAmount={(v) => {
          setAmount(v)
          setFailed(false)
          setNoWallet(false)
          setFamilyChanged(false)
          setStaleList(false)
        }}
        onOverLimit={setOverLimit}
        onSubmit={() => void onSubmit()}
        onBack={backToTrip}
      />
    ) : null

  let body
  if (stage === 'launch') {
    body = (
      <div className="shopping-page">
        <div className="shopping-page__header">
          <h1 className="shopping-page__title">{t('shopping.tripTitle')}</h1>
        </div>
        {launchFailed ? (
          <FailBox onRetry={() => setLaunchTry((n) => n + 1)} />
        ) : null}
      </div>
    )
  } else if (stage === 'manual' && manual) {
    body = (
      <ShoppingManualView
        method={manual.method}
        status={manual.status}
        amount={amount}
        overLimit={overLimit}
        currencySuffix={walletCurrencySuffix(wallet?.currency ?? 'UZS')}
        busy={busy}
        failed={failed}
        canRetry={retryIds.length > 0}
        onAmount={(v) => {
          setAmount(v)
          setFailed(false)
        }}
        onOverLimit={setOverLimit}
        onSubmit={() => void onManualSubmit()}
        onRetry={() => void startBot(manual.method, retryIds)}
        onCancel={leaveToList}
        onCancelPurchase={() => void onCancelPurchase()}
        cancelBusy={cancelBusy}
        cancelFailed={cancelFailed}
      />
    )
  } else if (stage === 'result' && result) {
    body = (
      <ShoppingResultView
        purchase={result.purchase}
        requested={result.requested}
        categoryLabel={categoryLabel}
        walletLabel={resultWalletLabel(result.purchase.wallet_name, wallets, t)}
        onDone={done}
      />
    )
  } else {
    body = (
      <>
        {familyChanged || staleList ? (
          <div className="shopping-amount__fail" role="alert" ref={revealMessage}>
            {familyChanged ? t('familyChanged.generic') : t('shopping.staleList')}
          </div>
        ) : null}
        <ShoppingTripView
        items={items}
        checked={checked}
        popId={popId}
        onToggle={onToggle}
        onCancel={leave}
        onFinish={() => {
          if (canFinishTrip(new Set(ids))) setStage('amount')
        }}
      />
      </>
    )
  }

  return (
    <div className="page-content">
      {body}
      {finishSheet}
    </div>
  )
}
