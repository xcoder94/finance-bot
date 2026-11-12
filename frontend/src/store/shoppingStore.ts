import { FamilyChangedError } from '../api/familyChanged'
import { create } from 'zustand'

import {
  addShoppingItem,
  createShoppingPurchase,
  deleteShoppingItem,
  listShoppingItems,
  renameShoppingItem,
  ShoppingApiError,
  type ShoppingItem,
  type ShoppingPurchase,
  type ShoppingPurchaseBody,
} from '../api/shopping'
import { normalizeShoppingName, sameShoppingName } from '../utils/shoppingText'

export type ShoppingStatus = 'idle' | 'loading' | 'ready' | 'error'
export type AddResult = 'added' | 'duplicate' | 'limit' | 'invalid' | 'failed'
export type RenameResult = 'ok' | 'duplicate' | 'invalid' | 'gone' | 'failed'
export type RemoveResult = 'ok' | 'failed'
export type PurchaseOutcome =
  | { kind: 'ok'; purchase: ShoppingPurchase; replay: boolean }
  | { kind: 'no_wallet' }
  /** the person's family changed while saving: nothing was recorded */
  | { kind: 'family_changed' }
  /** definite = the server answered with a 4xx (nothing was recorded); otherwise the outcome is unknown. */
  | { kind: 'failed'; definite: boolean }

type ShoppingState = {
  items: ShoppingItem[]
  status: ShoppingStatus
  /** Family the shown items belong to; a different family never sees them. */
  scope: string
  load: (scope: string, options?: { silent?: boolean }) => Promise<void>
  add: (rawName: string) => Promise<AddResult>
  rename: (id: string, rawName: string) => Promise<RenameResult>
  remove: (id: string) => Promise<RemoveResult>
  purchase: (body: ShoppingPurchaseBody) => Promise<PurchaseOutcome>
}

let loadSeq = 0

function codeOf(error: unknown): string {
  return error instanceof ShoppingApiError ? error.code : 'unknown'
}

export const useShoppingStore = create<ShoppingState>((set, get) => ({
  items: [],
  status: 'idle',
  scope: '',

  load: async (scope, options) => {
    const seq = ++loadSeq
    const known = get().scope === scope
    if (!known) {
      set({ items: [], scope, status: 'loading' })
    } else if (!options?.silent || get().status === 'idle' || get().status === 'error') {
      set({ status: get().items.length > 0 ? get().status : 'loading' })
    }
    try {
      const items = await listShoppingItems()
      if (seq !== loadSeq) {
        return
      }
      set({ items, status: 'ready', scope })
    } catch {
      if (seq !== loadSeq) {
        return
      }
      if (get().items.length === 0 || get().status !== 'ready') {
        set({ status: 'error' })
      }
    }
  },

  add: async (rawName) => {
    const name = normalizeShoppingName(rawName)
    if (name.length === 0) {
      return 'invalid'
    }
    if (get().items.some((item) => sameShoppingName(item.name, name))) {
      return 'duplicate'
    }
    try {
      const { item, created } = await addShoppingItem(name)
      set((state) =>
        state.items.some((existing) => existing.id === item.id)
          ? state
          : { items: [...state.items, item] },
      )
      return created ? 'added' : 'duplicate'
    } catch (error) {
      const code = codeOf(error)
      if (code === 'shopping_limit') return 'limit'
      if (code === 'invalid') return 'invalid'
      return 'failed'
    }
  },

  rename: async (id, rawName) => {
    const name = normalizeShoppingName(rawName)
    if (name.length === 0) {
      return 'invalid'
    }
    const current = get().items.find((item) => item.id === id)
    if (current && current.name === name) {
      return 'ok'
    }
    if (get().items.some((item) => item.id !== id && sameShoppingName(item.name, name))) {
      return 'duplicate'
    }
    try {
      const updated = await renameShoppingItem(id, name)
      set((state) => ({
        items: state.items.map((item) => (item.id === id ? updated : item)),
      }))
      return 'ok'
    } catch (error) {
      const code = codeOf(error)
      if (code === 'already_in_list') return 'duplicate'
      if (code === 'invalid') return 'invalid'
      if (code === 'not_found') {
        await get().load(get().scope, { silent: true })
        return 'gone'
      }
      return 'failed'
    }
  },

  remove: async (id) => {
    try {
      await deleteShoppingItem(id)
    } catch (error) {
      if (codeOf(error) !== 'not_found') {
        return 'failed'
      }
    }
    set((state) => ({ items: state.items.filter((item) => item.id !== id) }))
    return 'ok'
  },

  purchase: async (body) => {
    try {
      const { purchase, replay } = await createShoppingPurchase(body)
      if (replay) {
        // The recorded set may differ from the one just sent: trust the server.
        await get().load(get().scope, { silent: true })
      } else {
        const bought = new Set(body.item_ids)
        set((state) => ({ items: state.items.filter((item) => !bought.has(item.id)) }))
      }
      return { kind: 'ok', purchase, replay }
    } catch (error) {
      if (error instanceof FamilyChangedError) return { kind: 'family_changed' }
      if (codeOf(error) === 'no_wallet') return { kind: 'no_wallet' }
      const status = error instanceof ShoppingApiError ? error.status : 0
      return { kind: 'failed', definite: status >= 400 && status < 500 }
    }
  },
}))
