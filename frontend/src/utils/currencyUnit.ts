import i18n from 'i18next'

/** Currency word for UZS amounts: «сум» (RU) / «so'm» (UZ). Never «UZS» in the UI. */
export function sumUnit(): string {
  const lang = i18n.resolvedLanguage ?? i18n.language ?? 'ru'
  return lang.startsWith('uz') ? "so'm" : 'сум'
}
