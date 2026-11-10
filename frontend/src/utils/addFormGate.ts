export type AddSubmitVerdict = 'ok' | 'category' | 'invalid'

/** 'category' = everything else is fine but no category was chosen: show the message under the row. */
export function evaluateAddSubmit(input: {
  parsedAmount: number | null
  walletId: string
  categoryId: string
  amountOverLimit: boolean
}): AddSubmitVerdict {
  if (!input.parsedAmount || !input.walletId || input.amountOverLimit) {
    return 'invalid'
  }
  return input.categoryId ? 'ok' : 'category'
}
