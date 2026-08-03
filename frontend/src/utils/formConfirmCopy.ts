export type FormConfirmCurrency = 'UZS' | 'USD'

type BuildDeleteConfirmBodyArgs = {
  comment: string | null | undefined
  categoryLabel: string
  amount: number
  currency: FormConfirmCurrency
}

function formatSheetAmount(amount: number): string {
  const absolute = Math.abs(amount)
  return absolute.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

function currencyWord(currency: FormConfirmCurrency): string {
  return currency === 'USD' ? '$' : 'сум'
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

  return `Запись «${label}» на ${formattedAmount} ${word} удалится из истории и из аналитики. Отменить нельзя.`
}
