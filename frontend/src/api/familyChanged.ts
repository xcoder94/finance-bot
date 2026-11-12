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

let reload: Promise<boolean> | null = null

function sameBudgetAndRole(a: { familyBudgetId: string; role: string } | null | undefined, b: { familyBudgetId: string; role: string }): boolean {
  return Boolean(a) && a!.familyBudgetId === b.familyBudgetId && a!.role === b.role
}

/**
 * Asks /me who the person is now. If the family or the role differ from what the app knows, the
 * new person replaces the old one and the data of both families is dropped. Returns whether it
 * changed. `force` also takes the fresh person and drops the family data when nothing differs
 * (the server itself said family_changed).
 */
async function rereadPerson(force: boolean): Promise<boolean> {
  const old = useAuthStore.getState().user
  let user
  try {
    user = await fetchMe()
  } catch {
    // keep the old person; the form still tells them to check and save again
    if (force && old?.familyBudgetId) invalidateFamilyData(old.familyBudgetId)
    return force
  }
  const changed = !sameBudgetAndRole(old, user)
  if (changed || force) {
    useAuthStore.getState().setReady(user)
    invalidateFamilyData(user.familyBudgetId)
    if (old?.familyBudgetId) invalidateFamilyData(old.familyBudgetId)
  }
  return changed || force
}

/**
 * Coming back to the app: the person may have joined, left or been moved while the app was in the
 * background. Rereads /me; the family data is always refreshed (as before this check existed).
 */
export async function refreshPersonOnReturn(): Promise<void> {
  const old = useAuthStore.getState().user
  const changed = await rereadPerson(false)
  if (!changed && old?.familyBudgetId) {
    invalidateFamilyData(old.familyBudgetId)
  }
}

async function detailOf(response: Response): Promise<unknown> {
  try {
    const copy = typeof response.clone === 'function' ? response.clone() : response
    return ((await copy.json()) as { detail?: unknown } | null)?.detail
  } catch {
    return undefined
  }
}

/** The machine code of a failed response ({"detail": "goal_already_exists"}); the body stays readable. */
export async function errorCodeOf(response: Response): Promise<string | null> {
  const detail = await detailOf(response)
  return typeof detail === 'string' ? detail : null
}

/**
 * Called by every write helper when a response is not ok. Throws FamilyChangedError when the
 * person's family or role is not what the app thought: either the server said so (409
 * family_changed) or it refused with 403/404/409 and /me, asked once, shows a different family or
 * role. Otherwise returns and the caller throws its usual error.
 */
export async function raiseIfFamilyChanged(response: Response): Promise<void> {
  const status = response.status
  if (status !== 403 && status !== 404 && status !== 409) {
    return
  }
  const explicit = status === 409 && (await detailOf(response)) === 'family_changed'
  reload ??= rereadPerson(explicit).finally(() => {
    reload = null
  })
  if (await reload) {
    throw new FamilyChangedError()
  }
}

/** i18n key for a failed save: the family-changed explanation, or the form's usual message. */
export function saveErrorKey(
  error: unknown,
  usualKey: string,
  familyKey = 'familyChanged.generic',
): string {
  return error instanceof FamilyChangedError ? familyKey : usualKey
}

/**
 * Forms that only the owner may save (categories, goals): if the person is no longer the owner
 * after the family change, say that; otherwise the generic family message.
 */
export function ownerFormErrorKey(error: unknown, usualKey: string, ownerOnlyKey: string): string {
  if (!(error instanceof FamilyChangedError)) return usualKey
  return useAuthStore.getState().user?.role === 'owner' ? 'familyChanged.generic' : ownerOnlyKey
}
