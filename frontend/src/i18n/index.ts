import { createI18n } from 'vue-i18n'

import enUS from './messages/en-US'
import jaJP from './messages/ja-JP'
import zhCN from './messages/zh-CN'

export const SUPPORTED_LOCALES = ['zh-CN', 'en-US', 'ja-JP'] as const
export type AppLocale = (typeof SUPPORTED_LOCALES)[number]

const LOCALE_STORAGE_KEY = 'lui.locale'
const DEFAULT_LOCALE: AppLocale = 'zh-CN'
const FALLBACK_LOCALE: AppLocale = 'en-US'

const messages = {
  'zh-CN': zhCN,
  'en-US': enUS,
  'ja-JP': jaJP,
}

function normalizeLocale(rawLocale?: string | null): AppLocale {
  if (!rawLocale) return DEFAULT_LOCALE

  const lowered = rawLocale.toLowerCase()
  if (lowered.startsWith('zh')) return 'zh-CN'
  if (lowered.startsWith('ja')) return 'ja-JP'
  if (lowered.startsWith('en')) return 'en-US'

  return DEFAULT_LOCALE
}

function resolveInitialLocale(): AppLocale {
  if (typeof window === 'undefined') return DEFAULT_LOCALE

  const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY)
  if (stored && SUPPORTED_LOCALES.includes(stored as AppLocale)) {
    return stored as AppLocale
  }

  return normalizeLocale(window.navigator.language)
}

const initialLocale = resolveInitialLocale()

const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: FALLBACK_LOCALE,
  messages,
}) as any

const globalComposer = i18n.global

function applyDocumentLocale(locale: AppLocale): void {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('lang', locale)
}

export function setLocale(locale: AppLocale): void {
  globalComposer.locale.value = locale

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  }

  applyDocumentLocale(locale)
}

export function getLocale(): AppLocale {
  return globalComposer.locale.value as AppLocale
}

export function translate(key: string, params?: Record<string, unknown>): string {
  return globalComposer.t(key, params)
}

export function translateMessages<T = unknown>(key: string): T {
  return globalComposer.tm(key) as T
}

applyDocumentLocale(initialLocale)

export default i18n
