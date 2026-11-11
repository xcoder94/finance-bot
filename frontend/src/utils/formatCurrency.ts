import i18n from '../i18n'
import { sumUnit } from './currencyUnit'
import { groupThousands } from './groupThousands'

export type Currency = 'UZS' | 'USD'

export function formatCurrency(amount: number, currency: Currency): string {
  const sign = amount < 0 ? '-' : ''
  const absolute = Math.abs(amount)
  const formatted = groupThousands(absolute)

  if (currency === 'USD') {
    return `${sign}$${formatted}`
  }

  // NBSP before the unit: amount + currency is one unbreakable unit (B5)
  return `${sign}${formatted}\u00a0${sumUnit()}`
}

export function formatUsdTrendAxisAmount(value: number): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return String(value)
  }

  const sign = numeric < 0 ? '-' : ''
  const absolute = Math.abs(numeric)
  const isUzbek = i18n.resolvedLanguage?.startsWith('uz') ?? i18n.language.startsWith('uz')
  const locale = isUzbek ? 'uz-Latn-UZ' : 'ru-RU'
  return `${sign}$${absolute.toLocaleString(locale)}`
}

export function formatCompactAxisAmount(value: number): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return String(value)
  }

  const sign = numeric < 0 ? '-' : ''
  const absolute = Math.abs(numeric)
  const isUzbek = i18n.resolvedLanguage?.startsWith('uz') ?? i18n.language.startsWith('uz')
  const locale = isUzbek ? 'uz-Latn-UZ' : 'ru-RU'

  const formatScaled = (scaled: number, suffix: string): string => {
    const formatted = scaled.toLocaleString(locale, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 1,
    })
    return `${sign}${formatted}\u00A0${suffix}`
  }

  if (absolute >= 1_000_000_000) {
    return formatScaled(
      absolute / 1_000_000_000,
      i18n.t('analytics.compactUnits.billion'),
    )
  }

  if (absolute >= 1_000_000) {
    return formatScaled(
      absolute / 1_000_000,
      i18n.t('analytics.compactUnits.million'),
    )
  }

  if (absolute >= 1000) {
    return formatScaled(
      absolute / 1000,
      i18n.t('analytics.compactUnits.thousand'),
    )
  }

  return `${sign}${absolute.toLocaleString(locale)}`
}
