export type GoalCurrency = 'UZS' | 'USD'

function formatGroupedAmount(amount: number): string {
  return amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

export function formatGoalMoney(amount: number, currency: GoalCurrency): string {
  const formatted = formatGroupedAmount(amount)
  if (currency === 'USD') {
    return `${formatted} $`
  }
  return `${formatted} сум`
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
    return 'Показатели заморожены'
  }

  if (opts.balance > opts.target) {
    return `Накоплено на ${formatGoalMoney(opts.balance - opts.target, opts.currency)} больше`
  }

  if (opts.balance === opts.target) {
    return null
  }

  return `Осталось ${formatGoalMoney(opts.target - opts.balance, opts.currency)}`
}

export function goalDueLabel(
  deadline: string | null,
  closedAt: string | null,
  done: boolean,
): string {
  if (done && closedAt) {
    return `закрыта ${formatGoalDate(closedAt)}`
  }

  if (!deadline) {
    return 'без срока'
  }

  return `до ${formatGoalDate(deadline)}`
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

export function goalProgressBarWidth(progressPct: number | null, balance: number, target: number): string {
  if (progressPct != null) {
    return `${Math.min(100, progressPct)}%`
  }

  if (target <= 0) {
    return '0%'
  }

  return `${Math.min(100, Math.round((balance / target) * 100))}%`
}
