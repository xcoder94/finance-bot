if (!import.meta.env.DEV) {
  throw new Error('mockTelegramEnv setup is available only in development builds')
}

import { mockTelegramEnv } from '@tma.js/sdk-react'

import { buildDevInitData } from './signInitData'

const DEV_THEME_PARAMS_LIGHT = {
  accent_text_color: '#2481cc',
  bg_color: '#ffffff',
  button_color: '#2481cc',
  button_text_color: '#ffffff',
  destructive_text_color: '#ff3b30',
  header_bg_color: '#ffffff',
  hint_color: '#8e8e93',
  link_color: '#2481cc',
  secondary_bg_color: '#f4f4f5',
  section_bg_color: '#ffffff',
  section_header_text_color: '#2481cc',
  subtitle_text_color: '#8e8e93',
  text_color: '#000000',
} as const

/** Dark palette for local testing — swap `DEV_THEME_PARAMS` assignment to this. */
export const DEV_THEME_PARAMS_DARK = {
  accent_text_color: '#6ab2f2',
  bg_color: '#17212b',
  button_color: '#5288c1',
  button_text_color: '#ffffff',
  destructive_text_color: '#ec3942',
  header_bg_color: '#17212b',
  hint_color: '#708499',
  link_color: '#6ab3f3',
  secondary_bg_color: '#0f0f0f',
  section_bg_color: '#17212b',
  section_header_text_color: '#6ab3f3',
  subtitle_text_color: '#708499',
  text_color: '#f5f5f5',
} as const

const DEV_THEME_PARAMS = DEV_THEME_PARAMS_LIGHT

export async function setupDevTelegramEnv(): Promise<void> {
  const initData = await buildDevInitData()
  const tgWebAppData = new URLSearchParams(initData)

  if (!tgWebAppData.has('signature')) {
    tgWebAppData.set('signature', '')
  }

  mockTelegramEnv({
    launchParams: {
      tgWebAppData,
      tgWebAppThemeParams: DEV_THEME_PARAMS,
      tgWebAppVersion: '8',
      tgWebAppPlatform: 'tdesktop',
    },
  })
}
