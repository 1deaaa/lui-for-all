<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { getLocale, setLocale, SUPPORTED_LOCALES, type AppLocale } from '@/i18n'

const settings = ref({
  // 安全与扩展配置
  safety_default_action: 'confirm',
  mcp_api_token: '',
  
  // 主模型配置
  llm_api_base: '',
  llm_api_key: '',
  llm_model_id: '',
  llm_extra_body: ''
})
const { t } = useI18n()

const saving = ref(false)
const testing = ref(false)
const loading = ref(false)
const fetchingModels = ref(false)
const testStatus = ref<'success' | 'error' | null>(null)
const availableModels = ref<string[]>([])
const currentLocale = ref<AppLocale>(getLocale())

const localeLabelKeyMap: Record<AppLocale, string> = {
  'zh-CN': 'language.options.zhCN',
  'en-US': 'language.options.enUS',
  'ja-JP': 'language.options.jaJP',
}

const localeOptions = computed(() =>
  SUPPORTED_LOCALES.map((code) => ({
    value: code,
    label: t(localeLabelKeyMap[code]),
  })),
)

function handleLocaleChange(nextLocale: string | number | boolean) {
  const locale = nextLocale as AppLocale
  setLocale(locale)
  currentLocale.value = locale
  ElMessage.success(t('settings.messages.languageUpdated', { label: t(localeLabelKeyMap[locale]) }))
}

async function loadSettings() {
  loading.value = true
  try {
    const [settingsRes, llmRes] = await Promise.all([
      axios.get('/api/settings'),
      axios.get('/api/llm-status/main')
    ])
    
    settings.value = {
      safety_default_action: settingsRes.data.safety_default_action || 'confirm',
      mcp_api_token: settingsRes.data.mcp_api_token || '',
      llm_api_base: llmRes.data.llm_api_base || '',
      llm_api_key: llmRes.data.llm_api_key || '',
      llm_model_id: llmRes.data.llm_model_id || '',
      llm_extra_body: llmRes.data.llm_extra_body || ''
    }
    
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || t('settings.messages.loadFailed'))
  } finally {
    loading.value = false
  }
}

// 保存设置
async function saveSettings(silent = false) {
  if (loading.value) return // 防止初始加载触发
  saving.value = true
  try {
    formatApiBase()
    formatExtraBody() // 保存前格式化
    
    await Promise.all([
      axios.put('/api/settings', {
        safety_default_action: settings.value.safety_default_action,
        mcp_api_token: settings.value.mcp_api_token
      }),
      axios.put('/api/llm-status/main', {
        llm_api_base: settings.value.llm_api_base,
        llm_api_key: settings.value.llm_api_key,
        llm_model_id: settings.value.llm_model_id,
        llm_extra_body: settings.value.llm_extra_body
      })
    ])
    if (!silent) {
      ElMessage.success(t('settings.messages.saved'))
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || t('settings.messages.saveFailed'))
  } finally {
    saving.value = false
  }
}

// 自动格式化 API Endpoint
function formatApiBase() {
  let url = settings.value.llm_api_base.trim()
  if (!url) return
  url = url.replace(/\/+$/, '')
  if (!url.endsWith('/v1')) {
    url = url + '/v1'
  }
  settings.value.llm_api_base = url
}

// 自动修复并格式化 JSON
function formatExtraBody() {
  let body = settings.value.llm_extra_body.trim()
  if (!body) return
  if (!body.startsWith('{')) body = '{' + body
  if (!body.endsWith('}')) body = body + '}'
  try {
    const parsed = JSON.parse(body)
    settings.value.llm_extra_body = JSON.stringify(parsed, null, 2)
  } catch (e) {
    ElMessage.warning(t('settings.messages.formatJsonWarning'))
    settings.value.llm_extra_body = body
  }
}

