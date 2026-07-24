import { useCallback, useEffect, useState } from 'react'
import { Button, Cell, Input, Modal, Section, Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import {
  createExpenseCategory,
  deleteExpenseCategory,
  getExpenseCategories,
  type ExpenseCategoryResponse,
} from '../../api/categories'
import { useAuthStore } from '../../store/authStore'
import {
  getCachedExpenseCategories,
  invalidateExpenseCategoryData,
  peekExpenseCategories,
} from '../../store/dataCacheStore'
import {
  ENTITY_NAME_MAX_LENGTH,
  validateEntityName,
} from './entityNameValidation'
import { SettingsSectionLoadError, SettingsSectionLoading } from './EditableEntityList'
import { getExpenseCategoryIcon } from './expenseCategoryIcon'
import { getDisplayName } from '../../utils/getDisplayName'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; items: ExpenseCategoryResponse[] }

type GroupedExpenseCategory = {
  parent: ExpenseCategoryResponse
  subcategories: ExpenseCategoryResponse[]
}

type AddTarget =
  | { type: 'none' }
  | { type: 'topLevel' }
  | { type: 'subcategory'; parentId: string }

type PendingDelete = {
  id: string
  kind: 'parent' | 'subcategory'
  subcategoryCount: number
}

function groupExpenseCategories(categories: ExpenseCategoryResponse[]): GroupedExpenseCategory[] {
  const topLevel = categories.filter((category) => category.parent_id === null)

  return topLevel.map((parent) => ({
    parent,
    subcategories: categories.filter((category) => category.parent_id === parent.id),
  }))
}

type CategoryNameFormProps = {
  name: string
  nameTouched: boolean
  submitLabelKey: string
  submitting: boolean
  submitError: boolean
  onNameChange: (name: string) => void
  onNameBlur: () => void
  onCancel: () => void
  onSubmit: () => void
}

function CategoryNameForm({
  name,
  nameTouched,
  submitLabelKey,
  submitting,
  submitError,
  onNameChange,
  onNameBlur,
  onCancel,
  onSubmit,
}: CategoryNameFormProps) {
  const { t } = useTranslation()
  const nameValidationError = validateEntityName(name)
  const nameErrorKey =
    nameValidationError === 'required'
      ? 'settings.nameRequired'
      : nameValidationError === 'tooLong'
        ? 'settings.nameTooLong'
        : null

  return (
    <div className="settings-entity-list__add-form">
      <Input
        header={t('settings.nameLabel')}
        value={name}
        maxLength={ENTITY_NAME_MAX_LENGTH + 10}
        status={nameTouched && nameErrorKey ? 'error' : 'default'}
        onBlur={onNameBlur}
        onChange={(event) => onNameChange(event.target.value)}
      />
      {nameTouched && nameErrorKey ? (
        <Text className="settings-entity-list__field-error" role="alert">{t(nameErrorKey)}</Text>
      ) : null}
      {submitError ? (
        <div className="home-block-error" role="alert">
          <Text>{t('settings.submitError')}</Text>
        </div>
      ) : null}
      <div className="settings-entity-list__actions">
        <Button mode="gray" size="m" stretched disabled={submitting} onClick={onCancel}>
          {t('addTransaction.cancel')}
        </Button>
        <Button
          mode="filled"
          size="m"
          stretched
          loading={submitting}
          disabled={submitting || nameValidationError !== null}
          onClick={onSubmit}
        >
          {t(submitLabelKey)}
        </Button>
      </div>
    </div>
  )
}

type CategoryRowProps = {
  category: ExpenseCategoryResponse
  editable: boolean
  nested?: boolean
  onDelete: () => void
}

function CategoryRow({ category, editable, nested = false, onDelete }: CategoryRowProps) {
  const { t } = useTranslation()
  const CategoryIcon = getExpenseCategoryIcon(category.name)

  return (
    <Cell
      className={nested ? 'settings-expense-subcategory' : 'settings-expense-category'}
      before={
        <CategoryIcon
          className={
            nested
              ? 'settings-entity-icon settings-entity-icon--subcategory'
              : 'settings-entity-icon'
          }
          aria-hidden="true"
        />
      }
    >
      <div className="settings-entity-row">
        <Text
          className={
            nested
              ? 'settings-entity-row__name settings-entity-row__name--subcategory'
              : 'settings-entity-row__name'
          }
          weight={nested ? undefined : '2'}
        >
          {getDisplayName(category, t)}
        </Text>
        {editable ? (
          <Button
            mode="plain"
            size="s"
            className="settings-entity-row__delete"
            onClick={onDelete}
          >
            {t('settings.delete')}
          </Button>
        ) : null}
      </div>
    </Cell>
  )
}

