<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/stores/project'

const projectStore = useProjectStore()
const router = useRouter()
const { t } = useI18n()
let pollingTimer: number | null = null

// 描述内联编辑状态
const editingDescId = ref<string | null>(null)
const editingDescValue = ref('')
const descSaving = ref(false)

interface ImportFormState {
  name: string
  base_url: string
  openapi_url: string
  description: string
  source_path: string
  username: string
  password: string
  login_route_id: string
  body_field_username: string
  body_field_password: string
}

interface ImportPreset {
  id: string
  name: string
  description: string
  base_url: string
  openapi_url: string
  source_path: string
  login_route_id: string
  username: string
  password: string
  body_field_username: string
  body_field_password: string
  available: boolean
}

function createDefaultImportForm(): ImportFormState {
  return {
    name: '',
    base_url: 'http://localhost:',
    openapi_url: '',
    description: '',
    source_path: '',
    username: '',
    password: '',
    login_route_id: '',
    body_field_username: 'username',
    body_field_password: 'password',
  }
}

function getFallbackImportPresets(): ImportPreset[] {
  return [
    {
      id: 'sample-fastapi',
      name: t('projects.presets.fastapi.name'),
      description: t('projects.presets.fastapi.description'),
      base_url: 'http://localhost:8010',
      openapi_url: 'http://localhost:8010/openapi.json',
      source_path: '/app/backend_for_test/fastapi_sample',
      login_route_id: 'POST:/api/auth/login',
      username: '111',
      password: '111111',
      body_field_username: 'username',
      body_field_password: 'password',
      available: true,
    },
    {
      id: 'sample-node',
      name: t('projects.presets.node.name'),
      description: t('projects.presets.node.description'),
      base_url: 'http://localhost:8020',
      openapi_url: 'http://localhost:8020/openapi.json',
      source_path: '/app/backend_for_test/node_sample',
      login_route_id: 'POST:/api/auth/login',
      username: '111',
      password: '111111',
      body_field_username: 'username',
      body_field_password: 'password',
      available: true,
    },
  ]
}

// 导入表单
const importForm = ref<ImportFormState>(createDefaultImportForm())

const importPresets = ref<ImportPreset[]>([])
const presetLoading = ref(false)
const selectedPresetId = ref('')
const selectedPreset = computed(() => {
  return importPresets.value.find((preset) => preset.id === selectedPresetId.value) || null
})

const importDialogVisible = ref(false)
const importLoading = ref(false)
const testConnectionLoading = ref(false)
const connectionStatus = ref<'untested' | 'success' | 'warning' | 'error'>('untested')

// 登录接口选择
const routeOptions = ref<{ route_id: string; label: string }[]>([])
const routesLoading = ref(false)
const loginVerified = ref<boolean | null>(null)
const loginVerifying = ref(false)

// 打开导入对话框
function openImportDialog() {
  importForm.value = createDefaultImportForm()
  connectionStatus.value = 'untested'
  routeOptions.value = []
  loginVerified.value = null
  selectedPresetId.value = ''
  importDialogVisible.value = true
  void fetchImportPresets()
}

function applyImportPresetById(presetId: string) {
  const preset = importPresets.value.find((item) => item.id === presetId)
  if (!preset) return
  if (!preset.available) {
    ElMessage.warning(t('projects.messages.presetUnavailable'))
    return
  }

  selectedPresetId.value = preset.id
  importForm.value = {
    ...importForm.value,
    name: preset.name,
    base_url: preset.base_url,
    openapi_url: preset.openapi_url,
    source_path: preset.source_path,
    username: preset.username,
    password: preset.password,
    login_route_id: preset.login_route_id,
    body_field_username: preset.body_field_username,
    body_field_password: preset.body_field_password,
  }

  routeOptions.value = [
    {
      route_id: preset.login_route_id,
      label: t('projects.importDialog.sampleLoginRoute'),
    },
  ]
  loginVerified.value = null
  connectionStatus.value = 'untested'
  ElMessage.success(t('projects.messages.presetApplied', { name: preset.name }))
}