// 测试连接
async function testConnection() {
  formatApiBase()
  formatExtraBody()
  testing.value = true
  testStatus.value = null
  try {
    const response = await axios.post('/api/llm-status/test', {
      llm_api_base: settings.value.llm_api_base,
      llm_api_key: settings.value.llm_api_key,
      llm_model_id: settings.value.llm_model_id,
      llm_extra_body: settings.value.llm_extra_body
    })
    ElMessage.success(t('settings.messages.testSuccess', { reply: response.data.reply }))
    testStatus.value = 'success'
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || t('settings.messages.testFailed'))
    testStatus.value = 'error'
  } finally {
    testing.value = false
  }
}

// 获取模型列表
async function fetchModels() {
  if (!settings.value.llm_api_base) {
    ElMessage.warning(t('settings.messages.apiBaseRequired'))
    return
  }
  formatApiBase()
  fetchingModels.value = true
  try {
    const response = await axios.post('/api/llm-status/probe', {
      llm_api_base: settings.value.llm_api_base,
      llm_api_key: settings.value.llm_api_key,
      llm_model_id: '',
      llm_extra_body: ''
    })
    availableModels.value = response.data.models || []
    if (availableModels.value.length === 0) {
      ElMessage.warning(t('settings.messages.modelsEmpty'))
    } else {
      ElMessage.success(t('settings.messages.modelsProbed', { count: availableModels.value.length }))
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || t('settings.messages.probeFailed'))
  } finally {
    fetchingModels.value = false
  }
}

function handleModelSelectVisible(visible: boolean) {
  if (visible && availableModels.value.length === 0) {
    fetchModels()
  }
}

// 生成随机 Token 并立即保存
async function generateMcpToken() {
  settings.value.mcp_api_token = crypto.randomUUID().replace(/-/g, '')
  await saveSettings(true)
  ElMessage.success(t('settings.messages.tokenGenerated'))
}

async function handleSafetyActionChange(val: string) {
  if (val === 'allow') {
    try {
      await ElMessageBox.confirm(
        t('settings.dialogs.allowConfirmMessage'),
        t('settings.dialogs.allowConfirmTitle'),
        { type: 'warning', confirmButtonText: t('settings.dialogs.allowConfirmButton'), cancelButtonText: t('common.cancel') }
      )
      await ElMessageBox.confirm(
        t('settings.dialogs.finalConfirmMessage'),
        t('settings.dialogs.finalConfirmTitle'),
        { type: 'error', confirmButtonText: t('settings.dialogs.finalConfirmButton'), cancelButtonText: t('settings.dialogs.finalCancelButton') }
      )
    } catch {
      settings.value.safety_default_action = 'confirm'
    }
  }
  await saveSettings(false)
}

function resolveMcpGatewayOrigin(): string {
  const isViteDevServer = import.meta.env.DEV && window.location.port === '5173'
  if (isViteDevServer) {
    const devBackend = import.meta.env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:6689'
    return devBackend.replace(/\/+$/, '')
  }
  return `${window.location.protocol}//${window.location.host}`.replace(/\/+$/, '')
}

const mcpGatewayOrigin = computed(() => resolveMcpGatewayOrigin())
const mcpGatewayUrl = computed(() => `${mcpGatewayOrigin.value}/mcp/`)
const mcpJsonExample = computed(() => {
  const token = settings.value.mcp_api_token || t('settings.mcp.tokenFillHint')
  const url = mcpGatewayUrl.value
  
  // 提供标准的 Streamable HTTP 连接 JSON
  return JSON.stringify({
    "mcpServers": {
      "lui-for-all-remote": {
        "type": "streamable-http",
        "url": url,
        "headers": {
          "Authorization": `Bearer ${token}`
        }
      }
    }
  }, null, 2)
})

async function copyMcpJson() {
  try {
    await navigator.clipboard.writeText(mcpJsonExample.value)
    ElMessage.success(t('settings.messages.jsonCopied'))
  } catch (e) {
    ElMessage.error(t('settings.messages.copyFailed'))
  }
}

function highlightJson(code: string) {
  // @ts-ignore
  if (window.hljs) {
    // @ts-ignore
    return window.hljs.highlight(code, { language: 'json' }).value
  }
  return code
}

