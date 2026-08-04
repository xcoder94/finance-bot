import { type ReactNode, useState } from 'react'
import { Button, Cell, Input, Modal, Select, Spinner, Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import { ENTITY_NAME_MAX_LENGTH, validateEntityName } from './entityNameValidation'

export type EditableEntity = {
  id: string
  name: string
}

export type SelectFieldConfig = {
  key: string
  labelKey: string
  options: ReadonlyArray<{ value: string; label: string }>
  defaultValue: string
}

export type EditableEntityListProps<T extends EditableEntity> = {
  items: T[]
  editable: boolean
  addLabelKey: string
  getSubtitle?: (item: T) => string | undefined
  getItemDisplayName?: (item: T) => string
  renderBefore?: (item: T) => ReactNode
  selectFields?: ReadonlyArray<SelectFieldConfig>
  onAdd: (payload: { name: string } & Record<string, string>) => Promise<void>
  onDelete: (id: string) => Promise<void>
}

type AddFormState = {
  name: string
  selectValues: Record<string, string>
}

function buildInitialSelectValues(
  selectFields: ReadonlyArray<SelectFieldConfig> | undefined,
): Record<string, string> {
  if (!selectFields) {
    return {}
  }

  return Object.fromEntries(selectFields.map((field) => [field.key, field.defaultValue]))
}

export function EditableEntityList<T extends EditableEntity>({
  items,
  editable,
  addLabelKey,
  getSubtitle,
  getItemDisplayName,
  renderBefore,
  selectFields,
  onAdd,
  onDelete,
}: EditableEntityListProps<T>) {
  const { t } = useTranslation()

  const [showAddForm, setShowAddForm] = useState(false)
  const [addForm, setAddForm] = useState<AddFormState>(() => ({
    name: '',
    selectValues: buildInitialSelectValues(selectFields),
  }))
  const [nameTouched, setNameTouched] = useState(false)
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState(false)

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(false)

  const nameValidationError = validateEntityName(addForm.name)
  const nameErrorKey =
    nameValidationError === 'required'
      ? 'settings.nameRequired'
      : nameValidationError === 'tooLong'
        ? 'settings.nameTooLong30'
        : null

  const resetAddForm = () => {
    setAddForm({
      name: '',
      selectValues: buildInitialSelectValues(selectFields),
    })
    setNameTouched(false)
    setAddError(false)
  }

  const closeAddForm = () => {
    setShowAddForm(false)
    resetAddForm()
  }

  const handleOpenAddForm = () => {
    resetAddForm()
    setShowAddForm(true)
  }

  const handleSubmitAdd = async () => {
    setNameTouched(true)

    if (nameValidationError) {
      return
    }

    setAdding(true)
    setAddError(false)

    try {
      await onAdd({
        name: addForm.name.trim(),
        ...addForm.selectValues,
      })
      closeAddForm()
    } catch {
      setAddError(true)
    } finally {
      setAdding(false)
    }
  }

  const handleConfirmDelete = async () => {
    if (!confirmDeleteId) {
      return
    }

    setDeleting(true)
    setDeleteError(false)

    try {
      await onDelete(confirmDeleteId)
      setConfirmDeleteId(null)
    } catch {
      setDeleteError(true)
    } finally {
      setDeleting(false)
    }
  }

  const confirmDeleteOpen = confirmDeleteId !== null

  return (
    <>
      {items.map((item) => (
        <Cell
          key={item.id}
          before={renderBefore?.(item)}
          subtitle={getSubtitle?.(item)}
        >
          <div className="settings-entity-row">
            <Text className="settings-entity-row__name">
              {getItemDisplayName ? getItemDisplayName(item) : item.name}
            </Text>
            {editable ? (
              <Button
                mode="plain"
                size="s"
                className="settings-entity-row__delete"
                onClick={() => {
                  setDeleteError(false)
                  setConfirmDeleteId(item.id)
                }}
              >
                {t('settings.delete')}
              </Button>
            ) : null}
          </div>
        </Cell>
      ))}

      {editable ? (
        showAddForm ? (
          <div className="settings-entity-list__add-form">
            <Input
              header={t('settings.nameLabel')}
              value={addForm.name}
              maxLength={ENTITY_NAME_MAX_LENGTH + 10}
              status={nameTouched && nameErrorKey ? 'error' : 'default'}
              onBlur={() => setNameTouched(true)}
              onChange={(event) => {
                setAddForm((current) => ({ ...current, name: event.target.value }))
                setAddError(false)
              }}
            />
            {nameTouched && nameErrorKey ? (
              <Text className="settings-entity-list__field-error" role="alert">
                {t(nameErrorKey)}
              </Text>
            ) : null}

            {selectFields?.map((field) => (
              <Select
                key={field.key}
                header={t(field.labelKey)}
                value={addForm.selectValues[field.key] ?? field.defaultValue}
                onChange={(event) => {
                  setAddForm((current) => ({
                    ...current,
                    selectValues: {
                      ...current.selectValues,
                      [field.key]: event.target.value,
                    },
                  }))
                }}
              >
                {field.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            ))}

            {addError ? (
              <div className="home-block-error" role="alert">
                <Text>{t('settings.submitError')}</Text>
              </div>
            ) : null}

            <div className="settings-entity-list__actions">
              <Button
                mode="gray"
                size="m"
                stretched
                disabled={adding}
                onClick={closeAddForm}
              >
                {t('addTransaction.cancel')}
              </Button>
              <Button
                mode="filled"
                size="m"
                stretched
                loading={adding}
                disabled={adding || nameValidationError !== null}
                onClick={() => void handleSubmitAdd()}
              >
                {t(addLabelKey)}
              </Button>
            </div>
          </div>
        ) : (
          <Cell>
            <Button mode="plain" size="m" onClick={handleOpenAddForm}>
              + {t(addLabelKey)}
            </Button>
          </Cell>
        )
      ) : null}

      <Modal
        open={confirmDeleteOpen}
        onOpenChange={(nextOpen) => {
          if (!nextOpen && !deleting) {
            setConfirmDeleteId(null)
            setDeleteError(false)
          }
        }}
      >
        <Modal.Header>{t('settings.delete')}</Modal.Header>
        <div className="settings-entity-list__confirm-delete">
          <Text>{t('settings.confirmDelete')}</Text>
          {deleteError ? (
            <div className="home-block-error" role="alert">
              <Text>{t('settings.submitError')}</Text>
              <Button mode="plain" size="s" onClick={() => void handleConfirmDelete()}>
                {t('auth.retry')}
              </Button>
            </div>
          ) : null}
          <div className="settings-entity-list__actions">
            <Button
              mode="gray"
              size="l"
              stretched
              disabled={deleting}
              onClick={() => {
                setConfirmDeleteId(null)
                setDeleteError(false)
              }}
            >
              {t('addTransaction.cancel')}
            </Button>
            <Button
              mode="gray"
              size="l"
              stretched
              loading={deleting}
              className="settings-entity-list__delete-button"
              onClick={() => void handleConfirmDelete()}
            >
              {t('settings.delete')}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  )
}

export function SettingsSectionLoading() {
  const { t } = useTranslation()

  return (
    <Cell>
      <div className="settings-section-loading" role="status" aria-live="polite">
        <Spinner size="m" aria-hidden="true" />
        <span className="visually-hidden">{t('home.loading')}</span>
      </div>
    </Cell>
  )
}

export function SettingsSectionLoadError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()

  return (
    <Cell>
      <div className="home-block-error" role="alert">
        <Text>{t('settings.loadError')}</Text>
        <Button mode="plain" size="s" onClick={onRetry}>
          {t('auth.retry')}
        </Button>
      </div>
    </Cell>
  )
}