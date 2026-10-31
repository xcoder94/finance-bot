import type { AdminRetention, AdminUser } from '../api/admin'

const TASHKENT_TZ = 'Asia/Tashkent'
const DASH = '—'

/** "X% (n из N)", or a dash when the cohort is empty (percent is null). */
export function retentionValue(
  retention: AdminRetention,
  nOfN: (returned: number, cohort: number) => string,
): string {
  if (retention.percent === null || retention.cohort === 0) {
    return DASH
  }
  const percent = Number.isInteger(retention.percent)
    ? String(retention.percent)
    : retention.percent.toFixed(1).replace('.', ',')
  return `${percent}% (${nOfN(retention.returned, retention.cohort)})`
}

/** Tooltip "name: value" separator for the growth chart. */
export const CHART_TOOLTIP_SEPARATOR = ': '

function tashkentParts(iso: string): Record<string, string> {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: TASHKENT_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(iso))
  return Object.fromEntries(parts.map((p) => [p.type, p.value]))
}

/** DD.MM.YYYY in Tashkent time. */
export function formatRegisteredDate(iso: string): string {
  const p = tashkentParts(iso)
  return `${p.day}.${p.month}.${p.year}`
}

/** DD.MM HH:MM in Tashkent time, or a dash when never seen. */
export function formatLastSeen(iso: string | null): string {
  if (!iso) {
    return DASH
  }
  const p = tashkentParts(iso)
  return `${p.day}.${p.month} ${p.hour}:${p.minute}`
}

/** A calendar day "YYYY-MM-DD" (already Tashkent) as DD.MM.YYYY. */
export function formatSinceDate(day: string): string {
  const [y, m, d] = day.split('-')
  return `${d}.${m}.${y}`
}

/** DD.MM label for a chart bar from "YYYY-MM-DD". */
export function formatDayLabel(day: string): string {
  const [, m, d] = day.split('-')
  return `${d}.${m}`
}

const USERNAME = /^[A-Za-z0-9_]{1,32}$/

export function telegramLink(username: string | null): string | null {
  if (!username) {
    return null
  }
  const name = username.replace(/^@/, '')
  return USERNAME.test(name) ? `https://t.me/${name}` : null
}

/** Appends the next page, dropping rows already shown (new sign-ups can shift pages). */
export function appendUsersPage<T extends { id: string }>(current: T[], page: T[]): T[] {
  const seen = new Set(current.map((u) => u.id))
  return [...current, ...page.filter((u) => !seen.has(u.id))]
}

export type { AdminUser }
