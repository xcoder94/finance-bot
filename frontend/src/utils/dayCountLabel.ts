export function dayCountLabel(count: number): string {
  const abs = Math.abs(count)
  const mod10 = abs % 10
  const mod100 = abs % 100

  let word: string
  if (mod100 >= 11 && mod100 <= 14) {
    word = 'дней'
  } else if (mod10 === 1) {
    word = 'день'
  } else if (mod10 >= 2 && mod10 <= 4) {
    word = 'дня'
  } else {
    word = 'дней'
  }

  return `${count} ${word}`
}
