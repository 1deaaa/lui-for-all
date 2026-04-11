<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useWindowSize } from '@vueuse/core'
import { ChatDotRound, Folder, Document, Setting, SwitchButton } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import ja from 'element-plus/es/locale/lang/ja'
import BrandLogo from '@/components/BrandLogo.vue'
import { type AppLocale } from '@/i18n'
import { updateDocumentTitle } from '@/router'

const route = useRoute()
const projectStore = useProjectStore()
const { t, locale } = useI18n()
const currentLocale = computed(() => locale.value as AppLocale)

const elementPlusLocaleMap: Record<AppLocale, typeof zhCn> = {
  'zh-CN': zhCn,
  'en-US': en,
  'ja-JP': ja,
}

const elementPlusLocale = computed(() => elementPlusLocaleMap[currentLocale.value] || zhCn)

// 响应式窗口
const { width } = useWindowSize()
// 全局断点阈值，控制移动端样式切换点
const MOBILE_BREAKPOINT = 768
const isMobile = computed(() => width.value <= MOBILE_BREAKPOINT)

// 菜单状态控制
const drawerVisible = ref(false)

// 当前激活的菜单
const activeMenu = computed(() => route.path)

// 供 Menu 使用的核心导航结构
const menuItems = computed(() => [
  { index: '/', icon: ChatDotRound, title: t('routes.chat') },
  { index: '/projects', icon: Folder, title: t('routes.projects') },
  { index: '/audit', icon: Document, title: t('routes.audit') },
  { index: '/settings', icon: Setting, title: t('routes.settings') },
])

function clearSessionCaches() {
  const prefixes = ['lui_route_map_', 'lui_caps_', 'lui_history_']
  const keysToRemove: string[] = []

  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index)
    if (!key) continue
    if (key === 'lui_jwt' || prefixes.some((prefix) => key.startsWith(prefix))) {
      keysToRemove.push(key)
    }
  }

  keysToRemove.forEach((key) => localStorage.removeItem(key))
}

function handleLogout() {
  clearSessionCaches()
  drawerVisible.value = false
  window.location.replace('/login')
}

watch(
  [() => route.fullPath, () => locale.value],
  () => {
    updateDocumentTitle(route.meta.titleKey as string | undefined)
  },
  { immediate: true },
)

// 登录页不加载项目数据
const isLoginPage = computed(() => route.path === '/login')
watch(isLoginPage, (isLogin) => {
  const hasToken = !!localStorage.getItem('lui_jwt')
  if (!isLogin && hasToken) {
    projectStore.fetchProjects()
  }
}, { immediate: true })
</script>

<template>
  <el-config-provider :locale="elementPlusLocale">
    <!-- 登录页：全屏无侧边栏 -->
    <div v-if="isLoginPage" class="login-fullscreen">
      <router-view v-slot="{ Component }">
        <transition name="fade-slide" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>

    <!-- 非登录页：正常布局 -->
    <el-container v-else class="app-container" :class="{ 'no-padding-top': isMobile && route.path === '/' }">
      <!-- 移动端顶部 Navbar (合并策略：只有在非主聊天页时才显示独立顶栏) -->
      <div v-if="isMobile && route.path !== '/'" class="mobile-navbar">
        <div class="logo-mobile" @click="drawerVisible = true" style="cursor: pointer;">
          <BrandLogo :size="24" />
        </div>
      </div>

      <el-drawer
        v-model="drawerVisible"
        direction="ltr"
        size="180px"
        :with-header="false"
        class="mobile-drawer"
      >
        <div class="drawer-content">
          <div class="logo drawer-logo">
            <BrandLogo :size="24" style="margin-right:8px" />{{ t('app.name') }}
          </div>
          <el-menu :default-active="activeMenu" router class="drawer-menu" @select="drawerVisible = false">
            <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>
          </el-menu>
          <div class="drawer-footer">
            <el-tooltip :content="t('app.logout')" placement="right">
              <button class="logout-btn" type="button" :aria-label="t('app.logout')" @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>
              </button>
            </el-tooltip>
          </div>
        </div>
      </el-drawer>

      <!-- 桌面侧边栏 (极简固定) -->
      <el-aside v-if="!isMobile" width="64px" class="app-aside">
        <div class="logo">
          <BrandLogo :size="30" />
        </div>

        <el-menu
          :default-active="activeMenu"
          :collapse="true"
          router
          class="app-menu flat-menu"
        >
          <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.title }}</template>
          </el-menu-item>
        </el-menu>

        <div class="aside-footer">
          <el-tooltip :content="t('app.logout')" placement="right">
            <button class="logout-btn" type="button" :aria-label="t('app.logout')" @click="handleLogout">
              <el-icon><SwitchButton /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </el-aside>

      <!-- 主内容区 -->
      <el-container class="main-container">
        <el-main class="app-main">
          <router-view v-slot="{ Component }">
            <transition name="fade-slide" mode="out-in">
              <component :is="Component" @open-drawer="drawerVisible = true" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </el-config-provider>
