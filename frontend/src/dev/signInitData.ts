if (!import.meta.env.DEV) {
  throw new Error('signInitData is available only in development builds')
}

/** Owner test user (matches backend seed). */
const DEV_TELEGRAM_ID_OWNER = 111111
/** Member test user — assign to `DEV_TELEGRAM_ID` to test Member role. */
export const DEV_TELEGRAM_ID_MEMBER = 222222
const DEV_TELEGRAM_ID = DEV_TELEGRAM_ID_OWNER

const DEV_FIRST_NAME = DEV_TELEGRAM_ID === DEV_TELEGRAM_ID_OWNER ? 'Owner' : 'Member'

function bufferToHex(buffer: ArrayBuffer): string {
  return [...new Uint8Array(buffer)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

async function hmacSha256(
  key: BufferSource,
  message: string,
): Promise<ArrayBuffer> {
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    key,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  return crypto.subtle.sign('HMAC', cryptoKey, new TextEncoder().encode(message))
}

async function computeInitDataHash(
  dataCheckString: string,
  botToken: string,
): Promise<string> {
  const secretKey = await hmacSha256(
    new TextEncoder().encode('WebAppData'),
    botToken,
  )
  const hash = await hmacSha256(secretKey, dataCheckString)
  return bufferToHex(hash)
}

function buildUserPayload(telegramId: number, firstName: string): string {
  return JSON.stringify({
    id: telegramId,
    first_name: firstName,
    language_code: 'ru',
  })
}

export async function buildDevInitData(): Promise<string> {
  const botToken = import.meta.env.VITE_DEV_BOT_TOKEN
  if (!botToken) {
    throw new Error('VITE_DEV_BOT_TOKEN is not set in frontend/.env.development')
  }

  const fields: Record<string, string> = {
    auth_date: String(Math.floor(Date.now() / 1000)),
    query_id: 'AAHtestQueryId',
    user: buildUserPayload(DEV_TELEGRAM_ID, DEV_FIRST_NAME),
  }

  const dataCheckString = Object.keys(fields)
    .sort()
    .map((key) => `${key}=${fields[key]}`)
    .join('\n')

  const hash = await computeInitDataHash(dataCheckString, botToken)
  const query = Object.entries(fields)
    .map(([key, value]) => `${key}=${value}`)
    .join('&')

  return `${query}&hash=${hash}`
}
