import { init, themeParams } from '@tma.js/sdk-react'

export function bindTelegramThemeParams(): () => void {
  init()
  themeParams.mount()
  const unbindCssVars = themeParams.bindCssVars()

  return () => {
    unbindCssVars()
    themeParams.unmount()
  }
}
