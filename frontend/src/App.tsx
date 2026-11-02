import { AppRoot } from '@telegram-apps/telegram-ui'
import { useEffect } from 'react'

import { AppShell } from './components/AppShell'
import { AuthErrorScreen } from './components/AuthErrorScreen'
import { SplashScreen } from './components/SplashScreen'
import { useAuthBootstrap } from './hooks/useAuthBootstrap'
import { useAuthStore } from './store/authStore'
import { useThemeStore } from './store/themeStore'

function App() {
  const { retry } = useAuthBootstrap()
  const status = useAuthStore((state) => state.status)
  const errorType = useAuthStore((state) => state.errorType)
  const appearance = useThemeStore((state) => state.theme)
  const hydrateTheme = useThemeStore((state) => state.hydrate)
  const watchSystemTheme = useThemeStore((state) => state.watchSystem)

  useEffect(() => {
    void hydrateTheme()
  }, [hydrateTheme])

  useEffect(() => watchSystemTheme(), [watchSystemTheme])

  let content
  if (status === 'loading') {
    content = <SplashScreen />
  } else if (status === 'error' && errorType) {
    content = <AuthErrorScreen errorType={errorType} onRetry={retry} />
  } else {
    content = <AppShell />
  }

  return (
    <AppRoot appearance={appearance}>
      <div className="app-theme" data-theme={appearance}>
        {content}
      </div>
    </AppRoot>
  )
}

export default App