async function fetchImportPresets() {
  presetLoading.value = true
  try {
    const response = await fetch('/api/projects/import-presets')
    const data = (await response.json()) as { presets?: ImportPreset[]; detail?: string }
    if (!response.ok) {
      throw new Error(data.detail || t('projects.messages.presetFetchFailed'))
    }

    importPresets.value = Array.isArray(data.presets) ? data.presets : []
    if (!selectedPresetId.value) return

    const stillExists = importPresets.value.some((preset) => preset.id === selectedPresetId.value)
    if (!stillExists) {
      selectedPresetId.value = ''
    }
  } catch {
    importPresets.value = getFallbackImportPresets()
    ElMessage.warning(t('projects.messages.presetFallback'))
  } finally {
    presetLoading.value = false
  }
}

// 测试连通性
async function testConnection() {
  if (!importForm.value.base_url) {
    ElMessage.warning(t('projects.messages.apiUrlRequired'))
    return false
  }
  
  testConnectionLoading.value = true
  try {
    const response = await fetch('/api/projects/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        base_url: importForm.value.base_url,
        openapi_url: importForm.value.openapi_url || null,
        source_path: importForm.value.source_path || null,
      })
    })
    
    const data = await response.json()
    if (!response.ok) {
      ElMessage.error(data.detail || t('projects.messages.connectionFailed'))
      connectionStatus.value = 'error'
      return false
    } else {
      connectionStatus.value = data.status === 'success' ? 'success' : 'warning'
      if (data.status === 'warning') {
        ElMessage.warning(data.message)
      }
      // 顺带存入路由列表，避免聚焦下拉框时再发一次请求
      if (data.routes && data.routes.length > 0) {
        routeOptions.value = data.routes.map((r: any) => ({
          route_id: r.route_id,
          label: `${r.method} ${r.path}${r.summary ? '  · ' + r.summary : ''}`,
        }))
      }
      return true
    }
  } catch (error) {
    connectionStatus.value = 'error'
    ElMessage.error(t('projects.messages.connectionRequestFailed'))
    return false
  } finally {
    testConnectionLoading.value = false
  }
}

// 拉取路由列表（已有缓存时跳过，刷新按钮可强制重拉）
async function fetchRoutes(force = false) {
  if (!importForm.value.base_url) return
  if (!force && routeOptions.value.length > 0) return
  routesLoading.value = true
  routeOptions.value = []
  importForm.value.login_route_id = ''
  loginVerified.value = null
  try {
    const resp = await fetch('/api/projects/fetch-routes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        base_url: importForm.value.base_url,
        openapi_url: importForm.value.openapi_url || null,
        source_path: importForm.value.source_path || null,
      }),
    })
    const data = await resp.json()
    if (!resp.ok) {
      ElMessage.error(data.detail || t('projects.messages.routesFetchFailed'))
      return
    }
    routeOptions.value = (data.routes || []).map((r: any) => ({
      route_id: r.route_id,
      label: `${r.method} ${r.path}${r.summary ? '  · ' + r.summary : ''}`,
    }))
  } catch {
    ElMessage.error(t('projects.messages.routesFetchFailed'))
  } finally {
    routesLoading.value = false
  }
}

// 验证登录
async function verifyLogin(): Promise<boolean> {
  const { base_url, login_route_id, username, password, body_field_username, body_field_password } = importForm.value
  if (!login_route_id || !username || !password) {
    ElMessage.warning(t('projects.messages.loginInfoRequired'))
    return false
  }
  loginVerifying.value = true
  loginVerified.value = null
  try {
    const resp = await fetch('/api/projects/verify-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base_url, login_route_id, username, password, body_field_username, body_field_password }),
    })
    const data = await resp.json()
    if (data.success) {
      loginVerified.value = true
      ElMessage.success(t('projects.messages.loginVerifySuccess'))
      return true
    } else {
      loginVerified.value = false
      ElMessage.error(data.message || t('projects.messages.loginVerifyFailed'))
      return false
    }
  } catch {
    loginVerified.value = false
    ElMessage.error(t('projects.messages.verifyRequestFailed'))
    return false
  } finally {
    loginVerifying.value = false
  }
}

