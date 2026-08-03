import {
  buildEntityDeleteTitle,
  buildWalletDeleteIntro,
  WALLET_DELETE_DANGER_LABEL,
} from '../../utils/entityDeleteConfirmCopy'
import { FormSheet } from '../forms/FormSheet'

type EntityDeleteConfirmSheetProps = {
  open: boolean
  entityName: string
  transactionCount: number
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
  onClose,
  onConfirm,
  confirming = false,
  error = false,
  retryLabel = 'Попробовать снова',
  errorMessage = 'Не удалось сохранить изменения',
}: EntityDeleteConfirmSheetProps) {
  const title = buildEntityDeleteTitle(entityName)
  const intro = buildWalletDeleteIntro(transactionCount)

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
          {confirming ? '…' : WALLET_DELETE_DANGER_LABEL}
        </button>
      }
    >
      {error ? (
        <div className="form-sheet-load-error" role="alert">
          <p>{errorMessage}</p>
          <button type="button" onClick={onConfirm} disabled={confirming}>
            {retryLabel}
          </button>
        </div>
      ) : null}
    </FormSheet>
  )
}
