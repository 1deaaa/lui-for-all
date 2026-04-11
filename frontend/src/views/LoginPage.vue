<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()

// ── 状态 ──
const isSetup = ref(true) // true=首次设置密码, false=登录
const loading = ref(false)
const checkingStatus = ref(true)
const password = ref('')
const confirmPassword = ref('')
const forgotFilePath = ref('')
const AUTH_STATUS_TIMEOUT_MS = 8000
const AUTH_ACTION_TIMEOUT_MS = 15000
const PASSWORD_HINT_RELATIVE_PATH = 'workspace/password.txt'

// ── 密码强度校验 ──
const strengthChecks = computed(() => ({
  minLength: password.value.length >= 8,
  uppercase: /[A-Z]/.test(password.value),
  lowercase: /[a-z]/.test(password.value),
  digit: /[0-9]/.test(password.value),
}))

const isPasswordValid = computed(() =>
  strengthChecks.value.minLength &&
  strengthChecks.value.uppercase &&
  strengthChecks.value.lowercase &&
  strengthChecks.value.digit,
)

const passwordsMatch = computed(() =>
  !isSetup.value || password.value === confirmPassword.value,
)

const canSubmit = computed(() => {
  if (!password.value) return false
  if (!isSetup.value) return true
  return isPasswordValid.value && passwordsMatch.value
})

function normalizeRelativeFilePath(filePath: unknown): string {
  if (typeof filePath !== 'string') {
    return PASSWORD_HINT_RELATIVE_PATH
  }

  const normalized = filePath.replace(/\\/g, '/').trim()
  if (!normalized) {
    return PASSWORD_HINT_RELATIVE_PATH
  }

  if (normalized.startsWith('/') || normalized.includes('://') || /^[a-zA-Z]:\//.test(normalized) || normalized.includes('..')) {
    return PASSWORD_HINT_RELATIVE_PATH
  }

  return normalized
}

// ── 检查认证状态 ──
async function checkAuthStatus() {
  try {
    const res = await axios.get('/api/auth/status', { timeout: AUTH_STATUS_TIMEOUT_MS })
    isSetup.value = !res.data.password_set
  } catch {
    isSetup.value = true
  } finally {
    checkingStatus.value = false
  }
}

// ── 设置密码 ──
async function handleSetup() {
  if (!canSubmit.value || loading.value) return
  loading.value = true
  try {
    const res = await axios.post('/api/auth/setup', { password: password.value }, { timeout: AUTH_ACTION_TIMEOUT_MS })
    localStorage.setItem('lui_jwt', res.data.token)
    ElMessage.success(t('login.setupTitle'))
    router.replace('/')
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || t('login.errorSetupFailed'))
  } finally {
    loading.value = false
  }
}

// ── 登录 ──
async function handleLogin() {
  if (!password.value || loading.value) return
  loading.value = true
  try {
    const res = await axios.post('/api/auth/login', { password: password.value }, { timeout: AUTH_ACTION_TIMEOUT_MS })
    localStorage.setItem('lui_jwt', res.data.token)
    router.replace('/')
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || t('login.errorLoginFailed'))
  } finally {
    loading.value = false
  }
}

// ── 忘记密码 ──
async function handleForgotPassword() {
  try {
    const res = await axios.get('/api/auth/forgot-password-hint')
    forgotFilePath.value = normalizeRelativeFilePath(res.data.file_path)
  } catch {
    forgotFilePath.value = PASSWORD_HINT_RELATIVE_PATH
  }

  ElMessageBox.alert(
    `<p style="margin-bottom:12px;line-height:1.7;">${t('login.forgotDialogMessage')}</p>
     <p style="font-family:var(--font-mono);background:#f5f5f5;padding:10px 14px;border:1px solid #e5e5e5;font-size:13px;word-break:break-all;">${forgotFilePath.value}</p>`,
    t('login.forgotDialogTitle'),
    {
      dangerouslyUseHTMLString: true,
      confirmButtonText: t('login.forgotDialogConfirm'),
      customClass: 'forgot-dialog',
    },
  )
}

