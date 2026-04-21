import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { translate } from '@/i18n'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginPage.vue'),
    meta: { titleKey: 'routes.login', public: true },
  },
  {
    path: '/',
    name: 'Chat',
    component: () => import('@/views/ChatPage.vue'),
    meta: { titleKey: 'routes.chat' },
  },
  {
    path: '/projects',
    name: 'Projects',
    component: () => import('@/views/ProjectsPage.vue'),
    meta: { titleKey: 'routes.projects', adminOnly: true },
  },
  {
    path: '/audit',
    name: 'Audit',
    component: () => import('@/views/AuditPage.vue'),
    meta: { titleKey: 'routes.audit', adminOnly: true },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsPage.vue'),
    meta: { titleKey: 'routes.settings', adminOnly: true },
  },
  // ── 终端用户路由 ──
  {
    path: '/:slug/login',
    name: 'UserLogin',
    component: () => import('@/views/UserLoginPage.vue'),
    meta: { titleKey: 'routes.login', public: true },
  },
  {
    path: '/:slug',
    name: 'UserChat',
    component: () => import('@/views/ChatPage.vue'),
    meta: { titleKey: 'routes.chat', userOnly: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export function updateDocumentTitle(titleKey?: string): void {
  const pageTitle = titleKey ? translate(titleKey) : translate('app.name')
  document.title = translate('app.pageTitle', { page: pageTitle })
}

/** 解码 JWT payload（不验证签名，仅读取字段） */
function decodeJWTPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split('.')[1]
    const json = decodeURIComponent(
      atob(base64.replace(/-/g, '+').replace(/_/g, '/'))
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join(''),
    )
    return JSON.parse(json)
  } catch {
    return null
  }
}

/** 获取当前 JWT 的 subject 类型 */
function getJWTSubject(): 'admin' | 'user' | null {
  const token = localStorage.getItem('lui_jwt')
  if (!token) return null
  const payload = decodeJWTPayload(token)
  if (!payload) return null
  return payload.sub === 'lui-user' ? 'user' : payload.sub === 'lui-admin' ? 'admin' : null
}

// 路由守卫 - 更新页面标题 + JWT 鉴权
router.beforeEach((to, _from, next) => {
  updateDocumentTitle(to.meta.titleKey as string | undefined)

  const isPublicRoute = to.meta.public === true
  const hasToken = !!localStorage.getItem('lui_jwt')
  const subject = getJWTSubject()

  if (!isPublicRoute && !hasToken) {
    // 未登录：用户路由跳用户登录页，管理员路由跳管理员登录页
    if (to.meta.userOnly) {
      const slug = to.params.slug as string
      next({ name: 'UserLogin', params: { slug } })
    } else {
      next({ name: 'Login' })
    }
  } else if (isPublicRoute && hasToken) {
    // 已登录访问登录页：跳转到对应首页
    if (to.name === 'Login' && subject === 'admin') {
      next({ name: 'Chat' })
    } else if (to.name === 'UserLogin' && subject === 'user') {
      const slug = (to.params.slug as string) || localStorage.getItem('lui_user_slug') || ''
      next({ name: 'UserChat', params: { slug } })
    } else {
      next()
    }
  } else if (subject === 'user' && to.meta.adminOnly) {
    // 终端用户不能访问管理员页面
    const slug = localStorage.getItem('lui_user_slug') || ''
    next({ name: 'UserChat', params: { slug } })
  } else if (subject === 'admin' && to.meta.userOnly) {
    // 管理员不能访问用户路由
    next({ name: 'Chat' })
  } else {
    next()
  }
})

export default router
