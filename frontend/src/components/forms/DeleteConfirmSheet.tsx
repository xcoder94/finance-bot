import { useTranslation } from 'react-i18next'

import { buildDeleteConfirmBody, type FormConfirmCurrency } from '../../utils/formConfirmCopy'
import { FormSheet } from './FormSheet'

type DeleteConfirmSheetProps = {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  comment?: string | null
  categoryLabel: string
  amount: number
  currency: FormConfirmCurrency
  confirming?: boolean
  error?: boolean
}

export function DeleteConfirmSheet({
  open,
  onClose,
  onConfirm,
  comment,
  categoryLabel,
  amount,
  currency,
  confirming = false,
  error = false,
}: DeleteConfirmSheetProps) {
  const { t } = useTranslation()
  const intro = buildDeleteConfirmBody({
    comment,
    categoryLabel,
    amount,
    currency,
  })

  return (
    <FormSheet
      open={open}
      title="Удалить запись?"
      intro={intro}
      onClose={onClose}
      showPrimary={false}
      danger={
        <button
          type="button"
          className="form-sheet-danger-button"
          onClick={onConfirm}
          disabled={confirming}
        >
          {confirming ? '…' : 'Удалить запись'}
        </button>
      }
    >
      {error ? (
        <div className="form-sheet-load-error" role="alert">
          <p>{t('history.deleteError')}</p>
          <button type="button" onClick={onConfirm} disabled={confirming}>
            {t('auth.retry')}
          </button>
        </div>
      ) : null}
    </FormSheet>
  )
}
