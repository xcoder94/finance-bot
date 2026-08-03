import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { WalletResponse } from '../../api/wallets'
import {
  ENTITY_NAME_MAX,
  LIMIT_SHARED_WALLETS,
  SHARED_WALLET_LIMIT,
} from '../../constants/entityLimits'
import { useNativeBackButtonOverlay } from '../nativeBackButtonContext'
import { FormSheet } from '../forms/FormSheet'
import { FormSheetField } from '../forms/FormSheetField'

export type WalletFormMode = 'create' | 'edit'

type WalletFormSheetProps = {
  open: boolean
  mode: WalletFormMode
  wallet: WalletResponse | null
  displayName?: string
  sharedWalletCount: number
  editable: boolean
  onClose: () => void
  onSave: (payload: { name: string; currency: 'UZS' | 'USD' }) => Promise<void>
  currencyPickerOpen: boolean
  onCurrencyPickerOpenChange: (open: boolean) => void
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
  editable,
  onClose,
  onSave,
  currencyPickerOpen,
  onCurrencyPickerOpenChange,
}: WalletFormSheetProps) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [currency, setCurrency] = useState<'UZS' | 'USD'>('UZS')
  const [nameTouched, setNameTouched] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(false)

  const atSharedLimit = mode === 'create' && sharedWalletCount >= SHARED_WALLET_LIMIT
  const currencyLocked = mode === 'edit' && wallet !== null && wallet.transaction_count > 0

  useEffect(() => {
    if (!open) {
      return
    }
    setName(wallet?.name ?? '')
    setCurrency((wallet?.currency as 'UZS' | 'USD') ?? 'UZS')
    setNameTouched(false)
    setSaving(false)
    setSaveError(false)
  }, [open, wallet])

  useNativeBackButtonOverlay(open && !currencyPickerOpen, onClose)

  const nameValidation = validateWalletName(name)
  const nameErrorKey =
    nameValidation === 'required'
      ? 'settings.nameRequired'
      : nameValidation === 'tooLong'
        ? 'settings.nameTooLong30'
        : null

  const trimmedLength = name.trim().length
  const fieldHint = atSharedLimit
    ? LIMIT_SHARED_WALLETS
    : nameTouched && nameErrorKey
      ? t(nameErrorKey)
      : undefined
  const fieldHintError = atSharedLimit || (nameTouched && nameErrorKey !== null)

  const canSave =
    editable &&
    !atSharedLimit &&
    nameValidation === null &&
    !saving &&
    (mode === 'create' || wallet !== null)

  const title =
    mode === 'create' ? t('settings.walletForm.newTitle') : (displayName ?? wallet?.name ?? '')

  const intro =
    mode === 'create' && editable ? t('settings.walletForm.createIntroOwner') : undefined

  const handleSave = async () => {
    setNameTouched(true)
    if (!canSave || nameValidation) {
      return
    }

    setSaving(true)
    setSaveError(false)
    try {
      await onSave({ name: name.trim(), currency })
      onClose()
    } catch {
      setSaveError(true)
    } finally {
      setSaving(false)
    }
  }

  if (currencyPickerOpen) {
    return (
      <FormSheet
        open={open}
        title={t('settings.currencyLabel')}
        onClose={() => onCurrencyPickerOpenChange(false)}
        showPrimary={false}
      >
        <div className="category-picker">
          {(['UZS', 'USD'] as const).map((option) => {
            const selected = currency === option
            return (
              <button
                key={option}
                type="button"
                className="category-picker__row"
                onClick={() => {
                  setCurrency(option)
                  onCurrencyPickerOpenChange(false)
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
                <span className="category-picker__name">{option}</span>
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

      <FormSheetField
        label="Валюта"
        right="›"
        hint={
          currencyLocked ? 'После первой операции валюта не меняется' : undefined
        }
        onClick={
          editable && mode === 'create' && !currencyLocked
            ? () => onCurrencyPickerOpenChange(true)
            : undefined
        }
      >
        <span className="form-sheet-field__value">{currency}</span>
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
