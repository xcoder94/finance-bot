type SettingsRadioRowProps = {
  label: string
  subtitle?: string
  selected: boolean
  onSelect: () => void
}

export function SettingsRadioRow({ label, subtitle, selected, onSelect }: SettingsRadioRowProps) {
  return (
    <button type="button" className="category-picker__row" onClick={onSelect}>
      <span
        className={[
          'category-picker__radio',
          selected ? 'category-picker__radio--selected' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        aria-hidden="true"
      >
        <span className="category-picker__radio-dot" />
      </span>
      <span className="settings-radio-row__text">
        <span className="category-picker__name">{label}</span>
        {subtitle ? <span className="settings-radio-row__subtitle">{subtitle}</span> : null}
      </span>
    </button>
  )
}
