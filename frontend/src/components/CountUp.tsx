import { useLayoutEffect, useState } from 'react'

import { countUpValue, markCountUpPlayed, shouldCountUp } from '../utils/countUp'

const DURATION_MS = 650

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
}

/**
 * Short count-up from 0 on the very first show of a figure (per `id`, per session).
 * Initial render is the final value, so SSR/tests and later refreshes are static.
 */
export function CountUp({ id, value, format }: { id: string; value: number; format: (n: number) => string }) {
  const [shown, setShown] = useState(value)

  useLayoutEffect(() => {
    if (!shouldCountUp(id, value, prefersReducedMotion())) {
      setShown(value)
      return
    }
    setShown(0)
    const start = performance.now()
    let raf = requestAnimationFrame(function tick(now) {
      const progress = (now - start) / DURATION_MS
      setShown(countUpValue(value, progress))
      if (progress < 1) raf = requestAnimationFrame(tick)
      else markCountUpPlayed(id)
    })
    return () => cancelAnimationFrame(raf)
  }, [id, value])

  return <>{format(shown)}</>
}
