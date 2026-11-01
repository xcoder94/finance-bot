import { useEffect, useState } from 'react'

import { useSuccessFlashStore } from '../store/successFlashStore'
import { AnimatedTick } from './AnimatedTick'

const SHOW_MS = 1000

/** Centered animated tick shown briefly after a successful save; never blocks taps. */
export function SuccessFlash() {
  const token = useSuccessFlashStore((s) => s.token)
  const [visibleToken, setVisibleToken] = useState(0)

  useEffect(() => {
    if (token === 0) return
    setVisibleToken(token)
    const id = setTimeout(() => setVisibleToken(0), SHOW_MS)
    return () => clearTimeout(id)
  }, [token])

  if (visibleToken === 0) return null
  return (
    <div key={visibleToken} className="success-flash" aria-hidden="true">
      <div className="success-flash__badge">
        <AnimatedTick size={34} />
      </div>
    </div>
  )
}
