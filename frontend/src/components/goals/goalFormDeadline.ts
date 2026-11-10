import { isValidIsoDate, todayTashkent } from '../../utils/dateChips'

/** `deadline` values are `YYYY-MM-DD` Tashkent calendar days; '' means no deadline. */
export function isDeadlineOnOrAfterToday(value: string, now = new Date()): boolean {
  return isValidIsoDate(value) && value >= todayTashkent(now)
}

export type GoalDeadlineHintKey = 'goals.form.deadlineInvalid' | 'addTransaction.invalidDate'

export function goalDeadlineValidation(
  deadline: string,
  options: {
    mode: 'create' | 'edit'
    existingDeadline?: string
    now?: Date
  },
): { valid: boolean; hintKey: GoalDeadlineHintKey | null } {
  const hasDeadline = deadline.length > 0
  const formatValid = !hasDeadline || isValidIsoDate(deadline)
  const notBackdated =
    !hasDeadline ||
    isDeadlineOnOrAfterToday(deadline, options.now) ||
    (options.mode === 'edit' && deadline === options.existingDeadline)

  if (formatValid && notBackdated) {
    return { valid: true, hintKey: null }
  }

  if (!formatValid) {
    return { valid: false, hintKey: 'goals.form.deadlineInvalid' }
  }

  return { valid: false, hintKey: 'addTransaction.invalidDate' }
}
