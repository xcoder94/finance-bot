import { useRef } from 'react'

import {
  type NavKind,
  type PageDirection,
  pageScreenKey,
  transitionDirection,
} from '../utils/pageTransition'

/**
 * Direction of the enter animation of the current screen. Computed once per screen change and
 * kept stable while the screen stays (a changing class would restart the animation).
 */
export function usePageDirection(pathname: string, navKind: NavKind): PageDirection {
  const ref = useRef<{ key: string; path: string; dir: PageDirection } | null>(null)
  const key = pageScreenKey(pathname)
  if (ref.current === null) {
    ref.current = { key, path: pathname, dir: 'fade' }
  } else if (ref.current.key !== key) {
    ref.current = {
      key,
      path: pathname,
      dir: transitionDirection(ref.current.path, pathname, navKind) ?? 'fade',
    }
  }
  return ref.current.dir
}
