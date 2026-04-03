import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Chat',
    component: () => import('@/views/ChatPage.vue'),
    meta: { title: '对话' },
  },
  {
    path: '/projects',
    name: 'Projects',
    component: () => import('@/views/ProjectsPage.vue'),
    meta: { title: '项目' },
  },
  {
    path: '/audit',
    name: 'Audit',
    component: () => import('@/views/AuditPage.vue'),
    meta: { title: '审计' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsPage.vue'),
    meta: { title: '设置' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫 - 更新页面标题
router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'Talk-to-Interface'} - Talk-to-Interface`
  next()
})

export default router
