import { Spinner } from '@telegram-apps/telegram-ui'

export function SplashScreen() {
  return (
    <div className="auth-screen">
      <Spinner size="m" />
      <p className="auth-screen__message">Загрузка…</p>
    </div>
  )
}
