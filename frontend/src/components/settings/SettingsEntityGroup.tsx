import { type ReactNode } from 'react'

type SettingsEntityGroupProps = {
  title: string
  note?: string
  children: ReactNode
}

export function SettingsEntityGroup({ title, note, children }: SettingsEntityGroupProps) {
  return (
    <div className="settings-entity-group">
      <div className="settings-entity-group__title">{title}</div>
      <div className="settings-entity-group__list">{children}</div>
      {note ? <div className="settings-entity-group__note">{note}</div> : null}
    </div>
  )
}
