import { t } from '../i18n/t'

/** Currency word for UZS amounts: «сум» (RU) / «so'm» (UZ). Never «UZS» in the UI. */
export function sumUnit(): string {
  return t('common.sumUnit')
}
