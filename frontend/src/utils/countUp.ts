const played = new Set<string>()

export function resetCountUpPlayed(): void {
  played.clear()
}

export function markCountUpPlayed(id: string): void {
  played.add(id)
}

/** Count-up runs only on the first show of a figure, never for 0 or under reduced motion. */
export function shouldCountUp(id: string, target: number, reducedMotion: boolean): boolean {
  return !reducedMotion && target !== 0 && !played.has(id)
}

/** Ease-out cubic from 0 to target; progress is clamped to 0..1. */
export function countUpValue(target: number, progress: number): number {
  const p = Math.min(1, Math.max(0, progress))
  const eased = 1 - Math.pow(1 - p, 3)
  return Math.round(target * eased)
}
