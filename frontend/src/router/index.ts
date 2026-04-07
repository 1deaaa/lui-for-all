import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { translate } from '@/i18n'

const routes: RouteRecordRaw[] = [
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
    meta: { titleKey: 'routes.projects' },
  },
  {
    path: '/audit',
    name: 'Audit',
    component: () => import('@/views/AuditPage.vue'),
    meta: { titleKey: 'routes.audit' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsPage.vue'),
    meta: { titleKey: 'routes.settings' },
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

// 路由守卫 - 更新页面标题
router.beforeEach((to, _from, next) => {
  updateDocumentTitle(to.meta.titleKey as string | undefined)
  next()
})

export default router
