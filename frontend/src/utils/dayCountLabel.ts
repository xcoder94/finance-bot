import { t } from '../i18n/t'

/** Day word agreed with the number (RU: день/дня/дней; UZ: kun). */
export function dayWordRu(count: number): string {
  return t('common.day', { count: Math.abs(count) })
}

export function dayCountLabel(count: number): string {
  return `${count} ${dayWordRu(count)}`
}
