import { AppRoot } from '@telegram-apps/telegram-ui'
import { themeParams, useSignal } from '@tma.js/sdk-react'

import { AppShell } from './components/AppShell'
import { AuthErrorScreen } from './components/AuthErrorScreen'
import { SplashScreen } from './components/SplashScreen'
import { useAuthBootstrap } from './hooks/useAuthBootstrap'
import { useAuthStore } from './store/authStore'

function App() {
  const { retry } = useAuthBootstrap()
  const status = useAuthStore((state) => state.status)
  const errorType = useAuthStore((state) => state.errorType)
  const isDark = useSignal(themeParams.isDark)

  let content
  if (status === 'loading') {
    content = <SplashScreen />
  } else if (status === 'error' && errorType) {
    content = <AuthErrorScreen errorType={errorType} onRetry={retry} />
  } else {
    content = <AppShell />
  }

  const appearance = isDark ? 'dark' : 'light'

  return (
    <AppRoot appearance={appearance}>
      <div className="app-theme" data-theme={appearance}>
        {content}
      </div>
    </AppRoot>
  )
}

export default App
