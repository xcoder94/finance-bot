import { create } from 'zustand'

import { haptic } from '../telegram/haptic'

type SuccessFlashState = { token: number; flash: () => void }

export const useSuccessFlashStore = create<SuccessFlashState>((set) => ({
  token: 0,
  flash: () => set((s) => ({ token: s.token + 1 })),
}))

/** Successful save: success haptic + the animated tick overlay. */
export function celebrateSave(): void {
  haptic.success()
  useSuccessFlashStore.getState().flash()
}
