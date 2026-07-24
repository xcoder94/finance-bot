import { createContext, useContext, useEffect } from 'react'

export type BackHandler = () => void

type NativeBackButtonContextValue = {
  registerOverlayBackHandler: (handler: BackHandler) => () => void
}

export const NativeBackButtonContext = createContext<NativeBackButtonContextValue | null>(null)

export function useNativeBackButtonOverlay(open: boolean, onBack: BackHandler) {
  const context = useContext(NativeBackButtonContext)

  useEffect(() => {
    if (!open || !context) {
      return
    }
    return context.registerOverlayBackHandler(onBack)
  }, [context, onBack, open])
}
