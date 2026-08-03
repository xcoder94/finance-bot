import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { getMembers, type MemberResponse } from '../../api/members'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsSectionLoadError, SettingsSectionLoading } from '../../components/settings/EditableEntityList'
import { SettingsStaticRow } from '../../components/settings/SettingsStaticRow'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
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

type MembersSettingsBodyProps = {
  members: MemberResponse[]
  currentUserId: string
  isOwner: boolean
}

export function MembersSettingsBody({
  members,
  currentUserId,
  isOwner,
}: MembersSettingsBodyProps) {
  const { t } = useTranslation()
  const roleOwnerLabel = t('settings.roles.owner')
  const roleMemberLabel = t('settings.roles.member')

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
        <SettingsStaticRow
          key={member.id}
          name={getMemberDisplayName(member)}
          subtitle={buildMemberRowSubtitle(
            member,
            currentUserId,
            roleOwnerLabel,
            roleMemberLabel,
          )}
        />
      ))}
    </SettingsEntityGroup>
  )
}

export function MembersSettingsShellPage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'

  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [reloadCount, setReloadCount] = useState(0)

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

  if (!user) {
    return null
  }

  return (
    <SettingsSubPageShell
      title={t('settings.toc.members')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
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
        />
      ) : null}
    </SettingsSubPageShell>
  )
}
