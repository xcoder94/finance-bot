import { useTranslation } from 'react-i18next'

import { MEMBER_CONFIRM_CANCEL } from '../../utils/memberConfirmCopy'
import { FormSheet } from '../forms/FormSheet'

type MemberConfirmSheetProps = {
  open: boolean
  intro: string
  confirmLabel: string
  onClose: () => void
  onConfirm: () => void
  confirming?: boolean
  error?: boolean
}

export function MemberConfirmSheet({
  open,
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
      title=""
      intro={intro}
      onClose={onClose}
      showPrimary={false}
      danger={
        <>
          <button
            type="button"
            className="form-sheet-cancel"
            onClick={onClose}
            disabled={confirming}
          >
            {MEMBER_CONFIRM_CANCEL}
          </button>
          <button
            type="button"
            className="form-sheet-danger-button"
            onClick={onConfirm}
            disabled={confirming}
          >
            {confirming ? '…' : confirmLabel}
          </button>
        </>
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
