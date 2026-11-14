import { saveErrorKey } from '../../api/familyChanged'
import { FormNotice } from '../FormNotice'
import { noticeKindForKey } from '../../utils/noticeKind'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { WalletResponse } from '../../api/wallets'
import { ENTITY_NAME_MAX } from '../../constants/entityLimits'
import { clampEntityName } from './entityNameValidation'
import { useNameOverflow } from './useNameOverflow'
import { useNativeBackButtonOverlay } from '../nativeBackButtonContext'
import { FormSheet } from '../forms/FormSheet'
import { FormSheetField } from '../forms/FormSheetField'
import {
  type WalletFormType,
  walletCreateAtLimit,
  walletCreateIsPersonal,
  walletCreateLimitHint,
} from './walletFormLimits'

export type WalletFormMode = 'create' | 'edit'

type WalletFormSheetProps = {
  open: boolean
  mode: WalletFormMode
  wallet: WalletResponse | null
  displayName?: string
  sharedWalletCount: number
  personalWalletCount: number
  canPickWalletType: boolean
  editable: boolean
  onClose: () => void
  onSave: (payload: {
    name: string
    currency: 'UZS' | 'USD'
    is_personal: boolean
  }) => Promise<void>
  walletTypePickerOpen: boolean
  onWalletTypePickerOpenChange: (open: boolean) => void
  onDelete?: () => void
}

function validateWalletName(name: string): 'required' | 'tooLong' | null {
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

export function WalletFormSheet({
  open,
  mode,
  wallet,
  displayName,
  sharedWalletCount,
  personalWalletCount,
  canPickWalletType,
  editable,
  onClose,
  onSave,
  walletTypePickerOpen,
  onWalletTypePickerOpenChange,
  onDelete,
}: WalletFormSheetProps) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [walletType, setWalletType] = useState<WalletFormType>('shared')
  const [nameTouched, setNameTouched] = useState(false)
  const nameOverflow = useNameOverflow()
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // New wallets are always UZS; an existing wallet keeps its own currency.
  const currency: 'UZS' | 'USD' =
    mode === 'edit' && wallet?.currency === 'USD' ? 'USD' : 'UZS'
  const currencyLocked = mode === 'edit' && wallet !== null && wallet.transaction_count > 0
  const createWalletType: WalletFormType = canPickWalletType ? walletType : 'personal'
  const atLimit =
    mode === 'create' &&
    walletCreateAtLimit(createWalletType, sharedWalletCount, personalWalletCount)
  const limitHint =
    mode === 'create'
      ? walletCreateLimitHint(createWalletType, sharedWalletCount, personalWalletCount)
      : undefined

  useEffect(() => {
    if (!open) {
      return
    }
    setName(wallet?.name ?? '')
    setWalletType(wallet?.is_personal ? 'personal' : 'shared')
    setNameTouched(false)
    nameOverflow.reset()
    setSaving(false)
    setSaveError(null)
  }, [open, wallet])

  useNativeBackButtonOverlay(
    open && !walletTypePickerOpen,
    onClose,
  )

  const nameValidation = validateWalletName(name)
  const nameErrorKey =
    nameValidation === 'required'
      ? 'settings.nameRequired'
      : nameValidation === 'tooLong'
        ? 'settings.nameTooLong30'
        : null

  const trimmedLength = name.trim().length
  const fieldHint =
    limitHint ??
    (nameOverflow.overflow
      ? t('settings.nameTooLong30')
      : nameTouched && nameErrorKey
        ? t(nameErrorKey)
        : undefined)
  const fieldHintError =
    atLimit || nameOverflow.overflow || (nameTouched && nameErrorKey !== null)

  const canSave =
    editable &&
    !atLimit &&
    nameValidation === null &&
    !saving &&
    (mode === 'create' || wallet !== null)

  const title =
    mode === 'create' ? t('settings.walletForm.newTitle') : (displayName ?? wallet?.name ?? '')

  const intro =
    mode === 'create'
      ? canPickWalletType
        ? t('settings.walletForm.createIntroOwner')
        : t('settings.walletForm.createIntroMember')
      : undefined

  const walletTypeLabel =
    createWalletType === 'personal'
      ? t('settings.walletType.personal')
      : t('settings.walletType.shared')

  const handleSave = async () => {
    setNameTouched(true)
    if (!canSave || nameValidation) {
      return
    }

    setSaving(true)
    setSaveError(null)
    try {
      await onSave({
        name: name.trim(),
        currency,
        is_personal: walletCreateIsPersonal(createWalletType),
      })
      onClose()
    } catch (error) {
      setSaveError(saveErrorKey(error, 'settings.submitError'))
    } finally {
      setSaving(false)
    }
  }

  if (walletTypePickerOpen) {
    return (
      <FormSheet
        open={open}
        title={t('settings.walletForm.typeTitle')}
        onClose={() => onWalletTypePickerOpenChange(false)}
        showPrimary={false}
      >
        <div className="category-picker">
          {(['shared', 'personal'] as const).map((option) => {
            const selected = walletType === option
            const label =
              option === 'shared'
                ? t('settings.walletType.shared')
                : t('settings.walletType.personal')
            return (
              <button
                key={option}
                type="button"
                className="category-picker__row"
                onClick={() => {
                  setWalletType(option)
                  onWalletTypePickerOpenChange(false)
                }}
              >
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
                <span className="category-picker__name">{label}</span>
              </button>
            )
          })}
        </div>
      </FormSheet>
    )
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
        mode === 'edit' && onDelete
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

      {mode === 'edit' && wallet?.currency === 'USD' ? (
        <FormSheetField
          label={t('settings.currencyLabel')}
          hint={currencyLocked ? t('settings.walletForm.currencyLocked') : undefined}
        >
          <span className="form-sheet-field__value wallet-currency-tag">{currency}</span>
        </FormSheetField>
      ) : null}

      {mode === 'create' ? (
        <FormSheetField
          label={t('settings.walletForm.typeTitle')}
          right={canPickWalletType ? '›' : undefined}
          onClick={
            editable && canPickWalletType
              ? () => onWalletTypePickerOpenChange(true)
              : undefined
          }
        >
          <span className="form-sheet-field__value">{walletTypeLabel}</span>
        </FormSheetField>
      ) : null}

      {saveError ? (
        <FormNotice kind={noticeKindForKey(saveError)} reveal>
          <p>{t(saveError)}</p>
          {saveError === 'settings.submitError' ? (
            <button type="button" onClick={() => void handleSave()} disabled={saving}>
              {t('auth.retry')}
            </button>
          ) : null}
        </FormNotice>
      ) : null}
    </FormSheet>
  )
}