</template>

<style>
/* ================= 全局设计变量 ================= */
:root {
  --bg-color-main: #ffffff;
  --bg-color-sidebar: #f9f9f9;
  --border-color-light: #e5e5e5;
  
  /* 直角设计，极简黑白灰 */
  --color-primary: #171717;     /* 深玄黑 */
  --color-primary-light: #f4f4f4; 
  --color-text-primary: #0f0f0f;
  --color-text-secondary: #737373;
  
  /* 覆盖 Element Plus 默认蓝色主题 */
  --el-color-primary: #0f0f0f;
  --el-color-primary-light-3: #3f3f3f;
  --el-color-primary-light-5: #6f6f6f;
  --el-color-primary-light-7: #a3a3a3;
  --el-color-primary-light-8: #cccccc;
  --el-color-primary-light-9: #e5e5e5;
  --el-color-primary-dark-2: #000000;
  
  /* 阴影尽量克制，平面化设计 */
  --shadow-sm: none;
  --shadow-md: none;
  --shadow-lg: 0 4px 20px rgba(0, 0, 0, 0.05);
  --shadow-hover: 0 8px 30px rgba(0, 0, 0, 0.08); /* 仅在高级浮岛使用 */
  
  /* 强制直角风格 */
  --radius-lg: 0px;
  --radius-md: 0px;
  --radius-sm: 0px;
  
  /* 动画曲线加强专业感 */
  --transition-smooth: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);

  /* 全局字体定义：双语回退（英文优先，中文兜底） */
  --font-main: "Inter", "Noto Sans SC", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-ui: "Outfit", "Noto Sans SC", sans-serif;
  --font-mono: "JetBrains Mono", "Fira Code", "Noto Sans SC", monospace;
}

/* ================= 基础重置 ================= */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  /* 默认使用 Inter，系统备选 */
  font-family: var(--font-main);
  -webkit-font-smoothing: antialiased;
  letter-spacing: -0.015em; /* 增加紧致高级感 */
}

/* 航天/智能感 UI 关键标签 */
.logo, .el-button, .sidebar-label, .confirm-title {
  font-family: var(--font-ui) !important;
}

/* 技术/数据类极客感显示 */
code, pre, .mono-text, .http-tag, .http-badge {
  font-family: var(--font-mono) !important;
  letter-spacing: 0 !important;
}

html, body, #app {
  height: 100%;
  background-color: var(--bg-color-main);
  color: var(--color-text-primary);
  overflow: hidden;
}

/* ================= 动画特效 ================= */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* ================= 骨架布局 ================= */

.login-fullscreen {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.app-container {
  height: 100%;
}

.main-container {
  background-color: var(--bg-color-main);
  position: relative;
  z-index: 1;
}

.app-main {
  --el-main-padding: 0;
  padding: 0 !important;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--bg-color-main);
}

@media (max-width: 768px) {
  .app-main {
    padding: 16px;
  }
}

/* ================= 移动端导航 ================= */
.mobile-navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 60px;
  padding: 0 20px;
  background-color: rgba(255, 255, 255, 0.85);
  backdrop-filter: var(--sidebar-blur);
  border-bottom: 1px solid var(--border-color-light);
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
}

.logo-mobile {
  display: flex;
  align-items: center;
}

.logo-mobile .logo-text {
  font-weight: 800;
  font-size: 1.2rem;
  background: linear-gradient(135deg, var(--color-primary), #00d2ff);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.menu-btn {
  color: var(--color-text-primary);
}

/* 填补移动端 Navbar 高度 */
@media (max-width: 768px) {
  .app-container {
    padding-top: 60px;
  }
  .app-container.no-padding-top {
    padding-top: 0 !important;
  }
}

/* ================= 桌面侧边栏 (极简平面) ================= */
.app-aside {
  background-color: var(--bg-color-sidebar);
  border-right: 1px solid var(--border-color-light);
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 10;
  overflow: hidden;
}

.logo {
  height: 64px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-primary);
}