export function ExpenseCategoriesSection() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'
  const familyId = user?.familyBudgetId ?? ''

  const [loadState, setLoadState] = useState<LoadState>(() => {
    const cached = peekExpenseCategories(familyId)
    return cached ? { status: 'success', items: cached } : { status: 'loading' }
  })
  const [reloadCount, setReloadCount] = useState(0)

  const [addTarget, setAddTarget] = useState<AddTarget>({ type: 'none' })
  const [addName, setAddName] = useState('')
  const [addNameTouched, setAddNameTouched] = useState(false)
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState(false)

  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(false)

  const loadCategories = useCallback(async () => {
    setLoadState((current) => (current.status === 'success' ? current : { status: 'loading' }))
    try {
      const items = await getCachedExpenseCategories(
        familyId,
        getExpenseCategories,
        reloadCount > 0,
      )
      setLoadState({ status: 'success', items })
    } catch {
      setLoadState((current) => (current.status === 'success' ? current : { status: 'error' }))
    }
  }, [familyId, reloadCount])

  useEffect(() => {
    void loadCategories()
  }, [loadCategories, reloadCount])

  const resetAddForm = () => {
    setAddTarget({ type: 'none' })
    setAddName('')
    setAddNameTouched(false)
    setAddError(false)
  }

  const openAddTopLevel = () => {
    setAddName('')
    setAddNameTouched(false)
    setAddError(false)
    setAddTarget({ type: 'topLevel' })
  }

  const openAddSubcategory = (parentId: string) => {
    setAddName('')
    setAddNameTouched(false)
    setAddError(false)
    setAddTarget({ type: 'subcategory', parentId })
  }

  const handleSubmitAdd = async () => {
    setAddNameTouched(true)

    if (validateEntityName(addName)) {
      return
    }

    setAdding(true)
    setAddError(false)

    try {
      if (addTarget.type === 'topLevel') {
        await createExpenseCategory({ name: addName.trim() })
      } else if (addTarget.type === 'subcategory') {
        await createExpenseCategory({
          name: addName.trim(),
          parent_id: addTarget.parentId,
        })
      } else {
        return
      }

      resetAddForm()
      invalidateExpenseCategoryData(familyId)
      setReloadCount((count) => count + 1)
    } catch {
      setAddError(true)
    } finally {
      setAdding(false)
    }
  }

  const handleConfirmDelete = async () => {
    if (!pendingDelete) {
      return
    }

    setDeleting(true)
    setDeleteError(false)

    try {
      await deleteExpenseCategory(pendingDelete.id)
      setPendingDelete(null)
      invalidateExpenseCategoryData(familyId)
      setReloadCount((count) => count + 1)
    } catch {
      setDeleteError(true)
    } finally {
      setDeleting(false)
    }
  }

  const groupedCategories =
    loadState.status === 'success' ? groupExpenseCategories(loadState.items) : []

  const deleteConfirmText =
    pendingDelete?.kind === 'parent' && pendingDelete.subcategoryCount > 0
      ? t('settings.confirmDeleteParentWithSubcategories', {
          count: pendingDelete.subcategoryCount,
        })
      : t('settings.confirmDelete')

  return (
    <Section header={t('settings.categoriesExpense')}>
      {loadState.status === 'loading' ? <SettingsSectionLoading /> : null}
      {loadState.status === 'error' ? (
        <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
      ) : null}

      {loadState.status === 'success' ? (
        <>
          {groupedCategories.map((group) => (
            <div key={group.parent.id} className="settings-expense-group">
              <CategoryRow
                category={group.parent}
                editable={isOwner}
                onDelete={() => {
                  setDeleteError(false)
                  setPendingDelete({
                    id: group.parent.id,
                    kind: 'parent',
                    subcategoryCount: group.subcategories.length,
                  })
                }}
              />

              {group.subcategories.map((subcategory) => (
                <CategoryRow
                  key={subcategory.id}
                  category={subcategory}
                  editable={isOwner}
                  nested
                  onDelete={() => {
                    setDeleteError(false)
                    setPendingDelete({
                      id: subcategory.id,
                      kind: 'subcategory',
                      subcategoryCount: 0,
                    })
                  }}
                />
              ))}

              {isOwner ? (
                addTarget.type === 'subcategory' && addTarget.parentId === group.parent.id ? (
                  <CategoryNameForm
                    name={addName}
                    nameTouched={addNameTouched}
                    submitLabelKey="settings.addSubcategory"
                    submitting={adding}
                    submitError={addError}
                    onNameChange={(name) => {
                      setAddName(name)
                      setAddError(false)
                    }}
                    onNameBlur={() => setAddNameTouched(true)}
                    onCancel={resetAddForm}
                    onSubmit={() => void handleSubmitAdd()}
                  />
                ) : (
                  <Cell className="settings-expense-subcategory">
                    <Button
                      mode="plain"
                      size="m"
                      onClick={() => openAddSubcategory(group.parent.id)}
                    >
                      + {t('settings.addSubcategory')}
                    </Button>
                  </Cell>
                )
              ) : null}
            </div>
          ))}

          {isOwner ? (
            addTarget.type === 'topLevel' ? (
              <CategoryNameForm
                name={addName}
                nameTouched={addNameTouched}
                submitLabelKey="settings.addCategory"
                submitting={adding}
                submitError={addError}
                onNameChange={(name) => {
                  setAddName(name)
                  setAddError(false)
                }}
                onNameBlur={() => setAddNameTouched(true)}
                onCancel={resetAddForm}
                onSubmit={() => void handleSubmitAdd()}
              />
            ) : (
              <Cell>
                <Button mode="plain" size="m" onClick={openAddTopLevel}>
                  + {t('settings.addCategory')}
                </Button>
              </Cell>
            )
          ) : null}
        </>
      ) : null}

      <Modal
        open={pendingDelete !== null}
        onOpenChange={(nextOpen) => {
          if (!nextOpen && !deleting) {
            setPendingDelete(null)
            setDeleteError(false)
          }
        }}
      >
        <Modal.Header>{t('settings.delete')}</Modal.Header>
        <div className="settings-entity-list__confirm-delete">
          <Text>{deleteConfirmText}</Text>
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
                setPendingDelete(null)
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
    </Section>
  )
}
