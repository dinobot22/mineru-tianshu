/**
 * Scalar API Reference 类型声明
 */
declare module '@scalar/api-reference' {
  import { DefineComponent } from 'vue'

  export interface ScalarConfiguration {
    spec?: {
      url?: string
      content?: string | object
    }
    theme?: string
    layout?: 'modern' | 'classic'
    showSidebar?: boolean
    darkMode?: boolean
    hiddenClients?: string[]
    defaultHttpClient?: {
      targetKey?: string
      clientKey?: string
    }
    authentication?: {
      preferredSecurityScheme?: string
      http?: {
        bearer?: {
          token?: string
        }
      }
      apiKey?: {
        token?: string
      }
    }
    servers?: Array<{
      url: string
      description: string
    }>
    customCss?: string
    metaData?: {
      title?: string
      description?: string
      ogDescription?: string
      ogTitle?: string
      ogImage?: string
    }
    searchHotKey?: string
    withDefaultFonts?: boolean
  }

  export const ApiReference: DefineComponent<{
    configuration?: ScalarConfiguration
  }>
}

declare module '@scalar/api-reference/style.css' {
  const content: any
  export default content
}
