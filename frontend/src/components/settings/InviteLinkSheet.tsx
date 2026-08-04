import { useTranslation } from 'react-i18next'

import { LIMIT_MEMBERS, MEMBER_LIMIT } from '../../constants/entityLimits'
import { useNativeBackButtonOverlay } from '../nativeBackButtonContext'
import { FormSheet } from '../forms/FormSheet'
import { FormSheetField } from '../forms/FormSheetField'

type InviteLinkSheetProps = {
  open: boolean
  inviteLink: string
  atLimit: boolean
  loading: boolean
  reissuing: boolean
  onClose: () => void
  onCopy: () => void
  onReissue: () => void
}

export function InviteLinkSheet({
  open,
  inviteLink,
  atLimit,
  loading,
  reissuing,
  onClose,
  onCopy,
  onReissue,
}: InviteLinkSheetProps) {
  const { t } = useTranslation()

  useNativeBackButtonOverlay(open, onClose)

  const copyDisabled = atLimit || loading || !inviteLink

  return (
    <FormSheet
      open={open}
      title={t('settings.inviteLink')}
      onClose={onClose}
      cancelLabel="Отмена"
      primaryLabel={t('settings.copyLink')}
      onPrimary={onCopy}
      primaryDisabled={copyDisabled}
      primaryLoading={loading}
    >
      {loading ? (
        <div className="form-sheet-loading" role="status">
          {t('home.loading')}
        </div>
      ) : (
        <>
          <FormSheetField
            label={t('settings.membersScreen.linkFieldLabel')}
            hint={atLimit ? LIMIT_MEMBERS : undefined}
            hintError={atLimit}
            mono
            muted
          >
            {inviteLink || '—'}
          </FormSheetField>
          <button
            type="button"
            className="form-sheet-cancel invite-link-sheet__reissue"
            onClick={onReissue}
            disabled={loading || reissuing}
          >
            {reissuing ? '…' : t('settings.membersScreen.reissueLink')}
          </button>
        </>
      )}
    </FormSheet>
  )
}

export function isMembersAtLimit(memberCount: number): boolean {
  return memberCount >= MEMBER_LIMIT
}
