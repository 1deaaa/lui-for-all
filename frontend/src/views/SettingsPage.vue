<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { getLocale, setLocale, SUPPORTED_LOCALES, type AppLocale } from '@/i18n'

type SafetyDefaultAction = 'allow' | 'confirm' | 'block'
type LlmManagerDialogMode = 'create' | 'edit'

interface SettingsForm {
  safety_default_action: SafetyDefaultAction
  mcp_api_token: string
  llm_api_base: string
  llm_api_key: string
  llm_model_id: string
  llm_extra_body: string
}

interface SettingsResponse {
  safety_default_action?: string
  mcp_api_token?: string
}

interface MainModelConfigResponse {
  llm_api_base?: string
  llm_api_key?: string
  llm_model_id?: string
  llm_extra_body?: string
}

interface ManagedModel {
  model_id: number
}

interface ManagedPlatform {
  platform_id: number
  name: string
  base_url: string
  api_key_set: boolean
  models: ManagedModel[]
}

interface LLMManagerSnapshot {
  selected_platform_id: number | null
  selected_model_id: number | null
  platforms: ManagedPlatform[]
}

interface PlatformProbeSyncResponse {
  snapshot: LLMManagerSnapshot
  probed: number
  created: number
}

interface PlatformDialogForm {
  name: string
  base_url: string
  api_key: string
  clear_api_key: boolean
}

const settings = ref<SettingsForm>({
  safety_default_action: 'confirm',
  mcp_api_token: '',
  llm_api_base: '',
  llm_api_key: '',
  llm_model_id: '',
  llm_extra_body: '',
})
const { t } = useI18n()

const saving = ref(false)
const testing = ref(false)
const loading = ref(false)
const fetchingModels = ref(false)
const testStatus = ref<'success' | 'error' | null>(null)
const availableModels = ref<string[]>([])
const currentLocale = ref<AppLocale>(getLocale())

const managerLoading = ref(false)
const managerOperating = ref(false)
const managerSnapshot = ref<LLMManagerSnapshot>({
  selected_platform_id: null,
  selected_model_id: null,
  platforms: [],
})
const selectedPlatformId = ref<number | null>(null)

const platformDialogVisible = ref(false)
const platformDialogMode = ref<LlmManagerDialogMode>('create')
const platformDialogSaving = ref(false)
const platformForm = ref<PlatformDialogForm>({
  name: '',
  base_url: '',
  api_key: '',
  clear_api_key: false,
})

let syncingPlatformSelection = false

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

const platformOptions = computed(() => managerSnapshot.value.platforms)
const selectedPlatform = computed(() =>
  platformOptions.value.find((platform) => platform.platform_id === selectedPlatformId.value) ?? null,
)

const currentMainSelectionText = computed(() => {
  const currentPlatform = platformOptions.value.find(
    (platform) => platform.platform_id === managerSnapshot.value.selected_platform_id,
  )
  if (!currentPlatform) {
    return t('settings.llm.mainBindingUnset')
  }

  const modelText = settings.value.llm_model_id || '-'
  return t('settings.llm.mainBindingValue', {
    platform: currentPlatform.name,
    model: modelText,
  })
})

const platformDialogTitle = computed(() => {
  if (platformDialogMode.value === 'create') {
    return t('settings.llm.platformDialogCreateTitle')
  }
  return t('settings.llm.platformDialogEditTitle')
})

watch(selectedPlatformId, (nextPlatformId) => {
  if (syncingPlatformSelection) {
    return
  }
  if (nextPlatformId === null || nextPlatformId === managerSnapshot.value.selected_platform_id) {
    return
  }

  void switchPlatformAsMain(nextPlatformId)
})

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
    if (typeof error.message === 'string' && error.message.trim()) {
      return error.message
    }
    return fallback
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return fallback
}

function normalizeSafetyAction(value: string | undefined): SafetyDefaultAction {
  if (value === 'allow' || value === 'block') {
    return value
  }
  return 'confirm'
}

function applyMainModelConfig(config: MainModelConfigResponse) {
  settings.value.llm_api_base = config.llm_api_base || ''
  settings.value.llm_api_key = config.llm_api_key || ''
  settings.value.llm_model_id = config.llm_model_id || ''
  settings.value.llm_extra_body = config.llm_extra_body || ''
}