// ── 提交 ──
async function handleSubmit() {
  if (loading.value) return
  if (isSetup.value) {
    await handleSetup()
  } else {
    await handleLogin()
  }
}

// ── 动画控制 ──
const animPhase = ref(0) // 0=初始, 1=六边形绘制, 2=骨架绘制, 3=星芒显现

onMounted(() => {
  checkAuthStatus()
  // 逐阶段触发动画
  setTimeout(() => { animPhase.value = 1 }, 100)
  setTimeout(() => { animPhase.value = 2 }, 800)
  setTimeout(() => { animPhase.value = 3 }, 1400)
})
</script>

<template>
  <div class="login-page">
    <!-- 背景装饰线条 -->
    <div class="bg-lines">
      <div class="bg-line line-1"></div>
      <div class="bg-line line-2"></div>
      <div class="bg-line line-3"></div>
      <div class="bg-line line-4"></div>
      <div class="bg-line line-5"></div>
      <div class="bg-line line-6"></div>
    </div>

    <!-- 主内容区 -->
    <div class="login-content" v-if="!checkingStatus">
      <!-- Logo 动画区 -->
      <div class="logo-anim-wrap">
        <svg class="login-logo" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" width="80" height="80">
          <defs>
            <mask id="login-glow-mask">
              <rect width="100" height="100" fill="white" />
              <circle cx="50" cy="50" r="24" fill="black" />
            </mask>
          </defs>

          <!-- 层 1：外轮廓六边形（绘制动画） -->
          <polygon
            class="hex-outline"
            :class="{ draw: animPhase >= 1 }"
            points="50,6 88,28 88,72 50,94 12,72 12,28"
            fill="none"
            stroke="currentColor"
            stroke-width="3.5"
            stroke-linejoin="round"
          />

          <!-- 层 2：骨架线条（绘制动画） -->
          <g mask="url(#login-glow-mask)">
            <!-- 背侧虚线 -->
            <line class="skeleton-line back-line" :class="{ draw: animPhase >= 2 }"
              x1="50" y1="50" x2="50" y2="6" stroke="currentColor" stroke-width="1.2" opacity="0.22" stroke-dasharray="3,4" />
            <line class="skeleton-line back-line" :class="{ draw: animPhase >= 2 }"
              x1="50" y1="50" x2="88" y2="72" stroke="currentColor" stroke-width="1.2" opacity="0.22" stroke-dasharray="3,4" />
            <line class="skeleton-line back-line" :class="{ draw: animPhase >= 2 }"
              x1="50" y1="50" x2="12" y2="72" stroke="currentColor" stroke-width="1.2" opacity="0.22" stroke-dasharray="3,4" />

            <!-- 前端阳线 Y 型 -->
            <line class="skeleton-line front-line" :class="{ draw: animPhase >= 2 }"
              x1="50" y1="50" x2="88" y2="28" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
            <line class="skeleton-line front-line" :class="{ draw: animPhase >= 2 }"
              x1="50" y1="50" x2="50" y2="94" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
            <line class="skeleton-line front-line" :class="{ draw: animPhase >= 2 }"
              x1="50" y1="50" x2="12" y2="28" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
          </g>

          <!-- 层 3：四芒星（淡入脉冲） -->
          <path
            class="star-burst"
            :class="{ appear: animPhase >= 3 }"
            d="
              M 50 28
              C 46 46, 46 46, 28 50
              C 46 54, 46 54, 50 72
              C 54 54, 54 54, 72 50
              C 54 46, 54 46, 50 28
              Z
            "
            fill="currentColor"
          />
        </svg>
      </div>

      <!-- 标题 -->
      <h1 class="login-title">{{ isSetup ? t('login.setupTitle') : t('login.loginTitle') }}</h1>
      <p class="login-subtitle">{{ isSetup ? t('login.setupSubtitle') : t('login.loginSubtitle') }}</p>

      <!-- 表单 -->
      <form class="login-form" @submit.prevent="handleSubmit">
        <!-- 密码输入 -->
        <div class="field-group">
          <label class="field-label">{{ t('login.passwordLabel') }}</label>
          <input
            v-model="password"
            type="password"
            class="field-input"
            :placeholder="t('login.passwordPlaceholder')"
            data-allow-autocomplete
            autocomplete="current-password"
          />
        </div>

        <!-- 确认密码（仅设置模式） -->
        <div v-if="isSetup" class="field-group">
          <label class="field-label">{{ t('login.confirmPasswordLabel') }}</label>
          <input
            v-model="confirmPassword"
            type="password"
            class="field-input"
            :placeholder="t('login.confirmPasswordPlaceholder')"
            data-allow-autocomplete
            autocomplete="new-password"
          />
          <div v-if="confirmPassword && !passwordsMatch" class="field-error">
            {{ t('login.errorPasswordMismatch') }}
          </div>
        </div>

        <!-- 密码强度指示器（仅设置模式） -->
        <div v-if="isSetup && password" class="strength-indicator">
          <div class="strength-item" :class="{ met: strengthChecks.minLength }">
            <span class="strength-dot"></span>
            {{ t('login.strengthMinLength') }}
          </div>
          <div class="strength-item" :class="{ met: strengthChecks.uppercase }">
            <span class="strength-dot"></span>
            {{ t('login.strengthUppercase') }}
          </div>
          <div class="strength-item" :class="{ met: strengthChecks.lowercase }">
            <span class="strength-dot"></span>
            {{ t('login.strengthLowercase') }}
          </div>
          <div class="strength-item" :class="{ met: strengthChecks.digit }">
            <span class="strength-dot"></span>
            {{ t('login.strengthDigit') }}
          </div>
        </div>

        <!-- 提交按钮 -->
        <button
          type="submit"
          class="submit-btn"
          :disabled="!canSubmit || loading"
          :class="{ loading }"
        >
          <span v-if="loading" class="btn-loader"></span>
          <span v-else>{{ isSetup ? t('login.setupButton') : t('login.loginButton') }}</span>
        </button>
      </form>

      <!-- 忘记密码 -->
      <div v-if="!isSetup" class="forgot-link" @click="handleForgotPassword">
        {{ t('login.forgotPassword') }}
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-else class="login-loading">
      <div class="loader-ring"></div>
    </div>
  </div>
