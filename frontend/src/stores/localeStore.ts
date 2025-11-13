/**
 * 语言切换 Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  type SupportLocale,
  SUPPORT_LOCALES,
  LOCALE_NAMES,
  saveLocale,
  getSavedLocale,
  getBrowserLocale,
} from '@/locales'

export const useLocaleStore = defineStore('locale', () => {
  // 当前语言
  const currentLocale = ref<SupportLocale>(getSavedLocale() || getBrowserLocale())

  // 可用语言列表
  const availableLocales = computed(() => {
    return SUPPORT_LOCALES.map(locale => ({
      value: locale,
      label: LOCALE_NAMES[locale],
    }))
  })

  // 当前语言显示名称
  const currentLocaleName = computed(() => LOCALE_NAMES[currentLocale.value])

  // 切换语言
  function setLocale(locale: SupportLocale) {
    currentLocale.value = locale
    saveLocale(locale)

    // 更新 document.documentElement.lang 属性
    document.documentElement.lang = locale
  }

  return {
    currentLocale,
    currentLocaleName,
    availableLocales,
    setLocale,
  }
})
