import { Link } from 'react-router-dom'

type SettingsSubPageShellProps = {
  title: string
  backLabel: string
  backTo: string
}

export function SettingsSubPageShell({ title, backLabel, backTo }: SettingsSubPageShellProps) {
  return (
    <div className="page-content settings-sub-page">
      <Link to={backTo} className="settings-sub-page__back">
        {backLabel}
      </Link>
      <h1 className="settings-sub-page__title">{title}</h1>
    </div>
  )
}
