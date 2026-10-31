import { t } from '../i18n/t'
import { sumUnit } from './currencyUnit'
import { groupThousands } from './groupThousands'
export type FormConfirmCurrency = 'UZS' | 'USD'

type BuildDeleteConfirmBodyArgs = {
  comment: string | null | undefined
  categoryLabel: string
  amount: number
  currency: FormConfirmCurrency
}

function formatSheetAmount(amount: number): string {
  const absolute = Math.abs(amount)
  return groupThousands(absolute)
}

function currencyWord(currency: FormConfirmCurrency): string {
  return currency === 'USD' ? '$' : sumUnit()
}

function resolveDeleteLabel(
  comment: string | null | undefined,
  categoryLabel: string,
): string {
  const trimmed = comment?.trim()
  return trimmed ? trimmed : categoryLabel
}

export function buildDeleteConfirmBody({
  comment,
  categoryLabel,
  amount,
  currency,
}: BuildDeleteConfirmBodyArgs): string {
  const label = resolveDeleteLabel(comment, categoryLabel)
  const formattedAmount = formatSheetAmount(amount)
  const word = currencyWord(currency)

  return t('formSheet.deleteBody', { label, amount: formattedAmount, unit: word })
}
