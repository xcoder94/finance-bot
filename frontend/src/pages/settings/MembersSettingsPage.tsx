import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import {
  getInviteLink,
  getMembers,
  leaveFamily,
  regenerateInviteLink,
  type MemberResponse,
} from '../../api/members'
import { fetchMe } from '../../api/me'
import { InviteLinkSheet, isMembersAtLimit } from '../../components/settings/InviteLinkSheet'
import { MemberConfirmSheet } from '../../components/settings/MemberConfirmSheet'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsSectionLoadError, SettingsSectionLoading } from '../../components/settings/EditableEntityList'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import { SwipeableSettingsRow } from '../../components/settings/SwipeableSettingsRow'
import { useAuthStore } from '../../store/authStore'
import {
  buildMemberRowSubtitle,
  getMemberDisplayName,
  membersGroupTitle,
} from '../../utils/memberDisplay'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; members: MemberResponse[] }

type SheetState = { kind: 'closed' } | { kind: 'invite' } | { kind: 'leave' }

type MembersSettingsBodyProps = {
  members: MemberResponse[]
  currentUserId: string
  isOwner: boolean
  onOpenMember: (memberId: string) => void
}

export function MembersSettingsBody({
  members,
  currentUserId,
  isOwner,
  onOpenMember,
}: MembersSettingsBodyProps) {
  const { t } = useTranslation()
  const roleOwnerLabel = t('settings.roles.owner')
  const roleMemberLabel = t('settings.roles.member')
  const sincePrefix = t('settings.membersScreen.sincePrefix')

  return (
    <SettingsEntityGroup
      title={membersGroupTitle(members.length, isOwner)}
      note={
        isOwner
          ? t('settings.membersScreen.noteOwner')
          : t('settings.membersScreen.noteMember')
      }
    >
      {members.map((member) => (
        <SwipeableSettingsRow
          key={member.id}
          name={getMemberDisplayName(member)}
          subtitle={buildMemberRowSubtitle(
            member,
            currentUserId,
            roleOwnerLabel,
            roleMemberLabel,
            sincePrefix,
          )}
          onOpen={() => onOpenMember(member.id)}
        />
      ))}
    </SettingsEntityGroup>
  )
}

type MembersSettingsPageChromeProps = {
  isOwner: boolean
  children?: ReactNode
}

export function MembersSettingsPageChrome({
  isOwner,
  children,
}: MembersSettingsPageChromeProps) {
  const { t } = useTranslation()

  return (
    <SettingsSubPageShell
      title={t('settings.toc.members')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
      actionLabel={isOwner ? t('settings.inviteLink') : undefined}
      onAction={isOwner ? () => undefined : undefined}
      dangerLabel={!isOwner ? t('settings.membersScreen.leaveBudget') : undefined}
      onDanger={!isOwner ? () => undefined : undefined}
    >
      {children}
    </SettingsSubPageShell>
  )
}

export function MembersSettingsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const setReady = useAuthStore((state) => state.setReady)
  const isOwner = user?.role === 'owner'

  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [reloadCount, setReloadCount] = useState(0)
  const [sheetState, setSheetState] = useState<SheetState>({ kind: 'closed' })
  const [inviteLink, setInviteLink] = useState('')
  const [inviteLoading, setInviteLoading] = useState(false)
  const [reissuing, setReissuing] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const [leaveError, setLeaveError] = useState(false)

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

  const loadInviteLink = useCallback(async () => {
    setInviteLoading(true)
    try {
      const response = await getInviteLink()
      setInviteLink(response.invite_link)
    } catch {
      setInviteLink('')
    } finally {
      setInviteLoading(false)
    }
  }, [])

  useEffect(() => {
    if (sheetState.kind !== 'invite') {
      return
    }
    void loadInviteLink()
  }, [sheetState, loadInviteLink])

  const handleOpenInvite = () => {
    setSheetState({ kind: 'invite' })
  }

  const handleCopyInvite = async () => {
    if (!inviteLink) {
      return
    }
    try {
      await navigator.clipboard.writeText(inviteLink)
    } catch {
      // Clipboard may be unavailable in some WebViews.
    }
  }

  const handleReissueInvite = async () => {
    setReissuing(true)
    try {
      const response = await regenerateInviteLink()
      setInviteLink(response.invite_link)
    } catch {
      setInviteLink('')
    } finally {
      setReissuing(false)
    }
  }

  const handleLeave = async () => {
    setLeaving(true)
    setLeaveError(false)
    try {
      await leaveFamily()
      const nextUser = await fetchMe()
      setReady(nextUser)
      navigate('/settings', { replace: true })
    } catch {
      setLeaveError(true)
    } finally {
      setLeaving(false)
    }
  }

  if (!user) {
    return null
  }

  const memberCount = loadState.status === 'success' ? loadState.members.length : user.memberCount
  const atLimit = isMembersAtLimit(memberCount)

  return (
    <>
      <SettingsSubPageShell
        title={t('settings.toc.members')}
        backLabel={t('settings.toc.back')}
        backTo="/settings"
        actionLabel={isOwner ? t('settings.inviteLink') : undefined}
        onAction={isOwner ? handleOpenInvite : undefined}
        dangerLabel={!isOwner ? t('settings.membersScreen.leaveBudget') : undefined}
        onDanger={!isOwner ? () => setSheetState({ kind: 'leave' }) : undefined}
      >
        {loadState.status === 'loading' ? (
          <div className="settings-entity-page__loading">
            <SettingsSectionLoading />
          </div>
        ) : null}
        {loadState.status === 'error' ? (
          <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
        ) : null}
        {loadState.status === 'success' ? (
          <MembersSettingsBody
            members={loadState.members}
            currentUserId={user.id}
            isOwner={isOwner}
            onOpenMember={(memberId) => navigate(`/settings/members/${memberId}`)}
          />
        ) : null}
      </SettingsSubPageShell>

      <InviteLinkSheet
        open={sheetState.kind === 'invite'}
        inviteLink={inviteLink}
        atLimit={atLimit}
        loading={inviteLoading}
        reissuing={reissuing}
        onClose={() => setSheetState({ kind: 'closed' })}
        onCopy={() => void handleCopyInvite()}
        onReissue={() => void handleReissueInvite()}
      />

      <MemberConfirmSheet
        open={sheetState.kind === 'leave'}
        title={t('settings.membersScreen.leaveConfirmTitle')}
        intro={t('settings.membersScreen.leaveConfirmIntro')}
        confirmLabel={t('settings.membersScreen.leaveBudget')}
        onClose={() => {
          setSheetState({ kind: 'closed' })
          setLeaveError(false)
        }}
        onConfirm={() => void handleLeave()}
        confirming={leaving}
        error={leaveError}
      />
    </>
  )
}
