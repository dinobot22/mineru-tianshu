import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import i18n from './locales'
import { useAuthStore } from './stores'
import './style.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(i18n)

// 初始化认证状态
const authStore = useAuthStore()
authStore.initialize().then(() => {
  app.mount('#app')
})
