import { type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Spinner } from '@telegram-apps/telegram-ui'

import { useExitTransition } from '../../hooks/useExitTransition'
import { useVisualViewport } from '../../hooks/useVisualViewport'

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
  cancelLabel,
  primaryLabel,
  onPrimary,
  primaryDisabled = false,
  primaryLoading = false,
  danger,
}: FormSheetProps) {
  const { t } = useTranslation()
  const [mounted, closing] = useExitTransition(open)
  const viewport = useVisualViewport(mounted)
  if (!mounted) {
    return null
  }

  return (
    <div
      className={`form-sheet-backdrop${closing ? ' form-sheet-backdrop--closing' : ''}`}
      style={
        viewport
          ? { top: viewport.offsetTop, bottom: 'auto', height: viewport.height }
          : undefined
      }
      onClick={closing ? undefined : onClose}
    >
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
            aria-label={t('common.close')}
          >
            ✕
          </button>
        </header>

        {intro ? <p className="form-sheet-intro">{intro}</p> : null}

        {children ? <div className="form-sheet-fields">{children}</div> : null}

        {changes}

        {danger ? <div className="form-sheet-danger">{danger}</div> : null}

        {showPrimary ? (
          <div className="form-sheet-actions">
            <button type="button" className="form-sheet-cancel" onClick={onClose}>
              {cancelLabel ?? t('formSheet.cancel')}
            </button>
            <button
              type="button"
              className="form-sheet-primary"
              onClick={onPrimary}
              disabled={primaryDisabled || primaryLoading}
            >
              {primaryLoading ? (
                <>
                  <Spinner size="s" aria-hidden="true" />
                  <span className="visually-hidden">{t('home.loading')}</span>
                </>
              ) : (
                primaryLabel ?? t('formSheet.save')
              )}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
