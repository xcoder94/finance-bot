export const PASS_STORAGE_KEY = 'chontak_app_pass'

export function readAppPass(): string | null {
  return localStorage.getItem(PASS_STORAGE_KEY)
}

export function setAppPass(token: string): void {
  localStorage.setItem(PASS_STORAGE_KEY, token)
}

export function clearAppPass(): void {
  localStorage.removeItem(PASS_STORAGE_KEY)
}

export function getAuthHeader(): string {
  const token = readAppPass()
  if (!token) {
    throw new Error('application pass is not available — authenticate first')
  }
  return `Bearer ${token}`
}
