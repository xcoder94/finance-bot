import { describe, expect, it } from 'vitest'

import type { MemberResponse } from '../api/members'
import {
  buildMemberRowSubtitle,
  formatMemberJoinDate,
  getMemberDisplayName,
  membersGroupTitle,
} from './memberDisplay'

describe('memberDisplay', () => {
  const owner: MemberResponse = {
    id: '1',
    first_name: 'Рустам',
    username: null,
    role: 'owner',
    created_at: '2026-01-15T10:00:00Z',
  }

  const member: MemberResponse = {
    id: '2',
    first_name: null,
    username: 'dilnoza',
    role: 'member',
    created_at: '2026-03-12T10:00:00Z',
  }

  it('formats display name from first name or username', () => {
    expect(getMemberDisplayName(owner)).toBe('Рустам')
    expect(getMemberDisplayName(member)).toBe('@dilnoza')
    expect(
      getMemberDisplayName({
        id: '3',
        first_name: null,
        username: null,
        role: 'member',
        created_at: '2026-01-01T00:00:00Z',
      }),
    ).toBe('—')
  })

  it('formats members group title', () => {
    expect(membersGroupTitle(3, true)).toBe('3 из 4 · вы владелец')
    expect(membersGroupTitle(3, false)).toBe('3 из 4 · вы участник')
  })

  it('formats member join date', () => {
    expect(formatMemberJoinDate('2026-03-12T10:00:00Z')).toMatch(/12\.03\.2026/)
  })

  it('formats member row subtitle with you marker and join date', () => {
    expect(buildMemberRowSubtitle(owner, '1', 'Владелец', 'Участник', 'с')).toBe('Владелец · вы')
    expect(buildMemberRowSubtitle(member, '1', 'Владелец', 'Участник', 'с')).toBe(
      'Участник · с 12.03.2026',
    )
    expect(buildMemberRowSubtitle(member, '2', 'Владелец', 'Участник', 'с')).toBe('Участник · вы')
  })
})
