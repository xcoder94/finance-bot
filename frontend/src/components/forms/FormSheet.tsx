import { type ReactNode } from 'react'

type FormSheetProps = {
  open: boolean
  title: string
  intro?: string
  onClose: () => void
  children?: ReactNode
  changes?: ReactNode
  showPrimary?: boolean
  cancelLabel?: string
  primaryLabel?: string
  onPrimary?: () => void
  primaryDisabled?: boolean
  primaryLoading?: boolean
  danger?: ReactNode
}

export function FormSheet({
  open,
  title,
  intro,
  onClose,
  children,
  changes,
  showPrimary = true,
  cancelLabel = 'Отмена',
  primaryLabel = 'Сохранить',
  onPrimary,
  primaryDisabled = false,
  primaryLoading = false,
  danger,
}: FormSheetProps) {
  if (!open) {
    return null
  }

  return (
    <div className="form-sheet-backdrop" onClick={onClose}>
      <div
        className="form-sheet-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="form-sheet-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="form-sheet-header">
          <h2 id="form-sheet-title" className="form-sheet-title">
            {title}
          </h2>
          <button
            type="button"
            className="form-sheet-close"
            onClick={onClose}
            aria-label="Закрыть"
          >
            ✕
          </button>
        </header>

        {intro ? <p className="form-sheet-intro">{intro}</p> : null}

        {children ? <div className="form-sheet-fields">{children}</div> : null}

        {changes}

        {showPrimary ? (
          <div className="form-sheet-actions">
            <button type="button" className="form-sheet-cancel" onClick={onClose}>
              {cancelLabel}
            </button>
            <button
              type="button"
              className="form-sheet-primary"
              onClick={onPrimary}
              disabled={primaryDisabled || primaryLoading}
            >
              {primaryLoading ? '…' : primaryLabel}
            </button>
          </div>
        ) : null}

        {danger ? <div className="form-sheet-danger">{danger}</div> : null}
      </div>
    </div>
  )
}
