import { useEffect } from 'react'
import { create } from 'zustand'

type ChromeStore = {
  tabbarHidden: boolean
  setTabbarHidden: (hidden: boolean) => void
}

export const useChromeStore = create<ChromeStore>((set) => ({
  tabbarHidden: false,
  setTabbarHidden: (tabbarHidden) => set({ tabbarHidden }),
}))

/** Hides the bottom menu while the calling screen is mounted (shopping mode, m3-3). */
export function useHideTabbar(hidden = true): void {
  const setTabbarHidden = useChromeStore((s) => s.setTabbarHidden)
  useEffect(() => {
    setTabbarHidden(hidden)
    return () => setTabbarHidden(false)
  }, [hidden, setTabbarHidden])
}
