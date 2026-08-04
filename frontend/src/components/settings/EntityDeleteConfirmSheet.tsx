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
  dangerLabel = WALLET_DELETE_DANGER_LABEL,
  onClose,
  onConfirm,
  confirming = false,
  error = false,
  retryLabel = 'Попробовать снова',
  errorMessage = 'Не удалось сохранить изменения',
}: EntityDeleteConfirmSheetProps) {
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
          {confirming ? '…' : dangerLabel}
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
