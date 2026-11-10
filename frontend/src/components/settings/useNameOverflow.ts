import { type ClipboardEvent, useCallback, useState } from 'react'

import { ENTITY_NAME_MAX_LENGTH, pasteOverflows } from './entityNameValidation'

/** Tracks "pasted text was cut at 30 chars" for a name input (maxLength does the cutting). */
export function useNameOverflow() {
  const [overflow, setOverflow] = useState(false)

  const onPaste = useCallback((event: ClipboardEvent<HTMLInputElement>) => {
    const input = event.currentTarget
    const pasted = event.clipboardData.getData('text')
    if (
      pasteOverflows(input.value, input.selectionStart ?? 0, input.selectionEnd ?? 0, pasted)
    ) {
      setOverflow(true)
    }
  }, [])

  const onValueChange = useCallback((value: string) => {
    if (value.length < ENTITY_NAME_MAX_LENGTH) {
      setOverflow(false)
    }
  }, [])

  const reset = useCallback(() => setOverflow(false), [])

  return { overflow, onPaste, onValueChange, reset }
}
