import type { AdminUsage, AdminUsagePeriod } from '../api/admin'

const DASH = '—'

function decimalComma(value: string): string {
  return value.replace('.', ',')
}

/** Cost in dollars, two decimals; "≈" when some calls came without token counts. */
export function formatUsd(value: number, incomplete: boolean): string {
  const text = `$${decimalComma(value.toFixed(2))}`
  return incomplete ? `≈ ${text}` : text
}

/** Thousands separated by a non-breaking space. */
export function formatTokens(value: number): string {
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

/** "X% (n of N)", or a dash when no messages went to parsing. */
export function unparsedValue(
  unparsed: number,
  messages: number,
  format: (percent: string, n: number, total: number) => string,
): string {
  if (messages <= 0) {
    return DASH
  }
  const raw = (unparsed / messages) * 100
  const percent = Number.isInteger(raw) ? String(raw) : decimalComma(raw.toFixed(1))
  return format(percent, unparsed, messages)
}

export type OpsState =
  | { period: AdminUsagePeriod; status: 'loading' }
  | { period: AdminUsagePeriod; status: 'error' }
  | { period: AdminUsagePeriod; status: 'ready'; data: AdminUsage }

export type OpsAction =
  | { type: 'select'; period: AdminUsagePeriod }
  | { type: 'loaded'; period: AdminUsagePeriod; data: AdminUsage }
  | { type: 'failed'; period: AdminUsagePeriod }
  | { type: 'retry' }

export const initialOpsState: OpsState = { period: 'day', status: 'loading' }

/** Responses for a period that is no longer selected are dropped. */
export function opsReducer(state: OpsState, action: OpsAction): OpsState {
  switch (action.type) {
    case 'select':
      // Tapping the already selected period changes nothing (and requests nothing).
      return action.period === state.period ? state : { period: action.period, status: 'loading' }
    case 'loaded':
      return action.period === state.period ? { period: state.period, status: 'ready', data: action.data } : state
    case 'retry':
      return { period: state.period, status: 'loading' }
    case 'failed':
      return action.period === state.period ? { period: state.period, status: 'error' } : state
  }
}
