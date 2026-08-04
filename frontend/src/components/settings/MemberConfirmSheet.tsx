import { useTranslation } from 'react-i18next'

import { FormSheet } from '../forms/FormSheet'

type MemberConfirmSheetProps = {
  open: boolean
  title: string
  intro: string
  confirmLabel: string
  onClose: () => void
  onConfirm: () => void
  confirming?: boolean
  error?: boolean
}

export function MemberConfirmSheet({
  open,
  title,
  intro,
  confirmLabel,
  onClose,
  onConfirm,
  confirming = false,
  error = false,
}: MemberConfirmSheetProps) {
  const { t } = useTranslation()

  return (
    <FormSheet
      open={open}
      title={title}
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
          {confirming ? '…' : confirmLabel}
        </button>
      }
    >
      {error ? (
        <div className="form-sheet-load-error" role="alert">
          <p>{t('settings.submitError')}</p>
          <button type="button" onClick={onConfirm} disabled={confirming}>
            {t('auth.retry')}
          </button>
        </div>
      ) : null}
    </FormSheet>
  )
}
