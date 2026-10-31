import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ShoppingItem } from '../../api/shopping'
import type { RenameResult } from '../../store/shoppingStore'
import { clipShoppingName } from '../../utils/shoppingText'
import { FormSheet } from '../forms/FormSheet'
import { FormSheetField } from '../forms/FormSheetField'
import { useNativeBackButtonOverlay } from '../nativeBackButtonContext'

type ShoppingEditSheetProps = {
  item: ShoppingItem | null
  onClose: () => void
  onSave: (id: string, name: string) => Promise<RenameResult>
}

export function ShoppingEditSheet({ item, onClose, onSave }: ShoppingEditSheetProps) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [hint, setHint] = useState<string | null>(null)
  const open = item !== null

  useEffect(() => {
    setName(item?.name ?? '')
    setHint(null)
    setSaving(false)
  }, [item])

  useNativeBackButtonOverlay(open, onClose)

  const save = async () => {
    if (!item || saving) {
      return
    }
    setSaving(true)
    setHint(null)
    const result = await onSave(item.id, name)
    setSaving(false)
    if (result === 'ok' || result === 'gone') {
      onClose()
    } else if (result === 'duplicate') {
      setHint(t('shopping.duplicate'))
    } else if (result === 'invalid') {
      setHint(t('shopping.nameRequired'))
    } else {
      setHint(t('settings.submitError'))
    }
  }

  return (
    <FormSheet
      open={open}
      title={t('shopping.editTitle')}
      onClose={onClose}
      cancelLabel={t('addTransaction.cancel')}
      primaryLabel={t('shopping.save')}
      onPrimary={() => void save()}
      primaryDisabled={name.trim().length === 0}
      primaryLoading={saving}
    >
      <FormSheetField label={t('shopping.nameLabel')} hint={hint ?? undefined} hintError={hint !== null}>
        <input
          className="form-sheet-field__input"
          value={name}
          autoComplete="off"
          onChange={(event) => {
            setName(clipShoppingName(event.target.value))
            setHint(null)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              void save()
            }
          }}
        />
      </FormSheetField>
    </FormSheet>
  )
}
