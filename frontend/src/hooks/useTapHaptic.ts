import { useEffect } from 'react'

import { haptic, isHapticTapTarget } from '../telegram/haptic'

/** Light impact on every tap of an enabled button or tab (one delegated listener). */
export function useTapHaptic(): void {
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const target = event.target
      if (target instanceof Element && isHapticTapTarget(target)) haptic.light()
    }
    document.addEventListener('click', onClick, true)
    return () => document.removeEventListener('click', onClick, true)
  }, [])
}
