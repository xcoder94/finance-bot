/** Mini-app confirmation copy for leave / remove / transfer — approved strings, RU/UZ in the locale files. */
import { t } from '../i18n/t'

export function leaveConfirmBody(budgetName: string): string {
  return t('memberConfirm.leaveBody', { name: budgetName })
}

export function removeConfirmBody(memberName: string): string {
  return t('memberConfirm.removeBody', { name: memberName })
}

export function transferConfirmBody(memberName: string): string {
  return t('memberConfirm.transferBody', { name: memberName })
}

export const leaveConfirmAction = (): string => t('memberConfirm.leave')
export const removeConfirmAction = (): string => t('memberConfirm.remove')
export const transferConfirmAction = (): string => t('memberConfirm.transfer')
export const memberConfirmCancel = (): string => t('formSheet.cancel')
