import i18next, { type TOptions } from 'i18next'

// Side-effect import: makes sure the shared i18next instance is initialised (init.ts, not index.ts, so test mocks of ../i18n do not skip it) with ru/uz resources.
import './init'

/** Translate outside React components (utils, constants) in the current UI language. */
export function t(key: string, options?: TOptions): string {
  return i18next.t(key, options) as string
}
