import { type ReactNode } from 'react'

type FormSheetFieldProps = {
  label: string
  hint?: string
  hintError?: boolean
  right?: ReactNode
  mono?: boolean
  muted?: boolean
  onClick?: () => void
  children?: ReactNode
}

export function FormSheetField({
  label,
  hint,
  hintError = false,
  right,
  mono = false,
  muted = false,
  onClick,
  children,
}: FormSheetFieldProps) {
  const interactive = Boolean(onClick)
  const valueClassName = [
    'form-sheet-field__value',
    mono ? 'form-sheet-field__value--mono' : '',
    muted ? 'form-sheet-field__value--muted' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const body = (
    <>
      <div className="form-sheet-field__label">{label}</div>
      <div
        className={[
          'form-sheet-field__control',
          hintError ? 'form-sheet-field__control--error' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        {children ? (
          <div className={valueClassName}>{children}</div>
        ) : (
          <span className={valueClassName} />
        )}
        {right ? <span className="form-sheet-field__right">{right}</span> : null}
      </div>
      {hint ? (
        <div
          className={[
            'form-sheet-field__hint',
            hintError ? 'form-sheet-field__hint--error' : '',
          ]
            .filter(Boolean)
            .join(' ')}
        >
          {hint}
        </div>
      ) : null}
    </>
  )

  if (interactive) {
    return (
      <button type="button" className="form-sheet-field form-sheet-field--button" onClick={onClick}>
        {body}
      </button>
    )
  }

  return <div className="form-sheet-field">{body}</div>
}
