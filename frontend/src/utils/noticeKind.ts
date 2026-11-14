export type NoticeKind = 'error' | 'warning' | 'info'

/** Which look a form message key gets: a failure is red, «the family changed» is a warning, a hint is neutral. */
export function noticeKindForKey(key: string): NoticeKind {
  if (key === 'familyChanged.pickReplaced') return 'info'
  if (key.startsWith('familyChanged.')) return 'warning'
  return 'error'
}