.drawer-logo {
  border-bottom: 1px solid var(--border-color-light);
  font-size: 1.2rem;
  font-weight: bold;
}

.drawer-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.drawer-footer {
  margin-top: auto;
  padding: 16px 0 18px;
  border-top: 1px solid var(--border-color-light);
  display: flex;
  justify-content: flex-start;
}

/* ================= 组件复写: 平面直角菜单 ================= */
.el-menu {
  border-right: none !important;
  background-color: transparent !important;
}

.app-menu {
  flex: 1;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.aside-footer {
  margin-top: auto;
  width: 100%;
  padding: 16px 0 18px;
  border-top: 1px solid var(--border-color-light);
  display: flex;
  justify-content: center;
}

.logout-btn {
  width: 44px;
  height: 44px;
  border: 1px solid var(--border-color-light);
  background: #ffffff;
  color: var(--color-text-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.25s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.25s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  padding: 0;
}

.logout-btn:hover {
  background-color: #f0f0f0;
  border-color: #d4d4d4;
  color: var(--color-text-primary);
}

.logout-btn:active {
  background-color: #ebebeb;
}

.logout-btn .el-icon {
  font-size: 18px;
}

.drawer-menu {
  flex: 1;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 8px; /* 移动端抽屉项间距稍微紧凑 */
}

/* 针对桌面超窄边栏定制方块按钮 */
.app-menu .el-menu-item {
  color: var(--color-text-secondary) !important;
  border-radius: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  width: 44px !important;
  height: 44px !important;
  display: flex !important;
  align-items: center;
  justify-content: center;
  transition: color 0.25s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

.app-menu.el-menu--collapse .el-menu-item .el-tooltip__trigger {
  padding: 0 !important;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
}

.app-menu .el-menu-item:hover {
  background-color: #f0f0f0 !important;
  color: var(--color-text-primary) !important;
}

.app-menu .el-menu-item.is-active {
  background-color: rgba(0, 0, 0, 0.04) !important;
  color: #0f0f0f !important;
  font-weight: 600;
  box-shadow: inset 3px 0 0 0 #0f0f0f;
}

.app-menu .el-menu-item .el-icon {
  font-size: 20px !important;
  margin: 0 !important;
}

/* 针对移动端全宽抽屉正常菜单 */
.drawer-menu .el-menu-item {
  height: 48px !important;
  border-radius: 8px !important;
  margin: 0 12px !important;
  padding: 0 12px !important;
  color: var(--color-text-secondary) !important;
  transition: all 0.2s;
}

.drawer-menu .el-menu-item:hover {
  background-color: #f0f0f0 !important;
  color: var(--color-text-primary) !important;
}

.drawer-menu .el-menu-item.is-active {
  background-color: rgba(0, 0, 0, 0.04) !important;
  color: #0f0f0f !important;
  font-weight: 600;
}

.drawer-menu .el-menu-item .el-icon {
  font-size: 20px !important;
  margin-right: 12px !important;
}

/* ================= 全局 Element-Plus 重构 (直角平铺) ================= */

.el-card {
  border-radius: 0 !important;
  border: 1px solid var(--border-color-light) !important;
  box-shadow: none !important;
  transition: border-color 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
  background-color: #ffffff !important;
}

.el-card:hover {
  border-color: var(--color-text-primary) !important;
}

.el-card__header {
  border-bottom: 1px solid var(--border-color-light) !important;
  padding: 16px 20px !important;
  font-weight: 600 !important;
  color: var(--color-text-primary) !important;
  background: #fcfcfc !important;
}

.el-button {
  border-radius: 0 !important;
  font-weight: 500 !important;
  box-shadow: none !important;
  transition: background-color 0.25s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.25s cubic-bezier(0.16, 1, 0.3, 1), color 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

.el-button--primary {
  background-color: var(--color-primary) !important;
  border-color: var(--color-primary) !important;
  color: #ffffff !important;
}

.el-button--primary:hover, .el-button--primary:focus {
  background-color: #333333 !important;
  border-color: #333333 !important;
  transform: none !important;
  box-shadow: none !important;
}

.el-input__wrapper, .el-textarea__inner {
  border-radius: 0 !important;
  box-shadow: 0 0 0 1px var(--border-color-light) inset !important;
  background-color: #ffffff !important;
  transition: box-shadow 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

.el-input__wrapper:focus-within, .el-textarea__inner:focus {
  box-shadow: 0 0 0 1px var(--color-primary) inset !important;
}
</style>