// 提交导入
async function submitImport() {
  // 清洗源码路径，去掉两侧引号
  if (importForm.value.source_path) {
    importForm.value.source_path = importForm.value.source_path.replace(/^["']|["']$/g, '').trim()
  }

  if (!importForm.value.name || !importForm.value.base_url || !importForm.value.source_path) {
    ElMessage.warning(t('projects.messages.requiredFieldsMissing'))
    return
  }

  // 如果填写了账号密码，导入前自动补跑一次登录验证
  if (importForm.value.username && loginVerified.value !== true) {
    const verified = await verifyLogin()
    if (!verified) {
      return
    }
  }

  // 如果没有账号密码，清空 login_route_id
  if (!importForm.value.username) {
    importForm.value.login_route_id = ''
  }

  // 自动测试连通性
  const isConnected = await testConnection()
  if (!isConnected) return

  importLoading.value = true
  try {
    await projectStore.importProject(importForm.value)
    importDialogVisible.value = false
    ElMessage.success(t('projects.messages.importSuccess'))
  } catch (error) {
    console.error('导入失败:', error)
  } finally {
    importLoading.value = false
  }
}

// 触发发现
async function triggerDiscovery(projectId: string) {
  const project = projectStore.projects.find((p) => p.id === projectId)
  if (!project) return

  try {
    project.discovery_status = 'in_progress'
    await projectStore.triggerDiscovery(projectId)
    ElMessage.success(t('projects.messages.discoveryStarted'))
  } catch (error: any) {
    project.discovery_status = 'failed'
    ElMessage.error(
      t('projects.messages.discoveryFailed', {
        reason: error?.response?.data?.detail || error.message || t('common.unknown'),
      }),
    )
  }
}

// 处理点击发现按钮
async function handleDiscoveryClick(project: any) {
  if (project.discovery_status === 'completed') {
    try {
      await ElMessageBox.confirm(
        t('projects.dialogs.rediscoveryConfirm.message'),
        t('projects.dialogs.rediscoveryConfirm.title'),
        {
          confirmButtonText: t('projects.dialogs.rediscoveryConfirm.confirm'),
          cancelButtonText: t('common.cancel'),
          type: 'warning',
        }
      )
    } catch {
      return // user canceled
    }
  }
  
  triggerDiscovery(project.id)
  startPolling()
}

async function removeProject(projectId: string) {
  try {
    await ElMessageBox.confirm(
      t('projects.dialogs.deleteConfirm.message'),
      t('projects.dialogs.deleteConfirm.title'),
      {
        confirmButtonText: t('projects.dialogs.deleteConfirm.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
    await projectStore.deleteProject(projectId)
    ElMessage.success(t('projects.messages.deleteSuccess'))
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(
        t('projects.messages.deleteFailed', {
          reason: error?.response?.data?.detail || error.message || t('common.unknown'),
        }),
      )
    }
  }
}

// 进入项目聊天
function enterProject(projectId: string) {
  router.push({ path: '/', query: { project: projectId } })
}

// 描述内联编辑
function startEditDesc(project: any) {
  editingDescId.value = project.id
  editingDescValue.value = project.description || ''
}

async function saveDesc(projectId: string) {
  if (descSaving.value) return
  descSaving.value = true
  try {
    await projectStore.updateProjectDescription(projectId, editingDescValue.value)
    ElMessage.success(t('projects.messages.descSaved'))
  } catch {
    ElMessage.error(t('projects.messages.saveFailed'))
  } finally {
    descSaving.value = false
    editingDescId.value = null
  }
}

function cancelEditDesc() {
  editingDescId.value = null
}

async function refreshProjects() {
  await projectStore.fetchProjects()
}

function startPolling() {
  if (pollingTimer !== null) return
  pollingTimer = window.setInterval(async () => {
    await refreshProjects()
    if (!projectStore.projects.some((p) => p.discovery_status === 'in_progress')) {
      stopPolling()
    }
  }, 2000)
}

function stopPolling() {
  if (pollingTimer !== null) {
    window.clearInterval(pollingTimer)
    pollingTimer = null
  }
}

onMounted(async () => {
  await refreshProjects()
  if (projectStore.projects.some((p) => p.discovery_status === 'in_progress')) {
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

// 获取状态标签类型
function getStatusType(status: string): string {
  switch (status) {
    case 'completed':
      return 'success'
    case 'in_progress':
      return 'warning'
    case 'failed':
      return 'danger'
    default:
      return 'info'
  }
}

// 获取状态文本
function getStatusText(status: string): string {
  switch (status) {
    case 'completed':
      return t('projects.status.completed')
    case 'in_progress':
      return t('projects.status.inProgress')
    case 'failed':
      return t('projects.status.failed')
    case 'pending':
      return t('projects.status.pending')
    default:
      return status
  }
}
</script>

<template>
  <div class="projects-page">
    <div class="page-header">
      <h2>{{ t('projects.pageTitle') }}</h2>
      <el-button type="primary" @click="openImportDialog">
        <el-icon><Plus /></el-icon>
        {{ t('projects.importProject') }}
      </el-button>
    </div>

    <!-- 项目列表 -->
    <div class="project-grid" v-if="projectStore.projects.length > 0">
      <el-card
        v-for="project in projectStore.projects"
        :key="project.id"
        shadow="hover"
        class="project-card"
        @click="enterProject(project.id)"
      >
        <template #header>
          <div class="card-header">
            <span class="project-name">{{ project.name }}</span>
            <el-tag :type="getStatusType(project.discovery_status)" size="small">
              {{ getStatusText(project.discovery_status) }}
            </el-tag>
          </div>
        </template>

        <div class="project-info">
          <p class="info-item">
            <el-icon><Link /></el-icon>
            <span class="url-text">{{ project.base_url }}</span>
          </p>
          <!-- 描述区域：可内联编辑 -->
          <div class="description-area">
            <!-- 编辑状态 -->
            <template v-if="editingDescId === project.id">
              <el-input
                v-model="editingDescValue"
                type="textarea"
                :rows="3"
                autofocus
                :placeholder="t('projects.descriptionForm.placeholder')"
                @keydown.esc="cancelEditDesc"
              />
              <div class="desc-actions">
                <el-button size="small" type="primary" :loading="descSaving" @click="saveDesc(project.id)">{{ t('common.save') }}</el-button>
                <el-button size="small" @click="cancelEditDesc">{{ t('common.cancel') }}</el-button>
              </div>
            </template>
            <!-- 展示状态 -->
            <template v-else>
              <p
                class="info-item desc-text"
                :title="t('projects.descriptionForm.clickToEdit')"
                @click="startEditDesc(project)"
              >
                <el-icon><Document /></el-icon>
                <span v-if="project.description">{{ project.description }}</span>
                <span v-else class="desc-placeholder">{{ t('projects.descriptionForm.emptyHint') }}</span>
              </p>
            </template>
          </div>
          <p class="info-item">
            <el-icon><Clock /></el-icon>
            <span>{{ new Date(project.created_at).toLocaleString() }}</span>
          </p>
          <!-- 发现进度条 -->
          <div v-if="project.discovery_status === 'in_progress'" class="discovery-progress">
            <el-progress :percentage="project.discovery_progress || 0" :stroke-width="8" />
            <span class="progress-hint">{{ project.discovery_message || t('projects.progressHint') }}</span>
          </div>
          <div v-if="project.discovery_status === 'failed' && project.discovery_error" class="error-hint">
            <el-icon style="color: var(--el-color-danger)"><WarningFilled /></el-icon>
            <span class="error-text">{{ project.discovery_error?.slice(0, 80) }}</span>
          </div>
        </div>

        <div class="project-actions">
          <el-button
            size="small"
            type="primary"
            @click.stop="enterProject(project.id)"
            :disabled="project.discovery_status !== 'completed'"
            :title="project.discovery_status !== 'completed' ? t('projects.actions.enterChatHint') : ''"
          >
            <el-icon><ChatRound /></el-icon> {{ t('projects.actions.enterChat') }}
          </el-button>
          <el-button
            size="small"
            :type="project.discovery_status === 'failed' ? 'danger' : 'default'"
            @click.stop="handleDiscoveryClick(project)"
            :loading="project.discovery_status === 'in_progress'"
            :disabled="project.discovery_status === 'in_progress'"
          >
            <template v-if="project.discovery_status === 'completed'">
              <Icon icon="solar:refresh-circle-bold-duotone" style="margin-right: 4px; vertical-align: middle;" />{{ t('projects.actions.rediscover') }}
            </template>
            <template v-else-if="project.discovery_status === 'in_progress'">
              {{ t('projects.actions.discovering') }}
            </template>
            <template v-else>
              {{ project.discovery_status === 'failed' ? t('projects.actions.retryDiscovery') : t('projects.actions.startDiscovery') }}
            </template>
          </el-button>
          <el-button
            size="small"
            type="danger"
            plain
            @click.stop="removeProject(project.id)"
          >
            {{ t('common.delete') }}
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 空状态 -->
    <el-empty v-else :description="t('projects.emptyState')">
      <el-button type="primary" @click="openImportDialog">{{ t('projects.importFirstProject') }}</el-button>
    </el-empty>

    <!-- 导入对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      :title="t('projects.importDialog.title')"
      width="500px"
    >
      <el-form :model="importForm" label-width="100px">
        <el-form-item :label="t('projects.importDialog.presetsLabel')">
          <div class="preset-actions">
            <el-button
              v-for="preset in importPresets"
              :key="preset.id"
              size="small"
              :type="selectedPresetId === preset.id ? 'primary' : 'default'"
              :plain="selectedPresetId !== preset.id"
              :disabled="!preset.available"
              @click="applyImportPresetById(preset.id)"
            >
              {{ preset.name }}
            </el-button>
          </div>
          <div v-if="selectedPreset" class="preset-selected">
            <div>{{ selectedPreset.description }}</div>
            <div class="preset-source">{{ t('projects.importDialog.selectedPresetSourcePath', { path: selectedPreset.source_path }) }}</div>
            <div class="preset-source">{{ t('projects.importDialog.selectedPresetCredentials', { username: selectedPreset.username, password: selectedPreset.password }) }}</div>
          </div>
        </el-form-item>
        <el-form-item :label="t('projects.importDialog.fields.name.label')" required>
          <el-input v-model="importForm.name" :placeholder="t('projects.importDialog.fields.name.placeholder')" />
        </el-form-item>
        <el-form-item :label="t('projects.importDialog.fields.apiUrl.label')" required>
          <el-input v-model="importForm.base_url" :placeholder="t('projects.importDialog.fields.apiUrl.placeholder')" />
        </el-form-item>
        <el-form-item :label="t('projects.importDialog.fields.openapiUrl.label')">
          <el-input v-model="importForm.openapi_url" :placeholder="t('projects.importDialog.fields.openapiUrl.placeholder')" />
        </el-form-item>
        <el-form-item :label="t('projects.importDialog.fields.sourcePath.label')" required>
          <el-input v-model="importForm.source_path" :placeholder="t('projects.importDialog.fields.sourcePath.placeholder')" />
        </el-form-item>
        <el-form-item :label="t('projects.importDialog.fields.description.label')">
          <el-input
            v-model="importForm.description"
            type="textarea"
            :rows="3"
            :placeholder="t('projects.importDialog.fields.description.placeholder')"
          />
        </el-form-item>

        <el-divider>{{ t('projects.importDialog.authSection.title') }}</el-divider>
        <el-alert
          :title="t('projects.importDialog.authSection.alert')"
          type="info"
          show-icon
          :closable="false"
          style="margin-bottom: 16px;"
        />
        <div class="preset-help preset-credential-hint">
          {{ t('projects.importDialog.authSection.help') }}
        </div>
        <el-form-item :label="t('projects.importDialog.fields.username.label')">
          <el-input v-model="importForm.username" :placeholder="t('projects.importDialog.fields.username.placeholder')" @change="loginVerified = null" />
        </el-form-item>
        <el-form-item :label="t('projects.importDialog.fields.password.label')">
          <el-input v-model="importForm.password" type="password" :placeholder="t('projects.importDialog.fields.password.placeholder')" show-password @change="loginVerified = null" />
        </el-form-item>
        <template v-if="importForm.username">
          <el-form-item :label="t('projects.importDialog.fields.loginRoute.label')">
            <div style="display:flex;gap:8px;width:100%">
              <el-select
                v-model="importForm.login_route_id"
                filterable
                :placeholder="t('projects.importDialog.fields.loginRoute.placeholder')"
                style="flex:1"
                :loading="routesLoading"
                @focus="routeOptions.length === 0 && fetchRoutes()"
                @change="loginVerified = null"
              >
                <el-option
                  v-for="r in routeOptions"
                  :key="r.route_id"
                  :label="r.label"
                  :value="r.route_id"
                />
              </el-select>
              <el-button :loading="routesLoading" @click="fetchRoutes(true)">{{ t('projects.importDialog.fields.loginRoute.refresh') }}</el-button>
            </div>
          </el-form-item>
          <el-form-item :label="t('projects.importDialog.fields.usernameField.label')">
            <el-input v-model="importForm.body_field_username" :placeholder="t('projects.importDialog.fields.usernameField.placeholder')" @change="loginVerified = null" />
          </el-form-item>
          <el-form-item :label="t('projects.importDialog.fields.passwordField.label')">
            <el-input v-model="importForm.body_field_password" :placeholder="t('projects.importDialog.fields.passwordField.placeholder')" @change="loginVerified = null" />
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <div class="dialog-footer-row">
          <el-button
            class="verify-login-btn"
            :loading="loginVerifying"
            @click="verifyLogin"
          >
            {{ loginVerified === true ? t('projects.importDialog.verifyLogin.success') : loginVerified === false ? t('projects.importDialog.verifyLogin.failed') : t('projects.importDialog.verifyLogin.idle') }}
          </el-button>
          <div class="dialog-footer-actions">
            <el-button @click="importDialogVisible = false">{{ t('projects.importDialog.footer.cancel') }}</el-button>
            <el-button
              type="primary"
              @click="submitImport"
              :loading="importLoading || testConnectionLoading"
            >
              {{ t('projects.importDialog.footer.import') }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.projects-page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 32px 40px;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color-light, #e5e5e5);
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary, #0f0f0f);
  letter-spacing: -0.5px;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
  padding-bottom: 40px;
}

.project-card {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 220px;
  background: #ffffff;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.project-name {
  font-weight: 600;
  font-size: 16px;
  color: var(--color-text-primary, #0f0f0f);
}

.project-info {
  margin-bottom: 20px;
  flex: 1;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
  color: var(--color-text-secondary, #737373);
  font-size: 13px;
}

.project-actions {
  display: flex;
  gap: 12px;
  margin-top: auto;
  border-top: 1px solid var(--border-color-light, #e5e5e5);
  padding-top: 16px;
}

.description-area {
  margin: 12px 0;
}

.desc-text {
  cursor: pointer;
  border-radius: 0;
  padding: 6px 8px;
  margin: 4px -8px;
  transition: background 0.2s ease;
  line-height: 1.6;
  word-break: break-all;
  border-left: 2px solid transparent;
}

.desc-text:hover {
  background: #f4f4f4;
  border-left-color: #a3a3a3;
}

.desc-placeholder {
  color: #a3a3a3;
  font-style: italic;
  font-size: 13px;
}

.desc-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.url-text {
  font-family: var(--font-mono);
  font-size: 12px;
  word-break: break-all;
}

.preset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.preset-help {
  width: 100%;
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-text-secondary, #737373);
  line-height: 1.5;
}

.preset-selected {
  width: 100%;
  margin-top: 8px;
  padding: 8px 10px;
  border: 1px dashed #d4d4d8;
  background: #fafafa;
  font-size: 12px;
  color: var(--color-text-primary, #0f0f0f);
  line-height: 1.5;
}

.preset-source {
  margin-top: 4px;
  font-family: var(--font-mono);
  word-break: break-all;
}

.dialog-footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  flex-wrap: wrap;
}

.dialog-footer-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.verify-login-btn {
  background-color: #2f3136;
  border-color: #2f3136;
  color: #ffffff;
}

.verify-login-btn:hover,
.verify-login-btn:focus {
  background-color: #1f2125;
  border-color: #1f2125;
  color: #ffffff;
}

.verify-login-btn.is-loading {
  opacity: 0.92;
}

.progress-hint {
  font-size: 12px;
  color: var(--color-text-secondary, #737373);
  margin-top: 8px;
  display: block;
}

.error-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  background: #fffafa;
  border: 1px solid #ffcccc;
  border-radius: 0;
}

.error-text {
  font-size: 12px;
  color: #cc0000;
  word-break: break-all;
  line-height: 1.5;
}

:deep(.el-tag) {
  border-radius: 0 !important;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 11px;
}

/* ================= 移动端适配 (断点 768px) ================= */
@media (max-width: 768px) {
  .projects-page {
    padding: 16px 5%; /* 使用百分比适配窄屏幕 */
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 24px;
  }

  .project-grid {
    grid-template-columns: 1fr; /* 单列显示 */
    gap: 16px;
  }

  .project-card {
    min-height: auto; /* 移除最小高度，内容自适应 */
    width: 100%;
    box-sizing: border-box; /* 确保不溢出 */
  }

  .project-actions {
    flex-direction: column;
    gap: 8px;
  }

  .project-actions .el-button {
    width: 100%;
    margin-left: 0 !important;
  }

  /* 修复弹窗溢出 */
  :deep(.el-dialog) {
    width: 90% !important;
    max-width: 500px;
    margin: 0 auto;
  }

  :deep(.el-dialog__body) {
    padding: 16px 5%;
  }

  /* 修复表单显示不全，转换为列布局 */
  :deep(.el-form-item) {
    flex-direction: column;
    align-items: flex-start;
    margin-bottom: 16px;
  }

  :deep(.el-form-item__label) {
    width: 100% !important;
    text-align: left;
    margin-bottom: 8px;
    line-height: 1.2;
    float: none; /* 清除默认浮动 */
  }

  :deep(.el-form-item__content) {
    width: 100%;
    margin-left: 0 !important;
  }

  /* 底部按钮自适应 */
  .dialog-footer-row {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .dialog-footer-actions {
    margin-left: 0;
    justify-content: space-between;
    width: 100%;
  }

  .dialog-footer-actions .el-button {
    flex: 1;
    margin-left: 8px;
  }

  .dialog-footer-actions .el-button:first-child {
    margin-left: 0;
  }
}
</style>