function applyManagerSnapshot(snapshot: LLMManagerSnapshot) {
  managerSnapshot.value = snapshot
  syncingPlatformSelection = true
  selectedPlatformId.value = snapshot.selected_platform_id ?? snapshot.platforms[0]?.platform_id ?? null
  syncingPlatformSelection = false
}

function handleLocaleChange(nextLocale: string | number | boolean) {
  const locale = nextLocale as AppLocale
  setLocale(locale)
  currentLocale.value = locale
  ElMessage.success(t('settings.messages.languageUpdated', { label: t(localeLabelKeyMap[locale]) }))
}

async function loadMainModelConfig(showError = true) {
  try {
    const response = await axios.get<MainModelConfigResponse>('/api/llm-status/main')
    applyMainModelConfig(response.data)
  } catch (error: unknown) {
    if (showError) {
      ElMessage.error(getErrorMessage(error, t('settings.messages.loadFailed')))
    }
  }
}

async function refreshManagerSnapshot(showError = true) {
  managerLoading.value = true
  try {
    const response = await axios.get<LLMManagerSnapshot>('/api/llm-status/manager')
    applyManagerSnapshot(response.data)
    return true
  } catch (error: unknown) {
    if (showError) {
      ElMessage.error(getErrorMessage(error, t('settings.messages.managerLoadFailed')))
    }
    return false
  } finally {
    managerLoading.value = false
  }
}

async function loadSettings() {
  loading.value = true
  try {
    const [settingsRes, llmRes, managerRes] = await Promise.all([
      axios.get<SettingsResponse>('/api/settings'),
      axios.get<MainModelConfigResponse>('/api/llm-status/main'),
      axios.get<LLMManagerSnapshot>('/api/llm-status/manager'),
    ])

    settings.value.safety_default_action = normalizeSafetyAction(settingsRes.data.safety_default_action)
    settings.value.mcp_api_token = settingsRes.data.mcp_api_token || ''
    applyMainModelConfig(llmRes.data)
    applyManagerSnapshot(managerRes.data)
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, t('settings.messages.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function saveSettings(silent = false) {
  if (loading.value) return

  saving.value = true
  try {
    formatApiBase()
    formatExtraBody()

    await Promise.all([
      axios.put('/api/settings', {
        safety_default_action: settings.value.safety_default_action,
        mcp_api_token: settings.value.mcp_api_token,
      }),
      axios.put('/api/llm-status/main', {
        llm_api_base: settings.value.llm_api_base,
        llm_api_key: settings.value.llm_api_key,
        llm_model_id: settings.value.llm_model_id,
        llm_extra_body: settings.value.llm_extra_body,
      }),
    ])

    if (!silent) {
      ElMessage.success(t('settings.messages.saved'))
    }
    await refreshManagerSnapshot(false)
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, t('settings.messages.saveFailed')))
  } finally {
    saving.value = false
  }
}

async function saveMcpToken(silent = false) {
  if (loading.value) return

  saving.value = true
  try {
    await axios.put('/api/settings', {
      safety_default_action: settings.value.safety_default_action,
      mcp_api_token: settings.value.mcp_api_token,
    })

    if (!silent) {
      ElMessage.success(t('settings.messages.saved'))
    }
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, t('settings.messages.saveFailed')))
  } finally {
    saving.value = false
  }
}

function formatApiBase() {
  let url = settings.value.llm_api_base.trim()
  if (!url) return
  url = url.replace(/\/+$/, '')
  if (!url.endsWith('/v1')) {
    url = `${url}/v1`
  }
  settings.value.llm_api_base = url
}

function formatExtraBody() {
  let body = settings.value.llm_extra_body.trim()
  if (!body) return
  if (!body.startsWith('{')) body = `{${body}`
  if (!body.endsWith('}')) body = `${body}}`
  try {
    const parsed = JSON.parse(body)
    settings.value.llm_extra_body = JSON.stringify(parsed, null, 2)
  } catch {
    ElMessage.warning(t('settings.messages.formatJsonWarning'))
    settings.value.llm_extra_body = body
  }
}

function formatPlatformLabel(platform: ManagedPlatform): string {
  const keyStatus = platform.api_key_set
    ? t('settings.llm.apiKeyConfigured')
    : t('settings.llm.apiKeyMissing')
  return `${platform.name} · ${keyStatus}`
}

function openCreatePlatformDialog() {
  platformDialogMode.value = 'create'
  platformForm.value = {
    name: '',
    base_url: '',
    api_key: '',
    clear_api_key: false,
  }
  platformDialogVisible.value = true
}

