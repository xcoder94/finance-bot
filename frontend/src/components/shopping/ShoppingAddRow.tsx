import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { AddResult } from '../../store/shoppingStore'
import { clipShoppingName } from '../../utils/shoppingText'

type ShoppingAddRowProps = {
  onAdd: (name: string) => Promise<AddResult>
}

export function ShoppingAddRow({ onAdd }: ShoppingAddRowProps) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const [hint, setHint] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (busy) {
      return
    }
    setBusy(true)
    setHint(null)
    try {
      const result = await onAdd(value)
      if (result === 'added') {
        setValue('')
      } else if (result === 'duplicate') {
        setHint(t('shopping.duplicate'))
      } else if (result === 'limit') {
        setHint(t('shopping.limit'))
      } else if (result === 'invalid') {
        setHint(t('shopping.nameRequired'))
      } else {
        setHint(t('settings.submitError'))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      className="shopping-add"
      onSubmit={(event) => {
        event.preventDefault()
        void submit()
      }}
    >
      <div className="shopping-add__field">
        <input
          className="shopping-add__input"
          type="text"
          enterKeyHint="done"
          autoComplete="off"
          placeholder={t('shopping.addPlaceholder')}
          aria-label={t('shopping.addPlaceholder')}
          value={value}
          onChange={(event) => {
            setValue(clipShoppingName(event.target.value))
            setHint(null)
          }}
        />
        {value.trim().length > 0 ? (
          <button type="submit" className="shopping-add__submit" disabled={busy}>
            {t('shopping.addButton')}
          </button>
        ) : null}
      </div>
      {hint ? (
        <div className="shopping-add__hint" role="alert">
          {hint}
        </div>
      ) : null}
    </form>
  )
}
