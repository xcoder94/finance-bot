export type Removed<T> = { item: T; index: number }
export type Displayed<T> = { item: T; leaving: boolean }

/** Items that were in `prev` but are gone from `next` (to play a collapse animation). */
export function findRemoved<T extends { id: string }>(prev: T[], next: T[]): Removed<T>[] {
  const alive = new Set(next.map((i) => i.id))
  const out: Removed<T>[] = []
  prev.forEach((item, index) => {
    if (!alive.has(item.id)) out.push({ item, index })
  })
  return out
}

/** Live items plus leaving ghosts re-inserted at their old positions. */
export function withLeaving<T extends { id: string }>(live: T[], ghosts: Removed<T>[]): Displayed<T>[] {
  const out: Displayed<T>[] = live.map((item) => ({ item, leaving: false }))
  const liveIds = new Set(live.map((i) => i.id))
  const sorted = [...ghosts].filter((g) => !liveIds.has(g.item.id)).sort((x, y) => x.index - y.index)
  for (const g of sorted) {
    out.splice(Math.min(g.index, out.length), 0, { item: g.item, leaving: true })
  }
  return out
}