</template>

<style scoped>
/* ================= 页面容器 ================= */
.login-page {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
  position: relative;
  overflow: hidden;
}

/* ================= 背景装饰线条 ================= */
.bg-lines {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.bg-line {
  position: absolute;
  background: #0f0f0f;
  opacity: 0;
  animation: lineFadeIn 1.5s ease forwards;
}

.line-1 {
  width: 1px; height: 40vh;
  top: 0; left: 15%;
  opacity: 0.04;
  animation-delay: 0.3s;
  animation: lineDrift1 20s ease-in-out infinite alternate;
}
.line-2 {
  width: 1px; height: 50vh;
  bottom: 0; left: 30%;
  opacity: 0.03;
  animation: lineDrift2 25s ease-in-out infinite alternate;
}
.line-3 {
  height: 1px; width: 35vw;
  top: 25%; left: 0;
  opacity: 0.04;
  animation: lineDrift3 22s ease-in-out infinite alternate;
}
.line-4 {
  height: 1px; width: 40vw;
  bottom: 20%; right: 0;
  opacity: 0.03;
  animation: lineDrift4 18s ease-in-out infinite alternate;
}
.line-5 {
  width: 1px; height: 30vh;
  top: 10%; right: 20%;
  opacity: 0.035;
  animation: lineDrift5 24s ease-in-out infinite alternate;
}
.line-6 {
  height: 1px; width: 25vw;
  top: 60%; left: 10%;
  opacity: 0.03;
  animation: lineDrift6 21s ease-in-out infinite alternate;
}

@keyframes lineDrift1 {
  0% { transform: translateY(-10%); opacity: 0.03; }
  100% { transform: translateY(10%); opacity: 0.05; }
}
@keyframes lineDrift2 {
  0% { transform: translateY(10%); opacity: 0.02; }
  100% { transform: translateY(-10%); opacity: 0.04; }
}
@keyframes lineDrift3 {
  0% { transform: translateX(-5%); opacity: 0.03; }
  100% { transform: translateX(5%); opacity: 0.05; }
}
@keyframes lineDrift4 {
  0% { transform: translateX(5%); opacity: 0.02; }
  100% { transform: translateX(-5%); opacity: 0.04; }
}
@keyframes lineDrift5 {
  0% { transform: translateY(-8%); opacity: 0.025; }
  100% { transform: translateY(8%); opacity: 0.045; }
}
@keyframes lineDrift6 {
  0% { transform: translateX(-3%); opacity: 0.02; }
  100% { transform: translateX(3%); opacity: 0.04; }
}

/* ================= 主内容 ================= */
.login-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 360px;
  max-width: 90vw;
  position: relative;
  z-index: 1;
  animation: contentFadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) 1.6s both;
}

