import i18n from '../i18n'
import { sumUnit } from './currencyUnit'

export type TrendAxisScale = {
  divisor: number
  unitKey: 'thousand' | 'million' | 'billion' | null
}

/** One unit for the whole axis, chosen by the largest value shown. */
export function chooseTrendAxisScale(maxValue: number): TrendAxisScale {
  const max = Math.abs(Number.isFinite(maxValue) ? maxValue : 0)
  if (max >= 1_000_000_000) return { divisor: 1_000_000_000, unitKey: 'billion' }
  if (max >= 1_000_000) return { divisor: 1_000_000, unitKey: 'million' }
  if (max >= 1_000) return { divisor: 1_000, unitKey: 'thousand' }
  return { divisor: 1, unitKey: null }
}

function axisLocale(): string {
  return (i18n.resolvedLanguage ?? i18n.language).startsWith('uz') ? 'uz-Latn-UZ' : 'ru-RU'
}

/** Tick value in the axis unit, digits only (never wraps). */
export function formatTrendAxisTick(value: number, scale: TrendAxisScale): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  return (numeric / scale.divisor)
    .toLocaleString(axisLocale(), { minimumFractionDigits: 0, maximumFractionDigits: 1 })
    .replace(/[\s  ]/g, '')
}

/** Caption that names the same unit the ticks use. */
export function trendAxisCaption(scale: TrendAxisScale, currency: string): string {
  const unit = currency === 'USD' ? '$' : sumUnit()
  return scale.unitKey ? `${i18n.t(`analytics.compactUnits.${scale.unitKey}`)}\u00A0${unit}` : unit
}
