import { getAuthHeader } from './authHeader'

export type ShoppingItem = {
  id: string
  name: string
  created_at: string
}

export type ShoppingErrorCode =
  | 'shopping_limit'
  | 'already_in_list'
  | 'invalid'
  | 'not_found'
  | 'no_wallet'
  | 'receipt_disabled'
  | 'token_conflict'
  | 'purchase_closed'
  | 'network'
  | 'unknown'

export class ShoppingApiError extends Error {
  code: ShoppingErrorCode
  status: number

  constructor(code: ShoppingErrorCode, status = 0) {
    super(code)
    this.code = code
    this.status = status
  }
}

const BASE = '/api/v1/shopping/items'

async function readDetail(response: Response): Promise<unknown> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    return body?.detail
  } catch {
    return undefined
  }
}

async function toError(response: Response): Promise<ShoppingApiError> {
  const detail = await readDetail(response)
  if (response.status === 409 && detail === 'shopping_limit') {
    return new ShoppingApiError('shopping_limit', 409)
  }
  if (response.status === 409 && detail === 'already_in_list') {
    return new ShoppingApiError('already_in_list', 409)
  }
  if (response.status === 409 && detail === 'no_wallet') {
    return new ShoppingApiError('no_wallet', 409)
  }
  if (response.status === 409 && detail === 'receipt_disabled') {
    return new ShoppingApiError('receipt_disabled', 409)
  }
  if (response.status === 409 && detail === 'token_conflict') {
    return new ShoppingApiError('token_conflict', 409)
  }
  if (response.status === 410) {
    return new ShoppingApiError('purchase_closed', 410)
  }
  if (response.status === 422) {
    return new ShoppingApiError('invalid', 422)
  }
  if (response.status === 404) {
    return new ShoppingApiError('not_found', 404)
  }
  return new ShoppingApiError('unknown', response.status)
}

async function send(url: string, method: string, body?: unknown): Promise<Response> {
  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers: {
        Authorization: getAuthHeader(),
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ShoppingApiError('network')
  }
  if (!response.ok) {
    throw await toError(response)
  }
  return response
}

export async function listShoppingItems(): Promise<ShoppingItem[]> {
  const response = await send(BASE, 'GET')
  return (await response.json()) as ShoppingItem[]
}

/** 201 = new item, 200 = the name was already on the list (case-insensitive). */
export async function addShoppingItem(
  name: string,
): Promise<{ item: ShoppingItem; created: boolean }> {
  const response = await send(BASE, 'POST', { name })
  return { item: (await response.json()) as ShoppingItem, created: response.status === 201 }
}

export async function renameShoppingItem(id: string, name: string): Promise<ShoppingItem> {
  const response = await send(`${BASE}/${id}`, 'PATCH', { name })
  return (await response.json()) as ShoppingItem
}

export async function deleteShoppingItem(id: string): Promise<void> {
  await send(`${BASE}/${id}`, 'DELETE')
}

export type ShoppingPurchase = {
  id: string
  transaction_id: string
  items_recorded: number
  amount: number
  currency: string
  category_label: string
  wallet_name: string
  remaining: number
  items_left: number
}

export type ShoppingPurchaseBody = {
  item_ids: string[]
  amount: number
  client_token: string
}

/** 201 = recorded now, 200 = the same client_token was already recorded (nothing new created). */
export async function createShoppingPurchase(
  body: ShoppingPurchaseBody,
): Promise<{ purchase: ShoppingPurchase; replay: boolean }> {
  const response = await send('/api/v1/shopping/purchases', 'POST', body)
  return { purchase: (await response.json()) as ShoppingPurchase, replay: response.status === 200 }
}

export type PendingMethod = 'receipt' | 'voice'
export type PendingStatus = 'awaiting' | 'unrecognized' | 'completed' | 'cancelled' | 'expired'

export type PendingPurchase = {
  id: string
  status: PendingStatus
  method: PendingMethod
  expires_at: string
  purchase_id: string | null
  amount: number | null
}

const PENDING = '/api/v1/shopping/purchases/pending'

/** 201 = new wait, 200 = the same client_token again (the bot hint is not re-sent). */
export async function createPendingPurchase(body: {
  item_ids: string[]
  method: PendingMethod
  client_token?: string
}): Promise<{ pending: PendingPurchase; created: boolean }> {
  const response = await send(PENDING, 'POST', body)
  return { pending: (await response.json()) as PendingPurchase, created: response.status === 201 }
}

export async function fetchPendingPurchase(id: string): Promise<PendingPurchase> {
  const response = await send(`${PENDING}/${id}`, 'GET')
  return (await response.json()) as PendingPurchase
}

/** Manual amount for a waiting purchase: 201 = recorded now, 200 = replay (first amount wins). */
export async function submitPendingAmount(
  id: string,
  amount: number,
): Promise<{ purchase: ShoppingPurchase; replay: boolean }> {
  const response = await send(`${PENDING}/${id}/amount`, 'POST', { amount })
  return { purchase: (await response.json()) as ShoppingPurchase, replay: response.status === 200 }
}

export async function fetchPurchase(id: string): Promise<ShoppingPurchase> {
  const response = await send(`/api/v1/shopping/purchases/${id}`, 'GET')
  return (await response.json()) as ShoppingPurchase
}

/** Idempotent: 200 {status:"cancelled"}; 410 purchase_closed = already recorded; 404 = foreign / unknown. */
export async function cancelPendingPurchaseApi(id: string): Promise<{ status: 'cancelled' }> {
  const response = await send(`/api/v1/shopping/purchases/${id}/cancel`, 'POST')
  return (await response.json()) as { status: 'cancelled' }
}