@keyframes contentFadeIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ================= Logo 动画 ================= */
.logo-anim-wrap {
  margin-bottom: 32px;
  color: #0f0f0f;
}

.login-logo {
  display: block;
}

/* 六边形绘制动画 */
.hex-outline {
  stroke-dasharray: 340;
  stroke-dashoffset: 340;
  transition: stroke-dashoffset 0.7s cubic-bezier(0.65, 0, 0.35, 1);
}
.hex-outline.draw {
  stroke-dashoffset: 0;
}

/* 骨架线条绘制动画 */
.skeleton-line {
  stroke-dasharray: 60;
  stroke-dashoffset: 60;
  transition: stroke-dashoffset 0.5s cubic-bezier(0.65, 0, 0.35, 1);
}
.skeleton-line.draw {
  stroke-dashoffset: 0;
}
/* 背侧虚线逐条延迟 */
.skeleton-line.back-line:nth-child(2) {
  transition-delay: 0.08s;
}
.skeleton-line.back-line:nth-child(3) {
  transition-delay: 0.16s;
}
/* 前端阳线 Y 型逐条延迟 */
.skeleton-line.front-line {
  stroke-dasharray: 55;
  stroke-dashoffset: 55;
  transition: stroke-dashoffset 0.6s cubic-bezier(0.65, 0, 0.35, 1);
}
.skeleton-line.front-line.draw {
  stroke-dashoffset: 0;
}
.skeleton-line.front-line:nth-child(5) {
  transition-delay: 0.12s;
}
.skeleton-line.front-line:nth-child(6) {
  transition-delay: 0.24s;
}

/* 四芒星淡入脉冲 */
.star-burst {
  opacity: 0;
  transform-origin: 50px 50px;
  transform: scale(0.7);
  transition: opacity 0.5s ease, transform 0.7s cubic-bezier(0.16, 1, 0.3, 1);
}
.star-burst.appear {
  opacity: 1;
  transform: scale(1);
  animation: starPulse 4s ease-in-out 0.7s infinite;
}

@keyframes starPulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.08); opacity: 0.85; }
}

/* ================= 标题 ================= */
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
  margin-bottom: 36px;
  text-align: center;
  line-height: 1.5;
}

/* ================= 表单 ================= */
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

.field-error {
  font-size: 12px;
  color: #dc2626;
  margin-top: 2px;
}

/* ================= 密码强度 ================= */
.strength-indicator {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 16px;
  padding: 10px 0 0;
}

.strength-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #a3a3a3;
  transition: color 0.25s ease;
}

.strength-item.met {
  color: #0f0f0f;
}

.strength-dot {
  width: 6px;
  height: 6px;
  border: 1.5px solid #d4d4d4;
  transition: background-color 0.25s ease, border-color 0.25s ease;
  flex-shrink: 0;
}

.strength-item.met .strength-dot {
  background-color: #0f0f0f;
  border-color: #0f0f0f;
}

/* ================= 提交按钮 ================= */
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

/* ================= 忘记密码 ================= */
.forgot-link {
  margin-top: 24px;
  font-size: 12px;
  color: #737373;
  cursor: pointer;
  transition: color 0.2s ease;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.forgot-link:hover {
  color: #0f0f0f;
}

/* ================= 加载状态 ================= */
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