onMounted(loadSettings)
</script>

<template>
  <div class="settings-page">
    <div class="header-section">
      <div class="header-titles">
        <h2>{{ t('settings.pageTitle') }}</h2>
        <p class="subtitle">{{ t('settings.subtitle') }}</p>
      </div>
    </div>

    <div class="content-scroll" v-loading="loading">
      <el-form :model="settings" label-position="top" class="settings-form">
        <div class="cards-grid">

          <!-- Language Config Card -->
          <el-card class="setting-card language-card fade-in-up" shadow="never" style="animation-delay: 0s;">
            <template #header>
              <div class="card-header">
                <Icon icon="lucide:languages" class="card-icon" />
                <div>
                  <div class="card-title">{{ t('settings.language.cardTitle') }}</div>
                  <div class="card-desc">{{ t('settings.language.cardDesc') }}</div>
                </div>
              </div>
            </template>

            <el-form-item :label="t('settings.language.sectionLabel')">
              <el-radio-group v-model="currentLocale" class="language-radio-group" size="large" @change="handleLocaleChange">
                <el-radio-button
                  v-for="option in localeOptions"
                  :key="option.value"
                  :label="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </el-radio-button>
              </el-radio-group>
              <div class="language-hint">
                {{ t('settings.language.hint') }}
              </div>
            </el-form-item>
          </el-card>
          
          <!-- LLM Config Card -->
          <el-card class="setting-card fade-in-up llm-card" shadow="never" style="animation-delay: 0.05s;">
            <template #header>
              <div class="card-header">
                <Icon icon="lucide:cpu" class="card-icon" />
                <div style="flex: 1;">
                  <div class="card-title">{{ t('settings.llm.cardTitle') }}</div>
                  <div class="card-desc">{{ t('settings.llm.cardDesc') }}</div>
                </div>
                
                <div class="llm-actions">
                  <transition name="el-fade-in">
                    <div v-if="testStatus === 'success'" class="status-indicator success">
                      <Icon icon="lucide:check-circle-2" /> <span>{{ t('settings.llm.statusConnected') }}</span>
                    </div>
                  </transition>
                  <transition name="el-fade-in">
                    <div v-if="testStatus === 'error'" class="status-indicator error">
                      <Icon icon="lucide:x-circle" /> <span>{{ t('settings.llm.statusFailed') }}</span>
                    </div>
                  </transition>
                  <el-button @click="testConnection" :loading="testing" plain round size="default" class="test-btn">
                    <Icon icon="lucide:zap" class="btn-icon" /> {{ t('settings.llm.testConnection') }}
                  </el-button>
                </div>
              </div>
            </template>
            
            <el-row :gutter="24">
              <el-col :span="24" :md="12">
                <el-form-item :label="t('settings.llm.apiBaseLabel')">
                  <el-input 
                    v-model="settings.llm_api_base" 
                    :placeholder="t('settings.llm.apiBasePlaceholder')" 
                    @blur="formatApiBase"
                    @change="() => saveSettings(false)"
                  >
                    <template #prefix>
                      <Icon icon="lucide:globe" />
                    </template>
                  </el-input>
                </el-form-item>
              </el-col>
              <el-col :span="24" :md="12">
                <el-form-item :label="t('settings.llm.apiKeyLabel')">
                  <el-input 
                    v-model="settings.llm_api_key" 
                    type="password" 
                    show-password 
                    :placeholder="t('settings.llm.apiKeyPlaceholder')" 
                    @change="() => saveSettings(false)"
                  >
                    <template #prefix>
                      <Icon icon="lucide:key" />
                    </template>
                  </el-input>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="24">
              <el-col :span="24" :md="12">
                <el-form-item :label="t('settings.llm.modelIdLabel')">
                  <div class="model-select-wrap">
                    <el-select 
                      v-model="settings.llm_model_id" 
                      :placeholder="t('settings.llm.modelIdPlaceholder')" 
                      filterable 
                      allow-create 
                      default-first-option
                      :loading="fetchingModels"
                      @visible-change="handleModelSelectVisible"
                      @change="() => saveSettings(false)"
                      class="model-select"
                    >
                      <template #prefix>
                        <Icon icon="lucide:bot" />
                      </template>
                      <el-option
                        v-for="model in availableModels"
                        :key="model"
                        :label="model"
                        :value="model"
                      />
                    </el-select>
                    <el-button @click="fetchModels" :loading="fetchingModels" plain>
                      <Icon icon="lucide:radar" /> {{ t('settings.llm.probeModels') }}
                    </el-button>
                  </div>
                </el-form-item>
              </el-col>
              <el-col :span="24" :md="12">
                <el-form-item :label="t('settings.llm.extraBodyLabel')">
                  <el-input 
                    v-model="settings.llm_extra_body" 
                    type="textarea"
                    :rows="2"
                    :placeholder="t('settings.llm.extraBodyPlaceholder')"
                    @blur="formatExtraBody"
                    @change="() => saveSettings(false)"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-card>

          <!-- Safety Config Card -->
          <el-card class="setting-card fade-in-up" shadow="never" style="animation-delay: 0.15s;">
            <template #header>
              <div class="card-header">
                <Icon icon="lucide:shield-alert" class="card-icon" />
                <div>
                  <div class="card-title">{{ t('settings.safety.cardTitle') }}</div>
                  <div class="card-desc">{{ t('settings.safety.cardDesc') }}</div>
                </div>
              </div>
            </template>
            
            <el-form-item :label="t('settings.safety.defaultAction')">
              <el-select v-model="settings.safety_default_action" @change="handleSafetyActionChange" style="width: 100%;">
                <el-option :label="t('settings.safety.allow')" value="allow">
                  <div class="flex-option">
                    <Icon icon="lucide:unlock" class="text-danger" />
                    <span class="text-danger">{{ t('settings.safety.allow') }}</span>
                  </div>
                </el-option>
                <el-option :label="t('settings.safety.confirm')" value="confirm">
                  <div class="flex-option">
                    <Icon icon="lucide:user-check" class="text-success" />
                    <span>{{ t('settings.safety.confirm') }}</span>
                  </div>
                </el-option>
                <el-option :label="t('settings.safety.block')" value="block">
                  <div class="flex-option">
                    <Icon icon="lucide:ban" />
                    <span>{{ t('settings.safety.block') }}</span>
                  </div>
                </el-option>
              </el-select>
              
              <transition name="el-zoom-in-top">
                <div v-if="settings.safety_default_action === 'allow'" class="allow-warning">
                  <Icon icon="lucide:flame" class="warning-icon" />
                  <div class="warning-text">
                    {{ t('settings.safety.allowWarning') }}
                  </div>
                </div>
              </transition>
            </el-form-item>
          </el-card>

          <!-- MCP Config Card -->
          <el-card class="setting-card fade-in-up" shadow="never" style="animation-delay: 0.25s;">
            <template #header>
              <div class="card-header">
                <Icon icon="lucide:network" class="card-icon" />
                <div>
                  <div class="card-title">{{ t('settings.mcp.cardTitle') }}</div>
                  <div class="card-desc">{{ t('settings.mcp.cardDesc') }}</div>
                </div>
              </div>
            </template>

            <el-alert
              :title="t('settings.mcp.warningTitle')"
              type="error"
              show-icon
              :closable="false"
              style="margin-bottom: 24px;"
            >
              <template #title>{{ t('settings.mcp.warningBody') }}</template>
            </el-alert>

            <el-form-item :label="t('settings.mcp.tokenLabel')">
              <el-input 
                v-model="settings.mcp_api_token" 
                type="password"
                show-password
                :placeholder="t('settings.mcp.tokenPlaceholder')"
                @change="() => saveSettings(false)"
              >
                <template #append>
                  <el-button @click="generateMcpToken">
                    <Icon icon="lucide:dices" /> {{ t('settings.mcp.generateToken') }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item :label="t('settings.mcp.clientConfigLabel')">
              <div class="mcp-instructions">
                <div class="instruction-box">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h4>
                      <Icon icon="lucide:terminal" />
                      {{ t('settings.mcp.clientConfigTitle') }}
                    </h4>
                    <el-button size="small" @click="copyMcpJson" plain round>
                      <Icon icon="lucide:copy" style="margin-right: 4px;" /> {{ t('settings.mcp.copyJson') }}
                    </el-button>
                  </div>
                  <p>{{ t('settings.mcp.instructions') }}</p>
                  <p class="instruction-note">
                    <Icon icon="lucide:server" /> {{ t('settings.mcp.gatewayAddress') }}<code>{{ mcpGatewayUrl }}</code>
                  </p>
                  <div class="code-block" v-html="highlightJson(mcpJsonExample)"></div>
                  <p class="instruction-note">
                    <Icon icon="lucide:info" /> {{ t('settings.mcp.gatewayNote') }}
                  </p>
                </div>
              </div>
            </el-form-item>
          </el-card>
        </div>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color-page);
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 40px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  z-index: 10;
}