function openEditPlatformDialog() {
  if (!selectedPlatform.value) {
    ElMessage.warning(t('settings.messages.platformRequired'))
    return
  }

  platformDialogMode.value = 'edit'
  platformForm.value = {
    name: selectedPlatform.value.name,
    base_url: selectedPlatform.value.base_url,
    api_key: '',
    clear_api_key: false,
  }
  platformDialogVisible.value = true
}

async function submitPlatformDialog() {
  const name = platformForm.value.name.trim()
  const baseUrl = platformForm.value.base_url.trim()

  if (!name) {
    ElMessage.warning(t('settings.llm.platformNameLabel'))
    return
  }
  if (!baseUrl) {
    ElMessage.warning(t('settings.llm.platformBaseUrlLabel'))
    return
  }

  platformDialogSaving.value = true
  try {
    let response
    if (platformDialogMode.value === 'create') {
      response = await axios.post<LLMManagerSnapshot>('/api/llm-status/manager/platforms', {
        name,
        base_url: baseUrl,
        api_key: platformForm.value.api_key.trim(),
      })
      ElMessage.success(t('settings.messages.platformCreated'))
    } else {
      if (selectedPlatformId.value === null) {
        throw new Error(t('settings.messages.platformRequired'))
      }

      const shouldUpdateApiKey =
        platformForm.value.clear_api_key || platformForm.value.api_key.trim().length > 0

      const updatePayload: {
        name: string
        base_url: string
        update_api_key: boolean
        api_key?: string
      } = {
        name,
        base_url: baseUrl,
        update_api_key: shouldUpdateApiKey,
      }

      if (shouldUpdateApiKey) {
        updatePayload.api_key = platformForm.value.clear_api_key ? '' : platformForm.value.api_key.trim()
      }

      response = await axios.put<LLMManagerSnapshot>(
        `/api/llm-status/manager/platforms/${selectedPlatformId.value}`,
        updatePayload,
      )
      ElMessage.success(t('settings.messages.platformUpdated'))
    }

    applyManagerSnapshot(response.data)
    platformDialogVisible.value = false
    await loadMainModelConfig(false)
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, t('settings.messages.saveFailed')))
  } finally {
    platformDialogSaving.value = false
  }
}

async function deleteCurrentPlatform() {
  if (!selectedPlatform.value) {
    ElMessage.warning(t('settings.messages.platformRequired'))
    return
  }

  try {
    await ElMessageBox.confirm(
      t('settings.messages.confirmDeletePlatform', { name: selectedPlatform.value.name }),
      t('settings.llm.deletePlatform'),
      {
        type: 'warning',
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
      },
    )

    managerOperating.value = true
    const response = await axios.delete<LLMManagerSnapshot>(
      `/api/llm-status/manager/platforms/${selectedPlatform.value.platform_id}`,
    )
    applyManagerSnapshot(response.data)
    await loadMainModelConfig(false)
    ElMessage.success(t('settings.messages.platformDeleted'))
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getErrorMessage(error, t('settings.messages.saveFailed')))
    }
  } finally {
    managerOperating.value = false
  }
}

async function switchPlatformAsMain(platformId: number) {
  managerOperating.value = true
  try {
    let currentPlatform = platformOptions.value.find((item) => item.platform_id === platformId)
    if (!currentPlatform) {
      return
    }

    let preferredModelId: number | null =
      currentPlatform.models.find((model) => model.model_id === managerSnapshot.value.selected_model_id)?.model_id ??
      currentPlatform.models[0]?.model_id ??
      null

    if (preferredModelId === null) {
      const probeResponse = await axios.post<PlatformProbeSyncResponse>(
        `/api/llm-status/manager/platforms/${platformId}/probe-and-sync`,
      )
      applyManagerSnapshot(probeResponse.data.snapshot)

      currentPlatform = probeResponse.data.snapshot.platforms.find((item) => item.platform_id === platformId)
      preferredModelId =
        currentPlatform?.models.find((model) => model.model_id === probeResponse.data.snapshot.selected_model_id)
          ?.model_id ??
        currentPlatform?.models[0]?.model_id ??
        null

      if (preferredModelId === null) {
        ElMessage.warning(t('settings.llm.noModelsHint'))
        syncingPlatformSelection = true
        selectedPlatformId.value = managerSnapshot.value.selected_platform_id
        syncingPlatformSelection = false
        return
      }

      if (probeResponse.data.created > 0) {
        ElMessage.success(t('settings.messages.modelsProbed', { count: probeResponse.data.created }))
      }
    }

    const response = await axios.post<LLMManagerSnapshot>('/api/llm-status/manager/main-selection', {
      platform_id: platformId,
      model_id: preferredModelId,
    })
    applyManagerSnapshot(response.data)
    await loadMainModelConfig(false)
    ElMessage.success(t('settings.messages.mainSelectionSaved'))
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, t('settings.messages.saveFailed')))
    syncingPlatformSelection = true
    selectedPlatformId.value = managerSnapshot.value.selected_platform_id
    syncingPlatformSelection = false
  } finally {
    managerOperating.value = false
  }
}

