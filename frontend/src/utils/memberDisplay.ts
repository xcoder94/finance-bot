import type { MemberResponse } from '../api/members'

export function getMemberDisplayName(member: MemberResponse): string {
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

export function membersGroupTitle(memberCount: number, isOwner: boolean): string {
  const countPart = `${memberCount} из 4`
  return isOwner ? `${countPart} · вы владелец` : `${countPart} · вы участник`
}

export function buildMemberRowSubtitle(
  member: MemberResponse,
  currentUserId: string,
  roleOwnerLabel: string,
  roleMemberLabel: string,
): string {
  const roleLabel = member.role === 'owner' ? roleOwnerLabel : roleMemberLabel
  if (member.id === currentUserId) {
    return `${roleLabel} · вы`
  }
  return roleLabel
}
