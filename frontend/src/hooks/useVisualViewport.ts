import { useEffect, useState } from 'react'

export type ViewportBox = { height: number; offsetTop: number }

/**
 * The visible area while the on-screen keyboard is open (null when unsupported or
 * when it equals the layout viewport, so nothing is overridden in the normal case).
 */
export function useVisualViewport(enabled = true): ViewportBox | null {
  const [box, setBox] = useState<ViewportBox | null>(null)

  useEffect(() => {
    const viewport = typeof window === 'undefined' ? undefined : window.visualViewport
    if (!enabled || !viewport) {
      return
    }
    const update = () => {
      const shrunk = viewport.height < window.innerHeight - 1 || viewport.offsetTop > 0
      setBox(shrunk ? { height: viewport.height, offsetTop: viewport.offsetTop } : null)
    }
    update()
    viewport.addEventListener('resize', update)
    viewport.addEventListener('scroll', update)
    return () => {
      viewport.removeEventListener('resize', update)
      viewport.removeEventListener('scroll', update)
      setBox(null)
    }
  }, [enabled])

  return box
}
