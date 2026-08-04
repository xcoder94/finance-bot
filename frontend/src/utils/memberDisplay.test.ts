import { describe, expect, it } from 'vitest'

import type { MemberResponse } from '../api/members'
import {
  buildMemberRowSubtitle,
  getMemberDisplayName,
  membersGroupTitle,
} from './memberDisplay'

describe('memberDisplay', () => {
  const owner: MemberResponse = {
    id: '1',
    first_name: 'Рустам',
    username: null,
    role: 'owner',
  }

  const member: MemberResponse = {
    id: '2',
    first_name: null,
    username: 'dilnoza',
    role: 'member',
  }

  it('formats display name from first name or username', () => {
    expect(getMemberDisplayName(owner)).toBe('Рустам')
    expect(getMemberDisplayName(member)).toBe('@dilnoza')
    expect(
      getMemberDisplayName({ id: '3', first_name: null, username: null, role: 'member' }),
    ).toBe('—')
  })

  it('formats members group title', () => {
    expect(membersGroupTitle(3, true)).toBe('3 из 4 · вы владелец')
    expect(membersGroupTitle(3, false)).toBe('3 из 4 · вы участник')
  })

  it('formats member row subtitle with you marker', () => {
    expect(buildMemberRowSubtitle(owner, '1', 'Владелец', 'Участник')).toBe('Владелец · вы')
    expect(buildMemberRowSubtitle(member, '1', 'Владелец', 'Участник')).toBe('Участник')
    expect(buildMemberRowSubtitle(member, '2', 'Владелец', 'Участник')).toBe('Участник · вы')
  })
})
