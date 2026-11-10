import { t } from '../../i18n/t'
import { sumUnit } from '../../utils/currencyUnit'
import { groupThousands } from '../../utils/groupThousands'
export type GoalCurrency = 'UZS' | 'USD'

function formatGroupedAmount(amount: number): string {
  return groupThousands(amount)
}

export function formatGoalMoney(amount: number, currency: GoalCurrency): string {
  const formatted = formatGroupedAmount(amount)
  if (currency === 'USD') {
    return `${formatted} $`
  }
  return `${formatted} ${sumUnit()}`
}

function formatGoalDate(isoOrDate: string): string {
  const date = new Date(isoOrDate.includes('T') ? isoOrDate : `${isoOrDate}T12:00:00.000Z`)
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Asia/Tashkent',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date)
}

export function goalLeftLine(opts: {
  done: boolean
  balance: number
  target: number
  currency: GoalCurrency
}): string | null {
  if (opts.done) {
    return t('goals.frozen')
  }

  if (opts.balance > opts.target) {
    return t('goals.over', { amount: formatGoalMoney(opts.balance - opts.target, opts.currency) })
  }

  if (opts.balance === opts.target) {
    return null
  }

  return t('goals.left', { amount: formatGoalMoney(opts.target - opts.balance, opts.currency) })
}

export function goalDueLabel(
  deadline: string | null,
  closedAt: string | null,
  done: boolean,
): string {
  if (done && closedAt) {
    return t('goals.closedOn', { date: formatGoalDate(closedAt) })
  }

  if (!deadline) {
    return t('goals.noDeadline')
  }

  return t('goals.until', { date: formatGoalDate(deadline) })
}

export function goalShowCloseButton(opts: {
  isOwner: boolean
  canClose: boolean
  excessAmount: number | null
  isExactlyComplete: boolean
  status: string
}): boolean {
  if (!opts.isOwner || opts.status !== 'active') {
    return false
  }

  // balance >= target: excess when over, isExactlyComplete at 100%
  if (opts.excessAmount == null && !opts.isExactlyComplete) {
    return false
  }

  return opts.canClose || opts.isOwner
}

export function goalShowOwnerNote(opts: {
  isOwner: boolean
  excessAmount: number | null
  status: string
}): boolean {
  return !opts.isOwner && opts.status === 'active' && opts.excessAmount != null
}

/** Percent for the label and the bar: always 0..100 (a negative wallet balance shows 0). */
export function goalPercent(progressPct: number | null, balance: number, target: number): number {
  const raw =
    progressPct != null
      ? progressPct
      : target > 0
        ? Math.round((balance / target) * 100)
        : 0
  if (!Number.isFinite(raw)) {
    return 0
  }
  return Math.min(100, Math.max(0, raw))
}

export function goalProgressBarWidth(progressPct: number | null, balance: number, target: number): string {
  return `${goalPercent(progressPct, balance, target)}%`
}
