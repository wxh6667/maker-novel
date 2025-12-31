import '@fontsource/noto-sans-sc/300.css';
import '@fontsource/noto-sans-sc/400.css';
import '@fontsource/noto-sans-sc/500.css';
import '@fontsource/noto-sans-sc/700.css';

import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Handle token from URL
const urlParams = new URLSearchParams(window.location.search)
const token = urlParams.get('token')

if (token) {
  const authStore = useAuthStore()
  authStore.token = token
  localStorage.setItem('token', token)
  // Clean the URL
  window.history.replaceState({}, document.title, "/")
  authStore.fetchUser()
}

app.mount('#app')
