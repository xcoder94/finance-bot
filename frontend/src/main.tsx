import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@telegram-apps/telegram-ui/dist/styles.css'

import App from './App.tsx'
import './i18n'
import './index.css'
import { bindTelegramThemeParams } from './telegram/bindThemeParams.ts'

async function bootstrap() {
  if (import.meta.env.DEV) {
    const { setupDevTelegramEnv } = await import('./dev/mockTelegramEnv.ts')
    await setupDevTelegramEnv()
  }

  bindTelegramThemeParams()

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>,
  )
}

void bootstrap()
