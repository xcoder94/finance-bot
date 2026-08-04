type SettingsToggleRowProps = {
  name: string
  subtitle?: string
  enabled: boolean
  onToggle: () => void
}

export function SettingsToggleRow({ name, subtitle, enabled, onToggle }: SettingsToggleRowProps) {
  return (
    <button
      type="button"
      className="settings-toggle-row"
      role="switch"
      aria-checked={enabled}
      onClick={onToggle}
    >
      <span className="settings-toggle-row__text">
        <span className="settings-toggle-row__name">{name}</span>
        {subtitle ? <span className="settings-toggle-row__subtitle">{subtitle}</span> : null}
      </span>
      <span
        className={[
          'settings-toggle-row__track',
          enabled ? 'settings-toggle-row__track--on' : 'settings-toggle-row__track--off',
        ].join(' ')}
        aria-hidden="true"
      >
        <span className="settings-toggle-row__knob" />
      </span>
    </button>
  )
}
