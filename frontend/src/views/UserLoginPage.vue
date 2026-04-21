<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const route = useRoute()
const { t, locale } = useI18n()

// ── 状态 ──
const slug = computed(() => (route.params.slug as string) || '')
const loading = ref(false)
const resolvingSlug = ref(true)
const projectName = ref('')
const projectId = ref('')
const username = ref('')
const password = ref('')
const localeOptions = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' },
  { value: 'ja-JP', label: '日本語' },
]

// ── 解析 slug ──
async function resolveSlug() {
  if (!slug.value) {
    resolvingSlug.value = false
    return
  }
  try {
    const res = await axios.get(`/api/projects/resolve-slug/${slug.value}`)
    projectName.value = res.data.name
    projectId.value = res.data.project_id
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '项目不存在或未开放用户登录')
  } finally {
    resolvingSlug.value = false
  }
}

// ── 用户登录 ──
async function handleUserLogin() {
  if (!username.value || !password.value || loading.value) return
  loading.value = true
  try {
    const res = await axios.post('/api/auth/user-login', {
      project_slug: slug.value,
      username: username.value,
      password: password.value,
    })
    localStorage.setItem('lui_jwt', res.data.token)
    localStorage.setItem('lui_user_project_id', res.data.project_id)
    localStorage.setItem('lui_user_slug', res.data.project_slug || slug.value)
    localStorage.setItem('lui_user_project_name', res.data.project_name)
    router.replace({ name: 'UserChat', params: { slug: slug.value } })
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '登录失败')
  } finally {
    loading.value = false
  }
}

function handleLocaleChange(val: string) {
  locale.value = val
}

onMounted(() => {
  resolveSlug()
  // 逐阶段触发动画
  setTimeout(() => { animPhase.value = 1 }, 100)
  setTimeout(() => { animPhase.value = 2 }, 800)
  setTimeout(() => { animPhase.value = 3 }, 1400)
})

// ── 动画控制 ──
const animPhase = ref(0)
</script>

<template>
  <div class="user-login-page">
    <!-- 背景装饰线条 -->
    <div class="bg-lines">
      <div class="bg-line line-1"></div>
      <div class="bg-line line-2"></div>
      <div class="bg-line line-3"></div>
    </div>

    <!-- 语言切换 -->
    <div class="locale-switcher">
      <select :value="locale" @change="handleLocaleChange(($event.target as HTMLSelectElement).value)" class="locale-select">
        <option v-for="opt in localeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>
    </div>

    <!-- 加载状态 -->
    <div v-if="resolvingSlug" class="login-loading">
      <div class="loader-ring"></div>
    </div>

    <!-- 主内容区 -->
    <div v-else-if="projectName" class="login-content">
      <!-- Logo 动画区 -->
      <div class="logo-anim-wrap">
        <svg class="login-logo" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" width="64" height="64">
          <defs>
            <mask id="user-glow-mask">
              <rect width="100" height="100" fill="white" />
              <circle cx="50" cy="50" r="24" fill="black" />
            </mask>
          </defs>
          <polygon
            class="hex-outline"
            :class="{ draw: animPhase >= 1 }"
            points="50,6 88,28 88,72 50,94 12,72 12,28"
            fill="none"
            stroke="currentColor"
            stroke-width="3.5"
            stroke-linejoin="round"
          />
          <g mask="url(#user-glow-mask)">
            <line class="skeleton-line front-line" :class="{ draw: animPhase >= 2 }"
              x1="50" y1="50" x2="88" y2="28" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
            <line class="skeleton-line front-line" :class="{ draw: animPhase >= 2 }"
              x1="50" y1="50" x2="50" y2="94" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
            <line class="skeleton-line front-line" :class="{ draw: animPhase >= 2 }"
              x1="50" y1="50" x2="12" y2="28" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
          </g>
          <path
            class="star-burst"
            :class="{ appear: animPhase >= 3 }"
            d="M 50 28 C 46 46, 46 46, 28 50 C 46 54, 46 54, 50 72 C 54 54, 54 54, 72 50 C 54 46, 54 46, 50 28 Z"
            fill="currentColor"
          />
        </svg>
      </div>

      <!-- 项目名标题 -->
      <h1 class="login-title">{{ projectName }}</h1>
      <p class="login-subtitle">{{ t('login.loginSubtitle') }}</p>

      <!-- 表单 -->
      <form class="login-form" @submit.prevent="handleUserLogin">
        <div class="field-group">
          <label class="field-label">{{ t('userLogin.usernameLabel') || '用户名' }}</label>
          <input
            v-model="username"
            type="text"
            class="field-input"
            :placeholder="t('userLogin.usernamePlaceholder') || '请输入用户名'"
            autocomplete="username"
          />
        </div>
        <div class="field-group">
          <label class="field-label">{{ t('login.passwordLabel') }}</label>
          <input
            v-model="password"
            type="password"
            class="field-input"
            :placeholder="t('login.passwordPlaceholder')"
            autocomplete="current-password"
          />
        </div>
        <button
          type="submit"
          class="submit-btn"
          :disabled="!username || !password || loading"
          :class="{ loading }"
        >
          <span v-if="loading" class="btn-loader"></span>
          <span v-else>{{ t('login.loginButton') }}</span>
        </button>
      </form>
    </div>

    <!-- 项目不存在 -->
    <div v-else class="login-content">
      <h1 class="login-title">404</h1>
      <p class="login-subtitle">项目不存在或未开放用户登录</p>
    </div>
  </div>
