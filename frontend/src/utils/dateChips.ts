// Calendar-date helpers for the date chips and the period range.
// A "date" here is always a plain `YYYY-MM-DD` string meaning a Tashkent calendar day
// (PRD: every daily boundary is Tashkent-local). Tashkent has a fixed +05:00 offset.

const OFFSET = '+05:00'
const OFFSET_MS = 5 * 60 * 60 * 1000
const DAY_MS = 24 * 60 * 60 * 1000

export type ChipKey = 'today' | 'yesterday' | 'dayBefore' | 'other'
export type RangePreset = 'days7' | 'days30' | 'thisMonth' | 'lastMonth'

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function parts(iso: string): { year: number; month: number; day: number } | null {
  const match = ISO_DATE.exec(iso)
  if (!match) {
    return null
  }
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) }
}

function fromUtcMs(ms: number): string {
  const date = new Date(ms)
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`
}

export function isValidIsoDate(value: string): boolean {
  const p = parts(value)
  if (!p || p.month < 1 || p.month > 12 || p.day < 1) {
    return false
  }
  return p.day <= new Date(Date.UTC(p.year, p.month, 0)).getUTCDate()
}

export function tashkentDateOf(instant: string | Date): string {
  const date = typeof instant === 'string' ? new Date(instant) : instant
  return fromUtcMs(date.getTime() + OFFSET_MS)
}

export function todayTashkent(now: Date = new Date()): string {
  return tashkentDateOf(now)
}

export function addDays(iso: string, delta: number): string {
  const p = parts(iso)
  if (!p) {
    return iso
  }
  return fromUtcMs(Date.UTC(p.year, p.month - 1, p.day) + delta * DAY_MS)
}

export function isSelectableDate(iso: string, today: string = todayTashkent()): boolean {
  return isValidIsoDate(iso) && iso <= today
}

export function chipKeyFor(iso: string, today: string): ChipKey {
  if (iso === today) {
    return 'today'
  }
  if (iso === addDays(today, -1)) {
    return 'yesterday'
  }
  if (iso === addDays(today, -2)) {
    return 'dayBefore'
  }
  return 'other'
}

export function formatChipDate(iso: string, today: string, locale: string): string {
  const p = parts(iso)
  if (!p) {
    return ''
  }
  const sameYear = iso.slice(0, 4) === today.slice(0, 4)
  const text = new Intl.DateTimeFormat(locale, {
    timeZone: 'UTC',
    day: 'numeric',
    month: 'long',
    ...(sameYear ? {} : { year: 'numeric' as const }),
  }).format(new Date(Date.UTC(p.year, p.month - 1, p.day)))
  return text.replace(/\s*\u0433\.$/, '')
}

// New record (no original): noon of the chosen Tashkent day, as before.
// Editing: the original Tashkent time of day is kept, only the day changes.
export function dateToTransactionIso(dateIso: string, originalInstant?: string): string | null {
  if (!isValidIsoDate(dateIso)) {
    return null
  }
  let time = '12:00:00.000'
  if (originalInstant) {
    const original = new Date(originalInstant)
    if (!Number.isNaN(original.getTime())) {
      time = new Date(original.getTime() + OFFSET_MS).toISOString().slice(11, 23)
    }
  }
  return `${dateIso}T${time}${OFFSET}`
}

export function dayStartIso(dateIso: string): string {
  return `${dateIso}T00:00:00.000${OFFSET}`
}

export function dayEndIso(dateIso: string): string {
  return `${dateIso}T23:59:59.999${OFFSET}`
}

export function presetRange(preset: RangePreset, today: string): { from: string; to: string } {
  switch (preset) {
    case 'days7':
      return { from: addDays(today, -6), to: today }
    case 'days30':
      return { from: addDays(today, -29), to: today }
    case 'thisMonth':
      return { from: `${today.slice(0, 7)}-01`, to: today }
    case 'lastMonth': {
      const firstOfThis = `${today.slice(0, 7)}-01`
      const lastOfPrev = addDays(firstOfThis, -1)
      return { from: `${lastOfPrev.slice(0, 7)}-01`, to: lastOfPrev }
    }
  }
}


