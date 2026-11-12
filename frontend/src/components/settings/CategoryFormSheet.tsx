import { ownerFormErrorKey } from '../../api/familyChanged'
import { revealMessage } from '../../utils/revealMessage'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { t as translate } from '../../i18n/t'
import { ENTITY_NAME_MAX } from '../../constants/entityLimits'
import { clampEntityName } from './entityNameValidation'
import { useNameOverflow } from './useNameOverflow'
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
  onDelete?: () => void
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
    return translate('settings.categoryForm.newIncome')
  }
  if (kind === 'expense-parent') {
    return translate('settings.categoryForm.newExpense')
  }
  return translate('settings.categoryForm.newSub')
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
  onDelete,
}: CategoryFormSheetProps) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [nameTouched, setNameTouched] = useState(false)
  const nameOverflow = useNameOverflow()
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      return
    }
    setName(category?.name ?? '')
    nameOverflow.reset()
    setNameTouched(false)
    setSaving(false)
    setSaveError(null)
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
      : nameOverflow.overflow
        ? t('settings.nameTooLong30')
        : nameTouched && nameErrorKey
          ? t(nameErrorKey)
          : undefined
  const fieldHintError =
    (atLimit && Boolean(limitMessage)) ||
    nameOverflow.overflow ||
    (nameTouched && nameErrorKey !== null)

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
      ? t('settings.categoryForm.parentFixed', { parent: parentName })
      : undefined

  const handleSave = async () => {
    setNameTouched(true)
    if (!canSave || nameValidation) {
      return
    }

    setSaving(true)
    setSaveError(null)
    try {
      await onSave({ name: name.trim() })
      onClose()
    } catch (error) {
      setSaveError(ownerFormErrorKey(error, 'settings.submitError', 'familyChanged.categoriesOwnerOnly'))
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
      primaryLabel={t('formSheet.save')}
      onPrimary={() => void handleSave()}
      primaryDisabled={!canSave}
      primaryLoading={saving}
      danger={
        mode === 'edit' &&
        onDelete &&
        (kind === 'income' || kind === 'expense-subcategory')
          ? (
            <button
              type="button"
              className="form-sheet-danger-button"
              onClick={onDelete}
            >
              {t('settings.delete')}
            </button>
          )
          : undefined
      }
    >
      <FormSheetField
        label={t('settings.nameLabel30')}
        right={formatNameCounter(trimmedLength)}
        hint={fieldHint}
        hintError={fieldHintError}
      >
        <input
          className="form-sheet-field__input"
          value={name}
          maxLength={ENTITY_NAME_MAX}
          readOnly={!editable}
          onBlur={() => setNameTouched(true)}
          onPaste={nameOverflow.onPaste}
          onChange={(event) => {
            const next = clampEntityName(event.target.value)
            nameOverflow.onValueChange(next)
            setName(next)
            setSaveError(null)
          }}
        />
      </FormSheetField>

      {!editable || saveError ? (
        <div className="form-sheet-load-error" role="alert" ref={revealMessage}>
          <p>{t(editable ? saveError! : 'familyChanged.categoriesOwnerOnly')}</p>
          {editable && saveError === 'settings.submitError' ? (
            <button type="button" onClick={() => void handleSave()} disabled={saving}>
              {t('auth.retry')}
            </button>
          ) : null}
        </div>
      ) : null}
    </FormSheet>
  )
}
