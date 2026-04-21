import { createApp } from 'vue'
import { createPinia } from 'pinia'
import axios from 'axios'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { Icon } from '@iconify/vue'
import i18n from '@/i18n'

import App from './App.vue'
import router from './router'

let autofillFieldCounter = 0

function markFieldNoAutocomplete(field: HTMLInputElement | HTMLTextAreaElement) {
  if (field.hasAttribute('data-allow-autocomplete')) {
    return
  }

  const isPasswordInput = field instanceof HTMLInputElement && field.type.toLowerCase() === 'password'
  field.setAttribute('autocomplete', isPasswordInput ? 'new-password' : 'off')
  field.setAttribute('autocapitalize', 'none')
  field.setAttribute('autocorrect', 'off')
  field.setAttribute('spellcheck', 'false')
  field.setAttribute('data-lpignore', 'true')
  field.setAttribute('data-1p-ignore', 'true')

  const currentName = field.getAttribute('name')
  const needsNeutralName = !currentName || /user|email|account|pass|token|api|key/i.test(currentName)
  if (needsNeutralName) {
    autofillFieldCounter += 1
    field.setAttribute('name', `lui_no_fill_${autofillFieldCounter}`)
  }
}

function disableAutocompleteEverywhere(root: ParentNode) {
  const fields = root.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea')
  fields.forEach((field) => markFieldNoAutocomplete(field))
}

function installNoAutocompleteGuard() {
  disableAutocompleteEverywhere(document)

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach((node) => {
        if (!(node instanceof HTMLElement)) {
          return
        }

        if (node.matches('input, textarea')) {
          markFieldNoAutocomplete(node as HTMLInputElement | HTMLTextAreaElement)
          return
        }

        disableAutocompleteEverywhere(node)
      })
    }
  })

  observer.observe(document.body, { childList: true, subtree: true })
}

function isAuthApiUrl(url: unknown): boolean {
  if (typeof url !== 'string' || !url) {
    return false
  }

  try {
    const parsed = new URL(url, window.location.origin)
    return parsed.pathname.startsWith('/api/auth/')
  } catch {
    return url.includes('/api/auth/')
  }
}

const app = createApp(App)

// ── axios 全局拦截器：JWT Token 注入 + 401 自动登出 ──
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('lui_jwt')
  if (token && config.url?.startsWith('/api')) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      // 不在 auth 相关接口上触发登出（避免循环）
      if (!isAuthApiUrl(url)) {
        const token = localStorage.getItem('lui_jwt')
        let isUser = false
        let userSlug = ''
        if (token) {
          try {
            const base64 = token.split('.')[1]
            const json = decodeURIComponent(
              atob(base64.replace(/-/g, '+').replace(/_/g, '/'))
                .split('')
                .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
                .join(''),
            )
            const payload = JSON.parse(json)
            isUser = payload.sub === 'lui-user'
            userSlug = payload.project_slug || ''
          } catch { /* ignore */ }
        }
        localStorage.removeItem('lui_jwt')
        if (isUser && userSlug) {
          window.location.href = `/${userSlug}/login`
        } else if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  },
)

// 注册 Iconify 全局组件
app.component('Icon', Icon)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(i18n)
app.use(router)
app.use(ElementPlus)

app.mount('#app')
installNoAutocompleteGuard()
