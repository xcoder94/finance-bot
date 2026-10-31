import { useTranslation } from 'react-i18next'
import {
  buildEntityDeleteTitle,
  buildWalletDeleteIntro,
  walletDeleteDangerLabel,
} from '../../utils/entityDeleteConfirmCopy'
import { FormSheet } from '../forms/FormSheet'

type EntityDeleteConfirmSheetProps = {
  open: boolean
  entityName: string
  transactionCount: number
  intro?: string
  dangerLabel?: string
  onClose: () => void
  onConfirm: () => void
  confirming?: boolean
  error?: boolean
  retryLabel?: string
  errorMessage?: string
}

export function EntityDeleteConfirmSheet({
  open,
  entityName,
  transactionCount,
  intro,
  dangerLabel,
  onClose,
  onConfirm,
  confirming = false,
  error = false,
  retryLabel,
  errorMessage,
}: EntityDeleteConfirmSheetProps) {
  const { t } = useTranslation()
  const title = buildEntityDeleteTitle(entityName)
  const resolvedIntro = intro ?? buildWalletDeleteIntro(transactionCount)

  return (
    <FormSheet
      open={open}
      title={title}
      intro={resolvedIntro}
      onClose={onClose}
      showPrimary={false}
      danger={
        <button
          type="button"
          className="form-sheet-danger-button"
          onClick={onConfirm}
          disabled={confirming}
        >
          {confirming ? '…' : (dangerLabel ?? walletDeleteDangerLabel())}
        </button>
      }
    >
      {error ? (
        <div className="form-sheet-load-error" role="alert">
          <p>{errorMessage ?? t('settings.submitError')}</p>
          <button type="button" onClick={onConfirm} disabled={confirming}>
            {retryLabel ?? t('auth.retry')}
          </button>
        </div>
      ) : null}
    </FormSheet>
  )
}
