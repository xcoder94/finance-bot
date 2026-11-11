import { type ReactNode, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { clampPickedDate, isValidIsoDate } from '../utils/dateChips'

type NativeDatePickerProps = {
  value: string
  onChange: (value: string) => void
  max: string
  min?: string
  /**
   * Receives `open` (shows the system calendar; a visible input when `showPicker` is missing)
   * and `close` (hides that visible fallback input again).
   */
  children: (open: () => void, close: () => void) => ReactNode
}

export function NativeDatePicker({ value, onChange, max, min, children }: NativeDatePickerProps) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const [fallbackVisible, setFallbackVisible] = useState(false)
  const [seenValue, setSeenValue] = useState(value)

  // The value changed from outside (a chip or a preset): the fallback input has done its job.
  if (seenValue !== value) {
    setSeenValue(value)
    if (fallbackVisible) {
      setFallbackVisible(false)
    }
  }

  const close = () => setFallbackVisible(false)

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
      {children(open, close)}
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
          const picked = clampPickedDate(event.target.value, max, min)
          if (picked) {
            onChange(picked)
            setFallbackVisible(false)
          }
        }}
      />
    </>
  )
}
