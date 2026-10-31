/** Where a non-admin is sent from /admin; null = stay. The server still answers 404 to non-admins. */
export function adminRedirectTarget(isAdmin: boolean): string | null {
  return isAdmin ? null : '/settings'
}
