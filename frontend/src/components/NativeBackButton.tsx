import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { backButton } from '@tma.js/sdk-react'
import { useLocation, useNavigate } from 'react-router-dom'

import { backFallbackPath } from '../utils/backFallback'
import { historyBackTarget, isRootPath } from '../utils/historyBackTarget'
import {
  type BackHandler,
  NativeBackButtonContext,
} from './nativeBackButtonContext'

function normalizePathname(pathname: string): string {
  return pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
}

function NativeBackButtonController({
  overlayHandler,
}: {
  overlayHandler: BackHandler | null
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const pathname = normalizePathname(location.pathname)
  const locationState = location.state
  const pathnameRef = useRef(pathname)
  const locationStateRef = useRef(location.state)
  const overlayHandlerRef = useRef(overlayHandler)

  pathnameRef.current = pathname
  locationStateRef.current = location.state
  overlayHandlerRef.current = overlayHandler

  useEffect(() => {
    if (!backButton.isSupported()) {
      return
    }

    backButton.mount()
    const offClick = backButton.onClick(() => {
      const activeOverlayHandler = overlayHandlerRef.current
      if (activeOverlayHandler) {
        activeOverlayHandler()
        return
      }

      const activePathname = pathnameRef.current
      if (isRootPath(activePathname, locationStateRef.current)) {
        return
      }

      if (activePathname === '/history' || activePathname === '/analytics') {
        const backTarget = historyBackTarget(locationStateRef.current)
        if (backTarget) {
          navigate(backTarget, { replace: true })
          return
        }
      }

      const historyIndex = window.history.state?.idx
      if (typeof historyIndex === 'number' && historyIndex > 0) {
        navigate(-1)
        return
      }

      navigate(backFallbackPath(activePathname, locationStateRef.current), { replace: true })
    })

    return () => {
      offClick()
      backButton.hide()
      backButton.unmount()
    }
  }, [navigate])

  useEffect(() => {
    if (!backButton.isSupported() || !backButton.isMounted()) {
      return
    }

    if (overlayHandler || !isRootPath(pathname, locationState)) {
      backButton.show()
    } else {
      backButton.hide()
    }
  }, [overlayHandler, pathname, locationState])

  return null
}

export function NativeBackButtonProvider({ children }: { children: ReactNode }) {
  const [overlayHandler, setOverlayHandler] = useState<BackHandler | null>(null)

  const registerOverlayBackHandler = useCallback((handler: BackHandler) => {
    setOverlayHandler(() => handler)

    return () => {
      setOverlayHandler((current) => (current === handler ? null : current))
    }
  }, [])
  const contextValue = useMemo(
    () => ({ registerOverlayBackHandler }),
    [registerOverlayBackHandler],
  )

  return (
    <NativeBackButtonContext.Provider value={contextValue}>
      <NativeBackButtonController overlayHandler={overlayHandler} />
      {children}
    </NativeBackButtonContext.Provider>
  )
}
