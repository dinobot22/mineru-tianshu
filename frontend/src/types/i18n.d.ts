/**
 * Vue I18n 类型声明
 */
import 'vue-i18n'
import type zhCN from '@/locales/zh-CN'

type MessageSchema = typeof zhCN

declare module 'vue-i18n' {
  export interface DefineLocaleMessage extends MessageSchema {}
}
