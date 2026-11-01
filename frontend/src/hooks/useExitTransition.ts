import { useEffect, useState } from 'react'

/**
 * Keeps a component mounted for `ms` after `open` turns false so the exit
 * animation can play. Returns [mounted, closing].
 */
export function useExitTransition(open: boolean, ms = 200): [boolean, boolean] {
  const [mounted, setMounted] = useState(open)

  useEffect(() => {
    if (open) {
      setMounted(true)
      return
    }
    const id = setTimeout(() => setMounted(false), ms)
    return () => clearTimeout(id)
  }, [open, ms])

  return [open || mounted, !open && mounted]
}
