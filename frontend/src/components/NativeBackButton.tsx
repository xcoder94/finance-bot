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

import { historyBackTarget } from '../utils/historyBackTarget'
import {
  type BackHandler,
  NativeBackButtonContext,
} from './nativeBackButtonContext'

const ROOT_PATHS = new Set(['/', '/analytics', '/goals', '/settings'])

function normalizePathname(pathname: string): string {
  return pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
}

function fallbackPath(pathname: string, locationState: unknown): string {
  if (pathname.startsWith('/edit-')) {
    return historyBackTarget(locationState) ?? '/history'
  }
  return '/'
}

function NativeBackButtonController({
  overlayHandler,
}: {
  overlayHandler: BackHandler | null
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const pathname = normalizePathname(location.pathname)
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
      if (ROOT_PATHS.has(activePathname)) {
        return
      }

      if (activePathname === '/history') {
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

      navigate(fallbackPath(activePathname, locationStateRef.current), { replace: true })
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

    if (overlayHandler || !ROOT_PATHS.has(pathname)) {
      backButton.show()
    } else {
      backButton.hide()
    }
  }, [overlayHandler, pathname])

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
