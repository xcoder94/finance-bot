import { type ReactNode } from 'react'
import { Link } from 'react-router-dom'

type SettingsSubPageShellProps = {
  title: string
  backLabel: string
  backTo: string
  actionLabel?: string
  onAction?: () => void
  children?: ReactNode
}

export function SettingsSubPageShell({
  title,
  backLabel,
  backTo,
  actionLabel,
  onAction,
  children,
}: SettingsSubPageShellProps) {
  return (
    <div className="page-content settings-sub-page">
      <Link to={backTo} className="settings-sub-page__back">
        {backLabel}
      </Link>
      <h1 className="settings-sub-page__title">{title}</h1>
      {children}
      {actionLabel && onAction ? (
        <button type="button" className="settings-sub-page__action" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}
