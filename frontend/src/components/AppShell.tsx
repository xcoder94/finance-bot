import {
  type CSSProperties,
  Suspense,
  lazy,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import { Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom'
import { Spinner, Tabbar } from '@telegram-apps/telegram-ui'
import { useSignal, viewport } from '@tma.js/sdk-react'
import { useTranslation } from 'react-i18next'
import { ChartPie, History, House, Settings, type LucideIcon } from 'lucide-react'

import { AddExpensePage } from '../pages/AddExpensePage'
import { AddIncomePage } from '../pages/AddIncomePage'
import { AddTransferPage } from '../pages/AddTransferPage'
import { EditExpensePage } from '../pages/EditExpensePage'
import { EditIncomePage } from '../pages/EditIncomePage'
import { EditTransferPage } from '../pages/EditTransferPage'
import { HistoryPage } from '../pages/HistoryPage'
import { HomePage } from '../pages/HomePage'
import { SettingsPage } from '../pages/SettingsPage'
import { NativeBackButtonProvider } from './NativeBackButton'

const AnalyticsPage = lazy(() => import('../pages/AnalyticsPage'))

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
  }, [])

  const tabs = [
    { path: '/', label: t('nav.home'), icon: House, end: true },
    { path: '/analytics', label: t('nav.analytics'), icon: ChartPie, end: false },
    { path: '/history', label: t('nav.history'), icon: History, end: false },
    { path: '/settings', label: t('nav.settings'), icon: Settings, end: false },
  ] as const

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
        <Outlet />
      </main>

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

export function AppShell() {
  return (
    <NativeBackButtonProvider>
      <Routes>
        <Route path="add-income" element={<AddIncomePage />} />
        <Route path="add-expense" element={<AddExpensePage />} />
        <Route path="add-transfer" element={<AddTransferPage />} />
        <Route path="edit-income/:id" element={<EditIncomePage />} />
        <Route path="edit-expense/:id" element={<EditExpensePage />} />
        <Route path="edit-transfer/:id" element={<EditTransferPage />} />
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="analytics/*" element={<AnalyticsRoute />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </NativeBackButtonProvider>
  )
}
