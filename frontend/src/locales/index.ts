/**
 * 国际化配置
 */
import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'

// 支持的语言列表
export const SUPPORT_LOCALES = ['zh-CN', 'en-US'] as const
export type SupportLocale = (typeof SUPPORT_LOCALES)[number]

// 语言显示名称
export const LOCALE_NAMES: Record<SupportLocale, string> = {
  'zh-CN': '简体中文',
  'en-US': 'English',
}

// 获取浏览器语言
export function getBrowserLocale(): SupportLocale {
  const browserLang = navigator.language || 'zh-CN'

  // 精确匹配
  if (SUPPORT_LOCALES.includes(browserLang as SupportLocale)) {
    return browserLang as SupportLocale
  }

  // 模糊匹配（例如 zh-TW -> zh-CN, en-GB -> en-US）
  const langPrefix = browserLang.split('-')[0]
  const matched = SUPPORT_LOCALES.find(locale => locale.startsWith(langPrefix))

  return matched || 'zh-CN' // 默认中文
}

// 从 localStorage 获取保存的语言
export function getSavedLocale(): SupportLocale | null {
  const saved = localStorage.getItem('locale')
  if (saved && SUPPORT_LOCALES.includes(saved as SupportLocale)) {
    return saved as SupportLocale
  }
  return null
}

// 保存语言到 localStorage
export function saveLocale(locale: SupportLocale) {
  localStorage.setItem('locale', locale)
}

// 创建 i18n 实例
const i18n = createI18n({
  legacy: false, // 使用 Composition API 模式
  locale: getSavedLocale() || getBrowserLocale(), // 优先使用保存的语言，否则使用浏览器语言
  fallbackLocale: 'zh-CN', // 回退语言
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
  globalInjection: true, // 全局注入 $t
})

export default i18n
