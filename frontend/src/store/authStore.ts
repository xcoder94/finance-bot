import { create } from 'zustand'

export type AuthStatus = 'loading' | 'ready' | 'error'

export type AuthErrorType =
  | 'unauthorized'
  | 'not_onboarded'
  | 'removed_from_family'
  | 'pass_failed'
  | 'network'
  | null

export type AuthUser = {
  id: string
  telegramId: number
  familyBudgetId: string
  role: string
  firstName: string | null
  username: string | null
  language: string
  budgetName: string
  memberCount: number
  defaultWalletId: string | null
  eveningReminderEnabled: boolean
  weeklyDigestEnabled: boolean
}

type AuthState = {
  status: AuthStatus
  user: AuthUser | null
  errorType: AuthErrorType
  setLoading: () => void
  setReady: (user: AuthUser) => void
  setError: (errorType: Exclude<AuthErrorType, null>) => void
  setLocalLanguage: (language: string) => void
  setLocalDefaultWallet: (defaultWalletId: string | null) => void
  setLocalEveningReminder: (enabled: boolean) => void
  setLocalWeeklyDigest: (enabled: boolean) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  status: 'loading',
  user: null,
  errorType: null,
  setLoading: () => set({ status: 'loading', errorType: null }),
  setReady: (user) => set({ status: 'ready', user, errorType: null }),
  setError: (errorType) => set({ status: 'error', user: null, errorType }),
  setLocalLanguage: (language) =>
    set((state) =>
      state.user
        ? { user: { ...state.user, language } }
        : state,
    ),
  setLocalDefaultWallet: (defaultWalletId) =>
    set((state) =>
      state.user
        ? { user: { ...state.user, defaultWalletId } }
        : state,
    ),
  setLocalEveningReminder: (eveningReminderEnabled) =>
    set((state) =>
      state.user
        ? { user: { ...state.user, eveningReminderEnabled } }
        : state,
    ),
  setLocalWeeklyDigest: (weeklyDigestEnabled) =>
    set((state) =>
      state.user
        ? { user: { ...state.user, weeklyDigestEnabled } }
        : state,
    ),
}))
