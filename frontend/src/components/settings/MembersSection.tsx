import { useCallback, useEffect, useState } from 'react'
import { Button, Cell, Section, Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import { getInviteLink, getMembers, type MemberResponse } from '../../api/members'
import { useAuthStore } from '../../store/authStore'
import { SettingsSectionLoadError, SettingsSectionLoading } from './EditableEntityList'

type MembersLoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; members: MemberResponse[] }

type InviteLinkLoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; inviteLink: string }

function getMemberDisplayName(member: MemberResponse): string {
  const firstName = member.first_name?.trim()
  if (firstName) {
    return firstName
  }

  const username = member.username?.trim()
  if (username) {
    return username.startsWith('@') ? username : `@${username}`
  }

  return '—'
}

export function MembersSection() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'

  const [membersLoadState, setMembersLoadState] = useState<MembersLoadState>({
    status: 'loading',
  })
  const [inviteLinkLoadState, setInviteLinkLoadState] = useState<InviteLinkLoadState | null>(
    isOwner ? { status: 'loading' } : null,
  )
  const [reloadCount, setReloadCount] = useState(0)
  const [copied, setCopied] = useState(false)

  const loadMembers = useCallback(async () => {
    setMembersLoadState((current) =>
      current.status === 'success' ? current : { status: 'loading' },
    )
    try {
      const members = await getMembers()
      setMembersLoadState({ status: 'success', members })
    } catch {
      setMembersLoadState((current) =>
        current.status === 'success' ? current : { status: 'error' },
      )
    }
  }, [])

  const loadInviteLink = useCallback(async () => {
    if (!isOwner) {
      setInviteLinkLoadState(null)
      return
    }

    setInviteLinkLoadState((current) =>
      current?.status === 'success' ? current : { status: 'loading' },
    )

    try {
      const response = await getInviteLink()
      setInviteLinkLoadState({ status: 'success', inviteLink: response.invite_link })
    } catch {
      setInviteLinkLoadState((current) =>
        current?.status === 'success' ? current : { status: 'error' },
      )
    }
  }, [isOwner])

  useEffect(() => {
    void loadMembers()
  }, [loadMembers, reloadCount])

  useEffect(() => {
    void loadInviteLink()
  }, [loadInviteLink, reloadCount])

  useEffect(() => {
    if (!copied) {
      return
    }

    const timeoutId = window.setTimeout(() => {
      setCopied(false)
    }, 2000)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [copied])

  const handleCopyInviteLink = async () => {
    if (inviteLinkLoadState?.status !== 'success') {
      return
    }

    try {
      await navigator.clipboard.writeText(inviteLinkLoadState.inviteLink)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <Section header={t('settings.members')}>
      {membersLoadState.status === 'loading' ? <SettingsSectionLoading /> : null}
      {membersLoadState.status === 'error' ? (
        <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
      ) : null}

      {membersLoadState.status === 'success'
        ? membersLoadState.members.map((member) => (
            <Cell key={member.id} subtitle={member.role}>
              <Text>{getMemberDisplayName(member)}</Text>
            </Cell>
          ))
        : null}

      {isOwner ? (
        <>
          {inviteLinkLoadState?.status === 'loading' ? <SettingsSectionLoading /> : null}
          {inviteLinkLoadState?.status === 'error' ? (
            <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
          ) : null}
          {inviteLinkLoadState?.status === 'success' ? (
            <Cell subtitle={t('settings.inviteLink')}>
              <div className="settings-invite-link-block">
                <Text className="settings-invite-link-block__url">
                  {inviteLinkLoadState.inviteLink}
                </Text>
                <Button mode="plain" size="s" onClick={() => void handleCopyInviteLink()}>
                  {copied ? t('settings.linkCopied') : t('settings.copyLink')}
                </Button>
              </div>
            </Cell>
          ) : null}
        </>
      ) : null}
    </Section>
  )
}