async function testConnection() {
  formatApiBase()
  formatExtraBody()
  testing.value = true
  testStatus.value = null
  try {
    const response = await axios.post<{ reply?: string }>('/api/llm-status/test', {
      llm_api_base: settings.value.llm_api_base,
      llm_api_key: settings.value.llm_api_key,
      llm_model_id: settings.value.llm_model_id,
      llm_extra_body: settings.value.llm_extra_body,
    })
    ElMessage.success(t('settings.messages.testSuccess', { reply: response.data.reply || '' }))
    testStatus.value = 'success'
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, t('settings.messages.testFailed')))
    testStatus.value = 'error'
  } finally {
    testing.value = false
  }
}

async function fetchModels() {
  if (!settings.value.llm_api_base) {
    ElMessage.warning(t('settings.messages.apiBaseRequired'))
    return
  }

  formatApiBase()
  fetchingModels.value = true
  try {
    const response = await axios.post<{ models?: string[] }>('/api/llm-status/probe', {
      llm_api_base: settings.value.llm_api_base,
      llm_api_key: settings.value.llm_api_key,
      llm_model_id: '',
      llm_extra_body: '',
    })
    availableModels.value = response.data.models || []
    if (availableModels.value.length === 0) {
      ElMessage.warning(t('settings.messages.modelsEmpty'))
    } else {
      ElMessage.success(t('settings.messages.modelsProbed', { count: availableModels.value.length }))
    }
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, t('settings.messages.probeFailed')))
  } finally {
    fetchingModels.value = false
  }
}

function handleModelSelectVisible(visible: boolean) {
  if (visible && availableModels.value.length === 0) {
    void fetchModels()
  }
}

async function generateMcpToken() {
  settings.value.mcp_api_token = crypto.randomUUID().replace(/-/g, '')
  await saveMcpToken(true)
  ElMessage.success(t('settings.messages.tokenGenerated'))
}