</template>

<style scoped>
.user-login-page {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
  position: relative;
  overflow: hidden;
}

.bg-lines {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.bg-line {
  position: absolute;
  background: #0f0f0f;
}

.line-1 { width: 1px; height: 40vh; top: 0; left: 20%; opacity: 0.04; }
.line-2 { width: 1px; height: 50vh; bottom: 0; left: 60%; opacity: 0.03; }
.line-3 { height: 1px; width: 35vw; top: 30%; left: 0; opacity: 0.04; }

.locale-switcher {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
}

.locale-select {
  border: 1px solid #e5e5e5;
  background: #ffffff;
  color: #737373;
  font-size: 12px;
  padding: 4px 8px;
  outline: none;
  cursor: pointer;
  border-radius: 0;
}

.locale-select:focus {
  border-color: #0f0f0f;
}

.login-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 360px;
  max-width: 90vw;
  position: relative;
  z-index: 1;
  animation: contentFadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both;
}

@keyframes contentFadeIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.logo-anim-wrap {
  margin-bottom: 24px;
  color: #0f0f0f;
}

.login-logo {
  display: block;
}

.hex-outline {
  stroke-dasharray: 340;
  stroke-dashoffset: 340;
  transition: stroke-dashoffset 0.7s cubic-bezier(0.65, 0, 0.35, 1);
}
.hex-outline.draw {
  stroke-dashoffset: 0;
}

.skeleton-line {
  stroke-dasharray: 55;
  stroke-dashoffset: 55;
  transition: stroke-dashoffset 0.6s cubic-bezier(0.65, 0, 0.35, 1);
}
.skeleton-line.draw {
  stroke-dashoffset: 0;
}
.skeleton-line.front-line:nth-child(2) {
  transition-delay: 0.12s;
}
.skeleton-line.front-line:nth-child(3) {
  transition-delay: 0.24s;
}

.star-burst {
  opacity: 0;
  transform-origin: 50px 50px;
  transform: scale(0.7);
  transition: opacity 0.5s ease, transform 0.7s cubic-bezier(0.16, 1, 0.3, 1);
}
.star-burst.appear {
  opacity: 1;
  transform: scale(1);
}

.login-title {
  font-family: var(--font-ui);
  font-size: 22px;
  font-weight: 700;
  color: #0f0f0f;
  letter-spacing: -0.02em;
  margin-bottom: 6px;
  text-align: center;
}

.login-subtitle {
  font-size: 13px;
  color: #737373;
  margin-bottom: 32px;
  text-align: center;
  line-height: 1.5;
}

.login-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: #0f0f0f;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.field-input {
  width: 100%;
  height: 44px;
  padding: 0 14px;
  border: 1px solid #e5e5e5;
  background: #ffffff;
  color: #0f0f0f;
  font-size: 14px;
  font-family: var(--font-mono);
  letter-spacing: 0.04em;
  outline: none;
  transition: border-color 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  border-radius: 0;
}

.field-input::placeholder {
  color: #a3a3a3;
  font-family: var(--font-main);
  letter-spacing: 0;
}

.field-input:focus {
  border-color: #0f0f0f;
}

.submit-btn {
  width: 100%;
  height: 44px;
  background: #0f0f0f;
  color: #ffffff;
  border: none;
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-ui);
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: background-color 0.25s ease, opacity 0.25s ease;
  border-radius: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
}

.submit-btn:hover:not(:disabled) {
  background: #262626;
}

.submit-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.submit-btn.loading {
  pointer-events: none;
}

.btn-loader {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.login-loading {
  display: flex;
  align-items: center;
  justify-content: center;
}

.loader-ring {
  width: 32px;
  height: 32px;
  border: 2px solid #e5e5e5;
  border-top-color: #0f0f0f;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
</style>
