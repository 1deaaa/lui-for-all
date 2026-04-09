import { createApp } from 'vue'
import { createPinia } from 'pinia'
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

  field.setAttribute('autocomplete', 'off')
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

const app = createApp(App)

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
