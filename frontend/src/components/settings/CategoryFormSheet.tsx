import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ENTITY_NAME_MAX } from '../../constants/entityLimits'
import { useNativeBackButtonOverlay } from '../nativeBackButtonContext'
import { FormSheet } from '../forms/FormSheet'
import { FormSheetField } from '../forms/FormSheetField'

export type CategoryFormKind = 'income' | 'expense-parent' | 'expense-subcategory'
export type CategoryFormMode = 'create' | 'edit'

type CategoryFormSheetProps = {
  open: boolean
  mode: CategoryFormMode
  kind: CategoryFormKind
  category: { name: string } | null
  displayName?: string
  parentName?: string
  atLimit: boolean
  limitMessage?: string
  editable: boolean
  onClose: () => void
  onSave: (payload: { name: string }) => Promise<void>
}

function validateCategoryName(name: string): 'required' | 'tooLong' | null {
  const trimmed = name.trim()
  if (trimmed.length === 0) {
    return 'required'
  }
  if (trimmed.length > ENTITY_NAME_MAX) {
    return 'tooLong'
  }
  return null
}

function formatNameCounter(length: number): string {
  return `${length} / ${ENTITY_NAME_MAX}`
}

function createTitle(kind: CategoryFormKind): string {
  if (kind === 'income') {
    return 'Новая категория дохода'
  }
  if (kind === 'expense-parent') {
    return 'Новая категория расхода'
  }
  return 'Новая подкатегория'
}

export function CategoryFormSheet({
  open,
  mode,
  kind,
  category,
  displayName,
  parentName,
  atLimit,
  limitMessage,
  editable,
  onClose,
  onSave,
}: CategoryFormSheetProps) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [nameTouched, setNameTouched] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(false)

  useEffect(() => {
    if (!open) {
      return
    }
    setName(category?.name ?? '')
    setNameTouched(false)
    setSaving(false)
    setSaveError(false)
  }, [open, category])

  useNativeBackButtonOverlay(open, onClose)

  const nameValidation = validateCategoryName(name)
  const nameErrorKey =
    nameValidation === 'required'
      ? 'settings.nameRequired'
      : nameValidation === 'tooLong'
        ? 'settings.nameTooLong30'
        : null

  const trimmedLength = name.trim().length
  const fieldHint =
    atLimit && limitMessage
      ? limitMessage
      : nameTouched && nameErrorKey
        ? t(nameErrorKey)
        : undefined
  const fieldHintError = (atLimit && Boolean(limitMessage)) || (nameTouched && nameErrorKey !== null)

  const canSave =
    editable &&
    !atLimit &&
    nameValidation === null &&
    !saving &&
    (mode === 'create' || category !== null)

  const title =
    mode === 'create' ? createTitle(kind) : (displayName ?? category?.name ?? '')

  const intro =
    mode === 'create' && kind === 'expense-subcategory' && parentName
      ? `Родитель задан экраном, откуда пришли: ${parentName}.`
      : undefined

  const handleSave = async () => {
    setNameTouched(true)
    if (!canSave || nameValidation) {
      return
    }

    setSaving(true)
    setSaveError(false)
    try {
      await onSave({ name: name.trim() })
      onClose()
    } catch {
      setSaveError(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <FormSheet
      open={open}
      title={title}
      intro={intro}
      onClose={onClose}
      showPrimary={editable}
      primaryLabel="Сохранить"
      onPrimary={() => void handleSave()}
      primaryDisabled={!canSave}
      primaryLoading={saving}
    >
      <FormSheetField
        label="Название · до 30 знаков"
        right={formatNameCounter(trimmedLength)}
        hint={fieldHint}
        hintError={fieldHintError}
      >
        <input
          className="form-sheet-field__input"
          value={name}
          maxLength={ENTITY_NAME_MAX + 10}
          readOnly={!editable}
          onBlur={() => setNameTouched(true)}
          onChange={(event) => {
            setName(event.target.value)
            setSaveError(false)
          }}
        />
      </FormSheetField>

      {saveError ? (
        <div className="form-sheet-load-error" role="alert">
          <p>{t('settings.submitError')}</p>
          <button type="button" onClick={() => void handleSave()} disabled={saving}>
            {t('auth.retry')}
          </button>
        </div>
      ) : null}
    </FormSheet>
  )
}
