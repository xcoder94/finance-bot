import {
  LIMIT_PERSONAL_WALLETS,
  LIMIT_SHARED_WALLETS,
  PERSONAL_WALLET_LIMIT,
  SHARED_WALLET_LIMIT,
} from '../../constants/entityLimits'

export type WalletFormType = 'shared' | 'personal'

export function walletCreateLimitHint(
  walletType: WalletFormType,
  sharedWalletCount: number,
  personalWalletCount: number,
): string | undefined {
  if (walletType === 'shared' && sharedWalletCount >= SHARED_WALLET_LIMIT) {
    return LIMIT_SHARED_WALLETS
  }
  if (walletType === 'personal' && personalWalletCount >= PERSONAL_WALLET_LIMIT) {
    return LIMIT_PERSONAL_WALLETS
  }
  return undefined
}

export function walletCreateAtLimit(
  walletType: WalletFormType,
  sharedWalletCount: number,
  personalWalletCount: number,
): boolean {
  return walletCreateLimitHint(walletType, sharedWalletCount, personalWalletCount) !== undefined
}

export function walletCreateIsPersonal(walletType: WalletFormType): boolean {
  return walletType === 'personal'
}
