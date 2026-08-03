export function dayWordRu(count: number): string {
  const abs = Math.abs(count)
  const mod10 = abs % 10
  const mod100 = abs % 100

  if (mod100 >= 11 && mod100 <= 14) {
    return 'дней'
  }
  if (mod10 === 1) {
    return 'день'
  }
  if (mod10 >= 2 && mod10 <= 4) {
    return 'дня'
  }
  return 'дней'
}

export function dayCountLabel(count: number): string {
  return `${count} ${dayWordRu(count)}`
}
