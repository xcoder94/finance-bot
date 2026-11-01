import { useEffect, useRef, useState } from 'react'

import { findRemoved, withLeaving, type Displayed, type Removed } from '../utils/leavingItems'

/** Items plus the ones just removed (flagged `leaving`) for `ms` so they can collapse. */
export function useLeavingItems<T extends { id: string }>(items: T[], ms = 220): Displayed<T>[] {
  const prev = useRef(items)
  const [ghosts, setGhosts] = useState<Removed<T>[]>([])

  useEffect(() => {
    const removed = findRemoved(prev.current, items)
    prev.current = items
    if (removed.length === 0) return
    setGhosts((g) => [...g, ...removed])
    const ids = new Set(removed.map((r) => r.item.id))
    const timer = setTimeout(() => setGhosts((g) => g.filter((x) => !ids.has(x.item.id))), ms)
    return () => clearTimeout(timer)
  }, [items, ms])

  return withLeaving(items, ghosts)
}
