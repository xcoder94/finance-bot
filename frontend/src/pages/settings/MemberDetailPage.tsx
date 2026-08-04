import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { getMembers, removeMember, requestTransfer, type MemberResponse } from '../../api/members'
import { MemberConfirmSheet } from '../../components/settings/MemberConfirmSheet'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsSectionLoadError, SettingsSectionLoading } from '../../components/settings/EditableEntityList'
import { SettingsStaticRow } from '../../components/settings/SettingsStaticRow'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import { useAuthStore } from '../../store/authStore'
import {
  buildMemberRowSubtitle,
  getMemberDisplayName,
} from '../../utils/memberDisplay'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; members: MemberResponse[] }

type ConfirmKind = 'transfer' | 'remove'

type SheetState = { kind: 'closed' } | { kind: 'confirm'; confirmKind: ConfirmKind }

export function MemberDetailPage() {
  const { id: memberId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'

  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [reloadCount, setReloadCount] = useState(0)
  const [sheetState, setSheetState] = useState<SheetState>({ kind: 'closed' })
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(false)

  const loadMembers = useCallback(async () => {
    setLoadState((current) => (current.status === 'success' ? current : { status: 'loading' }))
    try {
      const members = await getMembers()
      setLoadState({ status: 'success', members })
    } catch {
      setLoadState((current) => (current.status === 'success' ? current : { status: 'error' }))
    }
  }, [])

  useEffect(() => {
    void loadMembers()
  }, [loadMembers, reloadCount])

  const member = useMemo(() => {
    if (loadState.status !== 'success' || !memberId) {
      return null
    }
    return loadState.members.find((row) => row.id === memberId) ?? null
  }, [loadState, memberId])

  if (!user || !memberId) {
    return null
  }

  const displayName = member ? getMemberDisplayName(member) : '—'
  const roleOwnerLabel = t('settings.roles.owner')
  const roleMemberLabel = t('settings.roles.member')
  const sincePrefix = t('settings.membersScreen.sincePrefix')
  const canManage =
    isOwner && member !== null && member.id !== user.id && member.role !== 'owner'

  const handleConfirm = async () => {
    if (!member || sheetState.kind !== 'confirm') {
      return
    }

    setSubmitting(true)
    setSubmitError(false)
    try {
      if (sheetState.confirmKind === 'remove') {
        await removeMember(member.id)
        navigate('/settings/members', { replace: true })
        return
      }
      await requestTransfer(member.id)
      setSheetState({ kind: 'closed' })
    } catch {
      setSubmitError(true)
    } finally {
      setSubmitting(false)
    }
  }

  const confirmCopy =
    sheetState.kind === 'confirm' && member
      ? sheetState.confirmKind === 'remove'
        ? {
            title: t('settings.membersScreen.removeConfirmTitle', { name: displayName }),
            intro: t('settings.membersScreen.removeConfirmIntro'),
            confirmLabel: t('settings.membersScreen.removeMember'),
          }
        : {
            title: t('settings.membersScreen.transferConfirmTitle'),
            intro: t('settings.membersScreen.transferConfirmIntro', { name: displayName }),
            confirmLabel: t('settings.membersScreen.transferOwnership'),
          }
      : null

  return (
    <>
      <SettingsSubPageShell
        title={displayName}
        backLabel={t('settings.membersScreen.backToMembers')}
        backTo="/settings/members"
      >
        {loadState.status === 'loading' ? (
          <div className="settings-entity-page__loading">
            <SettingsSectionLoading />
          </div>
        ) : null}
        {loadState.status === 'error' ? (
          <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
        ) : null}
        {loadState.status === 'success' && member ? (
          <>
            <SettingsEntityGroup title={t('settings.role')}>
              <SettingsStaticRow
                name={displayName}
                subtitle={buildMemberRowSubtitle(
                  member,
                  user.id,
                  roleOwnerLabel,
                  roleMemberLabel,
                  sincePrefix,
                )}
              />
            </SettingsEntityGroup>
            {canManage ? (
              <div className="member-detail-actions">
                <button
                  type="button"
                  className="settings-sub-page__action"
                  onClick={() => setSheetState({ kind: 'confirm', confirmKind: 'transfer' })}
                >
                  {t('settings.membersScreen.transferOwnership')}
                </button>
                <button
                  type="button"
                  className="settings-sub-page__danger"
                  onClick={() => setSheetState({ kind: 'confirm', confirmKind: 'remove' })}
                >
                  {t('settings.membersScreen.removeMember')}
                </button>
              </div>
            ) : null}
          </>
        ) : null}
        {loadState.status === 'success' && !member ? (
          <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
        ) : null}
      </SettingsSubPageShell>

      {confirmCopy ? (
        <MemberConfirmSheet
          open={sheetState.kind === 'confirm'}
          title={confirmCopy.title}
          intro={confirmCopy.intro}
          confirmLabel={confirmCopy.confirmLabel}
          onClose={() => {
            setSheetState({ kind: 'closed' })
            setSubmitError(false)
          }}
          onConfirm={() => void handleConfirm()}
          confirming={submitting}
          error={submitError}
        />
      ) : null}
    </>
  )
}
