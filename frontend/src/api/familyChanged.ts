import { useAuthStore } from '../store/authStore'
import { invalidateFamilyData } from '../store/dataCacheStore'
import { fetchMe } from './me'

/**
 * The server refused a write with 409 {"detail":"family_changed"}: the person joined or left a
 * family while the request was in flight, nothing was saved. Thrown after the app has already
 * reread the person and the family data; there is no automatic retry because the category and
 * wallet ids in the form belong to the old budget.
 */
export class FamilyChangedError extends Error {
  constructor() {
    super('family_changed')
  }
}

let reload: Promise<void> | null = null

async function rereadEverything(): Promise<void> {
  const oldFamilyId = useAuthStore.getState().user?.familyBudgetId
  try {
    const user = await fetchMe()
    useAuthStore.getState().setReady(user)
    invalidateFamilyData(user.familyBudgetId)
  } catch {
    // keep the old person; the message still tells them to check and save again
  }
  if (oldFamilyId) {
    invalidateFamilyData(oldFamilyId)
  }
}

/** Called by every write helper when a response is not ok. Throws FamilyChangedError if it is one. */
export async function raiseIfFamilyChanged(response: Response): Promise<void> {
  if (response.status !== 409) {
    return
  }
  let detail: unknown
  try {
    detail = ((await response.json()) as { detail?: unknown } | null)?.detail
  } catch {
    return
  }
  if (detail !== 'family_changed') {
    return
  }
  reload ??= rereadEverything().finally(() => {
    reload = null
  })
  await reload
  throw new FamilyChangedError()
}

/** i18n key for a failed save: the family-changed explanation, or the form's usual message. */
export function saveErrorKey(error: unknown, usualKey: string): string {
  return error instanceof FamilyChangedError ? 'familyChanged.message' : usualKey
}
