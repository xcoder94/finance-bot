import type { WalletResponse } from '../api/wallets'

/** «Деньги в кошельках»: balance of the shared (non-personal) UZS wallets. */
export function sharedUzsWalletsTotal(wallets: WalletResponse[]): number {
  return wallets
    .filter((wallet) => wallet.currency === 'UZS' && !wallet.is_personal)
    .reduce((sum, wallet) => sum + wallet.balance, 0)
}
