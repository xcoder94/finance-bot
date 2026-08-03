type SettingsStaticRowProps = {
  name: string
  subtitle?: string
}

export function SettingsStaticRow({ name, subtitle }: SettingsStaticRowProps) {
  return (
    <div className="settings-static-row">
      <span className="settings-static-row__text">
        <span className="settings-static-row__name">{name}</span>
        {subtitle ? <span className="settings-static-row__subtitle">{subtitle}</span> : null}
      </span>
    </div>
  )
}
