const NBSP = ' '

/** Digit groups joined by NBSP so a number never breaks in the middle (wrap only before the unit). */
export function groupThousands(digits: string | number): string {
  return String(digits).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP)
}
