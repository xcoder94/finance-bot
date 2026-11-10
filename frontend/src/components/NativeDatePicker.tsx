import { type ReactNode, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { isValidIsoDate } from '../utils/dateChips'

type NativeDatePickerProps = {
  value: string
  onChange: (value: string) => void
  max: string
  min?: string
  /** Receives `open`, which shows the system calendar (visible input when `showPicker` is missing). */
  children: (open: () => void) => ReactNode
}

export function NativeDatePicker({ value, onChange, max, min, children }: NativeDatePickerProps) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const [fallbackVisible, setFallbackVisible] = useState(false)

  const open = () => {
    const input = inputRef.current
    if (!input) {
      return
    }
    if (typeof input.showPicker === 'function') {
      try {
        input.showPicker()
        return
      } catch {
        // falls through to the visible input
      }
    }
    setFallbackVisible(true)
    input.focus()
  }

  return (
    <>
      {children(open)}
      <input
        ref={inputRef}
        type="date"
        className={fallbackVisible ? 'date-chips__native date-chips__native--visible' : 'date-chips__native'}
        value={isValidIsoDate(value) ? value : ''}
        max={max}
        min={min}
        tabIndex={fallbackVisible ? 0 : -1}
        aria-label={t('dateChips.pickDate')}
        onChange={(event) => {
          const next = event.target.value
          if (isValidIsoDate(next) && next <= max && (!min || next >= min)) {
            onChange(next)
            setFallbackVisible(false)
          }
        }}
      />
    </>
  )
}
