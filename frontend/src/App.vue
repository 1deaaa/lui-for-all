<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useWindowSize } from '@vueuse/core'
import { ChatDotRound, Folder, Document, Setting, Fold, Expand, Menu as MenuIcon } from '@element-plus/icons-vue'

const route = useRoute()
const projectStore = useProjectStore()

// 响应式窗口
const { width } = useWindowSize()
const isMobile = computed(() => width.value <= 768)

// 菜单状态控制
const isCollapse = ref(false)
const drawerVisible = ref(false)

// 自动响应移动端模式
watch(isMobile, (newVal) => {
  if (newVal) {
    isCollapse.value = false // 移动端用 Drawer 显示完整菜单
  }
})

// 当前激活的菜单
const activeMenu = computed(() => route.path)

// 切换桌面端侧边栏
const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}

// 供 Menu 使用的核心导航结构
const menuItems = [
  { index: '/', icon: ChatDotRound, title: '对话' },
  { index: '/projects', icon: Folder, title: '项目' },
  { index: '/audit', icon: Document, title: '审计' },
  { index: '/settings', icon: Setting, title: '设置' }
]

projectStore.fetchProjects()
</script>

<template>
  <el-container class="app-container">
    <!-- 移动端顶部 Navbar -->
    <div v-if="isMobile" class="mobile-navbar">
      <div class="logo-mobile">LUI ✨</div>
      <el-button text class="menu-btn" @click="drawerVisible = true">
        <el-icon :size="20"><MenuIcon /></el-icon>
      </el-button>
    </div>

    <!-- 移动端 Drawer 导航 -->
    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      size="240px"
      :with-header="false"
      class="mobile-drawer"
    >
      <div class="logo drawer-logo">Talk-to-Interface</div>
      <el-menu :default-active="activeMenu" router class="drawer-menu" @select="drawerVisible = false">
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <!-- 桌面侧边栏 -->
    <el-aside v-if="!isMobile" :width="isCollapse ? '80px' : '260px'" class="app-aside glass-effect">
      <div class="logo">
        <span v-if="!isCollapse" class="logo-text">LUI Core</span>
        <span v-else class="logo-icon">✨</span>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        router
        class="app-menu modern-menu"
      >
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
      
      <div class="sidebar-toggle" @click="toggleSidebar">
        <el-icon>
          <Fold v-if="!isCollapse" />
          <Expand v-else />
        </el-icon>
      </div>
    </el-aside>
    
    <!-- 主内容区 -->
    <el-container class="main-container">
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style>
/* ================= 全局设计变量 ================= */
:root {
  --bg-color-main: #fcfcfc;
  --bg-color-glass: rgba(255, 255, 255, 0.75);
  --sidebar-blur: blur(20px);
  --border-color-light: #eaedf1;
  
  /* oklch 高阶动态色彩 */
  --color-primary: oklch(0.6 0.15 250);     /* 主亮蓝 */
  --color-primary-light: oklch(0.9 0.05 250); 
  --color-text-primary: #1a1a1c;
  --color-text-secondary: #64748b;
  
  /* 阴影及微动效 */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
  --shadow-hover: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02);
  
  --radius-lg: 16px;
  --radius-md: 12px;
  --radius-sm: 8px;
  
  --transition-smooth: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ================= 基础重置 ================= */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
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
  transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
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
.app-container {
  height: 100%;
}

.main-container {
  background-color: var(--bg-color-main);
  position: relative;
  z-index: 1;
}

.app-main {
  padding: 24px;
  /* 为卡片的阴影等留出呼吸空间 */
  padding-bottom: 40px; 
  overflow-y: auto;
  overflow-x: hidden;
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
  font-weight: 800;
  font-size: 1.2rem;
  background: linear-gradient(135deg, var(--color-primary), #00d2ff);
  -webkit-background-clip: text;
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
}

/* ================= 桌面侧边栏 (玻璃态) ================= */
.app-aside {
  background-color: var(--bg-color-glass);
  backdrop-filter: var(--sidebar-blur);
  border-right: 1px solid var(--border-color-light);
  display: flex;
  flex-direction: column;
  transition: var(--transition-smooth);
  box-shadow: 1px 0 10px rgba(0,0,0,0.02);
  z-index: 10;
}

.logo {
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-primary);
  border-bottom: 1px solid transparent;
}

.logo-text {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.5px;
}

.logo-icon {
  font-size: 24px;
}

.drawer-logo {
  border-bottom: 1px solid var(--border-color-light);
  font-size: 1.2rem;
  font-weight: bold;
}

/* ================= 组件复写: 现代化菜单 ================= */
.el-menu {
  border-right: none !important;
  background-color: transparent !important;
}

.app-menu, .drawer-menu {
  flex: 1;
  padding: 12px 8px;
}

.el-menu-item {
  color: var(--color-text-secondary) !important;
  border-radius: var(--radius-md) !important;
  margin-bottom: 8px !important;
  height: 50px !important;
  line-height: 50px !important;
  font-weight: 500;
  transition: var(--transition-smooth) !important;
}

.el-menu-item:hover {
  background-color: var(--bg-color-main) !important;
  color: var(--color-text-primary) !important;
}

.el-menu-item.is-active {
  background-color: var(--color-primary-light) !important;
  color: var(--color-primary) !important;
  font-weight: 600;
}

.el-menu-item .el-icon {
  font-size: 20px !important;
  margin-right: 12px !important;
}

/* ================= 侧边栏 Toggle 控制器 ================= */
.sidebar-toggle {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-top: 1px solid var(--border-color-light);
  transition: var(--transition-smooth);
}

.sidebar-toggle:hover {
  background-color: var(--color-primary-light);
  color: var(--color-primary);
}

/* ================= 全局 Element-Plus 卡片重构 ================= */
.el-card {
  border-radius: var(--radius-lg) !important;
  border: 1px solid var(--border-color-light) !important;
  box-shadow: var(--shadow-md) !important;
  transition: var(--transition-smooth) !important;
  background-color: rgba(255, 255, 255, 0.9) !important;
  backdrop-filter: blur(10px) !important;
}

.el-card:hover {
  box-shadow: var(--shadow-hover) !important;
  transform: translateY(-2px);
}

.el-card__header {
  border-bottom-color: var(--border-color-light) !important;
  padding: 16px 20px !important;
  font-weight: 600 !important;
  color: var(--color-text-primary) !important;
}

.el-button {
  border-radius: var(--radius-md) !important;
  font-weight: 500 !important;
  transition: var(--transition-smooth) !important;
}

.el-button--primary {
  background-color: var(--color-primary) !important;
  border-color: var(--color-primary) !important;
  box-shadow: 0 4px 6px rgba(100, 100, 250, 0.2) !important;
}

.el-button--primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 12px rgba(100, 100, 250, 0.3) !important;
}

.el-input__wrapper, .el-textarea__inner {
  border-radius: var(--radius-md) !important;
  box-shadow: 0 0 0 1px var(--border-color-light) inset !important;
  background-color: var(--bg-color-main) !important;
}

.el-input__wrapper:focus-within, .el-textarea__inner:focus {
  box-shadow: 0 0 0 1px var(--color-primary) inset, 0 0 0 4px var(--color-primary-light) !important;
}
</style>