.header-titles h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* .global-actions 已移除，无全局保存按钮 */

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  animation: fadeIn 0.3s ease;
}
.status-indicator.success { color: var(--el-color-success); }
.status-indicator.error { color: var(--el-color-danger); }

.btn-icon {
  margin-right: 6px;
  font-size: 1.1em;
}

.content-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px;
}

.settings-form {
  max-width: 1400px;
  margin: 0 auto;
}

.cards-grid {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.setting-card {
  border-radius: 12px;
  border: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}

.language-card {
  border: 1px solid var(--el-color-primary-light-5);
  background: linear-gradient(180deg, #fafafa 0%, #ffffff 100%);
}

.language-radio-group {
  width: 100%;
  display: flex;
}

.language-radio-group :deep(.el-radio-button) {
  flex: 1;
}

.language-radio-group :deep(.el-radio-button__inner) {
  width: 100%;
  font-weight: 600;
}

.language-hint {
  margin-top: 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.llm-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
}
.status-indicator.success { color: var(--el-color-success); }
.status-indicator.error { color: var(--el-color-danger); }

.test-btn {
  margin-left: 8px;
}

.card-icon {
  font-size: 20px;
  margin-right: 4px;
  color: var(--el-color-primary);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}

.card-desc {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-weight: normal;
  margin-top: 4px;
}

.model-select-wrap {
  display: flex;
  width: 100%;
  gap: 12px;
}

.model-select {
  flex-grow: 1;
}

.flex-option {
  display: flex;
  align-items: center;
  gap: 8px;
}
.text-danger { color: var(--el-color-danger) !important; }
.text-success { color: var(--el-color-success) !important; }

/* 警示区动效与样式 */
.allow-warning {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: #fff0f0;
  border: 1px solid #ffcccc;
}
.warning-icon {
  font-size: 20px;
  color: #c9302c;
  line-height: 1;
}
.warning-text {
  font-size: 13px;
  color: #c9302c;
  line-height: 1.6;
}

.mcp-instructions {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 8px;
  width: 100%;
}
.instruction-box {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
}
.instruction-box h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: var(--el-text-color-regular);
  display: flex;
  align-items: center;
  gap: 6px;
}
.instruction-box p {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.instruction-note {
  font-size: 12px !important;
  color: var(--el-text-color-placeholder) !important;
  margin-top: 12px !important;
  margin-bottom: 0 !important;
}
.code-block {
  background: #f8f9fa;
  color: #24292e;
  padding: 14px;
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 13px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  border: 1px solid var(--el-border-color-lighter);
}

/* 入场动画 */
.fade-in-up {
  opacity: 0;
  animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes fadeInUp {
  0% { opacity: 0; transform: translateY(15px); }
  100% { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--el-text-color-regular);
}
</style>
