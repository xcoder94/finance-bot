import { cloudStorage } from '@tma.js/sdk-react'

export async function cloudGet(key: string): Promise<string | null> {
  try {
    if (!cloudStorage.getItem.isAvailable()) return null
    const value = await cloudStorage.getItem(key)
    return value || null
  } catch {
    return null
  }
}

export async function cloudSet(key: string, value: string): Promise<void> {
  try {
    if (!cloudStorage.setItem.isAvailable()) return
    await cloudStorage.setItem(key, value)
  } catch {
    // localStorage already holds the value
  }
}
