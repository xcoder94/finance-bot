import type { SelectedMonth } from './periodFilter'

export function twelveMonthKeysEndingAt(selected: SelectedMonth): string[] {
  let year = selected.year
  let month = selected.month
  const keys: string[] = []

  for (let index = 0; index < 12; index += 1) {
    keys.push(`${year}-${String(month).padStart(2, '0')}`)
    month -= 1
    if (month === 0) {
      month = 12
      year -= 1
    }
  }

  return keys.reverse()
}
