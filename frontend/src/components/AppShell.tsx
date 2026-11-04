import {
  type CSSProperties,
  Suspense,
  lazy,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import {
  type Location,
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigationType,
} from 'react-router-dom'
import { Spinner, Tabbar } from '@telegram-apps/telegram-ui'
import { useSignal, viewport } from '@tma.js/sdk-react'
import { useTranslation } from 'react-i18next'
import { type LucideIcon } from 'lucide-react'

import { AddExpensePage } from '../pages/AddExpensePage'
import { AddIncomePage } from '../pages/AddIncomePage'
import { AddTransferPage } from '../pages/AddTransferPage'
import { EditExpensePage } from '../pages/EditExpensePage'
import { EditIncomePage } from '../pages/EditIncomePage'
import { EditTransferPage } from '../pages/EditTransferPage'
import { GoalsPage } from '../pages/GoalsPage'
import { HistoryPage } from '../pages/HistoryPage'
import { WalletDetailPage } from '../pages/WalletDetailPage'
import { WalletsPage } from '../pages/WalletsPage'
import { HomePage } from '../pages/HomePage'
import { ShoppingPage } from '../pages/ShoppingPage'
import { ShoppingTripPage } from '../pages/ShoppingTripPage'
import { SettingsPage } from '../pages/SettingsPage'
import { TransactionGonePage } from '../pages/TransactionGonePage'
import { DefaultWalletSettingsPage } from '../pages/settings/DefaultWalletSettingsPage'
import { ExpenseCategoriesSettingsPage } from '../pages/settings/ExpenseCategoriesSettingsPage'
import { ExpenseSubcategoriesSettingsPage } from '../pages/settings/ExpenseSubcategoriesSettingsPage'
import { IncomeCategoriesSettingsPage } from '../pages/settings/IncomeCategoriesSettingsPage'
import { LanguageSettingsPage } from '../pages/settings/LanguageSettingsPage'
import { MembersSettingsPage } from '../pages/settings/MembersSettingsPage'
import { MemberDetailPage } from '../pages/settings/MemberDetailPage'
import { NotificationsSettingsShellPage } from '../pages/settings/NotificationsSettingsShellPage'
import { AdminPage } from '../pages/admin/AdminPage'
import { WalletsSettingsPage } from '../pages/settings/WalletsSettingsPage'
import { NativeBackButtonProvider } from './NativeBackButton'
import { MAIN_TABS } from './mainTabs'
import { usePageDirection } from '../hooks/usePageDirection'
import { pageScreenKey } from '../utils/pageTransition'
import { useShoppingStartup } from '../hooks/useShoppingStartup'
import { useTapHaptic } from '../hooks/useTapHaptic'
import { useTxDeepLink } from '../hooks/useTxDeepLink'
import { SuccessFlash } from './SuccessFlash'
import { useChromeStore } from '../store/chromeStore'

export { MAIN_TABS } from './mainTabs'

const AnalyticsPage = lazy(() => import('../pages/AnalyticsPage'))

/** Home passes its own location as `state.background` when it opens a form over itself. */
export function backgroundLocation(state: unknown): Location | null {
  const bg = (state as { background?: Location } | null)?.background
  return bg && typeof bg.pathname === 'string' ? bg : null
}

let viewportMountPromise: Promise<void> | null = null

function ensureViewportMounted(): Promise<void> {
  if (viewport.isMounted()) {
    return Promise.resolve()
  }
  if (!viewportMountPromise) {
    viewportMountPromise = viewport
      .mount()
      .then(() => undefined)
      .catch((error: unknown) => {
        viewportMountPromise = null
        throw error
      })
  }
  return viewportMountPromise
}

function TabIcon({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span className="tabbar-icon" aria-hidden="true">
      <Icon size={24} strokeWidth={2} />
    </span>
  )
}

function AppLayout() {
  const { t } = useTranslation()
  const tabbarHostRef = useRef<HTMLDivElement>(null)
  const [tabbarHeight, setTabbarHeight] = useState(0)
  const tabbarHidden = useChromeStore((s) => s.tabbarHidden)
  const location = useLocation()
  const navigationType = useNavigationType()
  const pageKey = pageScreenKey(location.pathname)
  const pageDirection = usePageDirection(location.pathname, navigationType)
  const viewportHeight = useSignal(viewport.height)
  const safeAreaBottom = useSignal(viewport.safeAreaInsetBottom)
  const contentSafeAreaBottom = useSignal(viewport.contentSafeAreaInsetBottom)

  useEffect(() => {
    void ensureViewportMounted()
      .then(() => {
        if (!viewport.isCssVarsBound()) {
          viewport.bindCssVars()
        }
      })
      .catch(() => undefined)
  }, [])

  useLayoutEffect(() => {
    if (tabbarHidden) {
      setTabbarHeight(0)
      return
    }
    const host = tabbarHostRef.current
    const renderedTabbar = host?.firstElementChild
    if (!host || !renderedTabbar) {
      return
    }

    const updateHeight = () => {
      setTabbarHeight(Math.ceil(renderedTabbar.getBoundingClientRect().height))
    }
    updateHeight()

    const observer = new ResizeObserver(updateHeight)
    observer.observe(renderedTabbar)
    window.addEventListener('resize', updateHeight)
    window.visualViewport?.addEventListener('resize', updateHeight)

    return () => {
      observer.disconnect()
      window.removeEventListener('resize', updateHeight)
      window.visualViewport?.removeEventListener('resize', updateHeight)
    }
  }, [tabbarHidden])

  const tabs = MAIN_TABS.map((tab) => ({
    ...tab,
    label: t(tab.labelKey),
  }))

  return (
    <div
      className="app-shell"
      style={
        {
          '--app-tabbar-height': `${tabbarHeight}px`,
          '--app-content-safe-area-bottom': `${Math.max(
            safeAreaBottom ?? 0,
            contentSafeAreaBottom ?? 0,
          )}px`,
          '--app-viewport-height': viewportHeight ? `${viewportHeight}px` : '100svh',
        } as CSSProperties
      }
    >
      <main className="app-shell__main">
        <div
          key={pageKey}
          className="app-shell__page"
          data-direction={pageDirection}
        >
          <Outlet />
        </div>
      </main>

      {tabbarHidden ? null : (
      <div ref={tabbarHostRef} className="app-shell__tabbar">
        <Tabbar>
          {tabs.map((tab) => (
            <NavLink
              key={tab.path}
              to={tab.path}
              end={tab.end}
              className="tabbar-link"
            >
              {({ isActive }) => (
                <Tabbar.Item selected={isActive} text={tab.label}>
                  <TabIcon icon={tab.icon} />
                </Tabbar.Item>
              )}
            </NavLink>
          ))}
        </Tabbar>
      </div>
      )}
    </div>
  )
}

function AnalyticsRoute() {
  const { t } = useTranslation()

  return (
    <Suspense
      fallback={
        <div
          className="page-content page-content--centered"
          role="status"
          aria-live="polite"
        >
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      }
    >
      <AnalyticsPage />
    </Suspense>
  )
}

function TxDeepLinkResolvingScreen() {
  const { t } = useTranslation()

  return (
    <div
      className="page-content page-content--centered"
      role="status"
      aria-live="polite"
    >
      <Spinner size="m" aria-hidden="true" />
      <span className="visually-hidden">{t('home.loading')}</span>
    </div>
  )
}

export function AppShell() {
  const location = useLocation()
  const background = backgroundLocation(location.state)
  useTapHaptic()
  const txDeepLinkPhase = useTxDeepLink()
  useShoppingStartup()

  if (txDeepLinkPhase === 'resolving') {
    return (
      <NativeBackButtonProvider>
        <TxDeepLinkResolvingScreen />
      </NativeBackButtonProvider>
    )
  }

  return (
    <NativeBackButtonProvider>
      <Routes location={background ?? location}>
        <Route path="add-income" element={<AddIncomePage />} />
        <Route path="add-expense" element={<AddExpensePage />} />
        <Route path="add-transfer" element={<AddTransferPage />} />
        <Route path="edit-income/:id" element={<EditIncomePage />} />
        <Route path="edit-expense/:id" element={<EditExpensePage />} />
        <Route path="edit-transfer/:id" element={<EditTransferPage />} />
        <Route path="transaction-gone" element={<TransactionGonePage />} />
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="shopping" element={<ShoppingPage />} />
          <Route path="shopping/trip" element={<ShoppingTripPage />} />
          <Route path="analytics/*" element={<AnalyticsRoute />} />
          <Route path="goals" element={<GoalsPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="wallets" element={<WalletsPage />} />
          <Route path="wallets/:id" element={<WalletDetailPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="settings/wallets" element={<WalletsSettingsPage />} />
          <Route path="settings/default-wallet" element={<DefaultWalletSettingsPage />} />
          <Route path="settings/income-categories" element={<IncomeCategoriesSettingsPage />} />
          <Route path="settings/expense-categories" element={<ExpenseCategoriesSettingsPage />} />
          <Route
            path="settings/expense-categories/:parentId"
            element={<ExpenseSubcategoriesSettingsPage />}
          />
          <Route path="settings/members" element={<MembersSettingsPage />} />
          <Route path="settings/members/:id" element={<MemberDetailPage />} />
          <Route path="settings/notifications" element={<NotificationsSettingsShellPage />} />
          <Route path="settings/language" element={<LanguageSettingsPage />} />
          <Route path="admin" element={<AdminPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {background ? (
        // Opened from Home: the page stays mounted underneath, only the sheet is drawn on top.
        <Routes>
          <Route path="add-income" element={<AddIncomePage />} />
          <Route path="add-expense" element={<AddExpensePage />} />
          <Route path="add-transfer" element={<AddTransferPage />} />
          <Route path="edit-income/:id" element={<EditIncomePage />} />
          <Route path="edit-expense/:id" element={<EditExpensePage />} />
          <Route path="edit-transfer/:id" element={<EditTransferPage />} />
          <Route path="*" element={null} />
        </Routes>
      ) : null}
      <SuccessFlash />
    </NativeBackButtonProvider>
  )
}