async function handleSafetyActionChange(val: string) {
  if (val === 'allow') {
    try {
      await ElMessageBox.confirm(t('settings.dialogs.allowConfirmMessage'), t('settings.dialogs.allowConfirmTitle'), {
        type: 'warning',
        confirmButtonText: t('settings.dialogs.allowConfirmButton'),
        cancelButtonText: t('common.cancel'),
      })
      await ElMessageBox.confirm(t('settings.dialogs.finalConfirmMessage'), t('settings.dialogs.finalConfirmTitle'), {
        type: 'error',
        confirmButtonText: t('settings.dialogs.finalConfirmButton'),
        cancelButtonText: t('settings.dialogs.finalCancelButton'),
      })
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

  return JSON.stringify(
    {
      mcpServers: {
        'lui-for-all-remote': {
          type: 'streamable-http',
          url,
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      },
    },
    null,
    2,
  )
})

async function copyMcpJson() {
  try {
    await navigator.clipboard.writeText(mcpJsonExample.value)
    ElMessage.success(t('settings.messages.jsonCopied'))
  } catch {
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
      <el-form :model="settings" label-position="top" class="settings-form" autocomplete="off">
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
                    autocomplete="off"
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
                    autocomplete="off"
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

            <el-divider class="manager-divider" content-position="left">
              {{ t('settings.llm.managerSectionTitle') }}
            </el-divider>
            <p class="manager-hint">{{ t('settings.llm.managerSectionDesc') }}</p>

            <div class="manager-panel" v-loading="managerLoading || managerOperating">
              <el-form-item :label="t('settings.llm.platformLabel')" class="manager-form-item">
                <el-select
                  v-model="selectedPlatformId"
                  class="manager-select"
                  :placeholder="t('settings.llm.platformPlaceholder')"
                  :disabled="platformOptions.length === 0"
                >
                  <el-option
                    v-for="platform in platformOptions"
                    :key="platform.platform_id"
                    :label="formatPlatformLabel(platform)"
                    :value="platform.platform_id"
                  />
                </el-select>
              </el-form-item>

              <div class="manager-actions">
                <el-button plain @click="openCreatePlatformDialog">
                  <Icon icon="lucide:plus-circle" class="btn-icon" />
                  {{ t('settings.llm.addPlatform') }}
                </el-button>
                <el-button plain :disabled="!selectedPlatform" @click="openEditPlatformDialog">
                  <Icon icon="lucide:pen-square" class="btn-icon" />
                  {{ t('settings.llm.editPlatform') }}
                </el-button>
                <el-button plain type="danger" :disabled="!selectedPlatform" @click="deleteCurrentPlatform">
                  <Icon icon="lucide:trash-2" class="btn-icon" />
                  {{ t('settings.llm.deletePlatform') }}
                </el-button>
              </div>

              <div class="manager-main-binding">{{ currentMainSelectionText }}</div>
              <div v-if="selectedPlatform" class="manager-platform-state">
                <Icon icon="lucide:key-round" />
                {{ selectedPlatform.api_key_set ? t('settings.llm.apiKeyConfigured') : t('settings.llm.apiKeyMissing') }}
              </div>

              <div v-if="selectedPlatform && selectedPlatform.models.length === 0" class="manager-empty-hint">
                {{ t('settings.llm.noModelsHint') }}
              </div>
            </div>
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
                autocomplete="off"
                :placeholder="t('settings.mcp.tokenPlaceholder')"
                @change="() => saveMcpToken(false)"
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

      <el-dialog v-model="platformDialogVisible" :title="platformDialogTitle" width="560px" destroy-on-close>
        <el-form :model="platformForm" label-position="top" class="dialog-form" @submit.prevent>
          <el-form-item :label="t('settings.llm.platformNameLabel')" required>
            <el-input
              v-model="platformForm.name"
              :placeholder="t('settings.llm.platformNamePlaceholder')"
              autocomplete="off"
            />
          </el-form-item>
          <el-form-item :label="t('settings.llm.platformBaseUrlLabel')" required>
            <el-input
              v-model="platformForm.base_url"
              :placeholder="t('settings.llm.platformBaseUrlPlaceholder')"
              autocomplete="off"
            />
          </el-form-item>
          <el-form-item :label="t('settings.llm.platformApiKeyLabel')">
            <el-input
              v-model="platformForm.api_key"
              type="password"
              show-password
              :placeholder="t('settings.llm.platformApiKeyPlaceholder')"
              autocomplete="off"
            />
            <el-checkbox v-model="platformForm.clear_api_key" class="dialog-checkbox">
              {{ t('settings.llm.clearPlatformApiKey') }}
            </el-checkbox>
          </el-form-item>
        </el-form>

        <template #footer>
          <div class="dialog-footer">
            <el-button @click="platformDialogVisible = false">{{ t('common.cancel') }}</el-button>
            <el-button type="primary" :loading="platformDialogSaving" @click="submitPlatformDialog">
              {{ t('common.submit') }}
            </el-button>
          </div>
        </template>
      </el-dialog>

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

.manager-divider {
  margin: 8px 0 12px;
}

.manager-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.manager-panel {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 16px;
  background: linear-gradient(180deg, #fcfcfc 0%, #ffffff 100%);
}

.manager-form-item {
  margin-bottom: 12px;
}

.manager-select {
  width: 100%;
}

.manager-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.manager-main-binding {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.manager-platform-state {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.manager-empty-hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-color-warning);
}

.dialog-form {
  padding-top: 4px;
}

.dialog-checkbox {
  margin-top: 10px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
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

/* ================= 移动端适配 (断点 768px) ================= */
@media (max-width: 768px) {
  .header-section {
    padding: 16px 5%;
  }

  .content-scroll {
    padding: 16px 5%; /* 使用百分比适配窄屏幕 */
  }

  .settings-form {
    width: 100%;
  }

  .cards-grid {
    gap: 16px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .llm-actions {
    margin-top: 12px;
    width: 100%;
    justify-content: flex-start;
  }

  .model-select-wrap {
    flex-direction: column;
  }

  .manager-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .manager-main-binding {
    line-height: 1.5;
  }
}
</style>
