let cachedInitData: string | null = null

export function setInitData(initData: string): void {
  cachedInitData = initData
}

export function getAuthHeader(): string {
  if (!cachedInitData) {
    throw new Error('initData is not available — authenticate first')
  }
  return `tma ${cachedInitData}`
}
