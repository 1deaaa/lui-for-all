<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/stores/project'

const projectStore = useProjectStore()
const router = useRouter()
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

const FALLBACK_IMPORT_PRESETS: ImportPreset[] = [
  {
    id: 'sample-fastapi',
    name: 'FastAPI 示例（Docker）',
    description: '自动填充容器内 FastAPI 示例地址与源码目录。',
    base_url: 'http://sample-fastapi:8010',
    openapi_url: 'http://sample-fastapi:8010/openapi.json',
    source_path: '/app/backend_for_test/fastapi_sample',
    login_route_id: 'POST:/api/auth/login',
    body_field_username: 'username',
    body_field_password: 'password',
    available: true,
  },
  {
    id: 'sample-node',
    name: 'Node 示例（Docker）',
    description: '自动填充容器内 Node 示例地址与源码目录。',
    base_url: 'http://sample-node:8020',
    openapi_url: 'http://sample-node:8020/openapi.json',
    source_path: '/app/backend_for_test/node_sample',
    login_route_id: 'POST:/api/auth/login',
    body_field_username: 'username',
    body_field_password: 'password',
    available: true,
  },
]

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
    ElMessage.warning('该预置在当前环境不可用，请检查示例目录是否存在')
    return
  }

  selectedPresetId.value = preset.id
  importForm.value = {
    ...importForm.value,
    name: preset.name,
    base_url: preset.base_url,
    openapi_url: preset.openapi_url,
    source_path: preset.source_path,
    login_route_id: preset.login_route_id,
    body_field_username: preset.body_field_username,
    body_field_password: preset.body_field_password,
  }

  routeOptions.value = [
    {
      route_id: preset.login_route_id,
      label: 'POST /api/auth/login  · 示例登录接口',
    },
  ]
  loginVerified.value = null
  connectionStatus.value = 'untested'
  ElMessage.success(`已填充预置：${preset.name}`)
}

async function fetchImportPresets() {
  presetLoading.value = true
  try {
    const response = await fetch('/api/projects/import-presets')
    const data = (await response.json()) as { presets?: ImportPreset[]; detail?: string }
    if (!response.ok) {
      throw new Error(data.detail || '获取预置失败')
    }

    importPresets.value = Array.isArray(data.presets) ? data.presets : []
    if (!selectedPresetId.value) return

    const stillExists = importPresets.value.some((preset) => preset.id === selectedPresetId.value)
    if (!stillExists) {
      selectedPresetId.value = ''
    }
  } catch {
    importPresets.value = FALLBACK_IMPORT_PRESETS
    ElMessage.warning('未能从后端读取预置，已使用默认示例配置')
  } finally {
    presetLoading.value = false
  }
}

// 测试连通性
async function testConnection() {
  if (!importForm.value.base_url) {
    ElMessage.warning('请先填写 API 地址')
    return false
  }
  
  testConnectionLoading.value = true
  try {
    const response = await fetch('/api/projects/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        base_url: importForm.value.base_url,
        openapi_url: importForm.value.openapi_url || null
      })
    })
    
    const data = await response.json()
    if (!response.ok) {
      ElMessage.error(data.detail || '连接失败')
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
    ElMessage.error('测试请求发出失败，请检查浏览器代理或网络')
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
      }),
    })
    const data = await resp.json()
    if (!resp.ok) {
      ElMessage.error(data.detail || '获取路由失败')
      return
    }
    routeOptions.value = (data.routes || []).map((r: any) => ({
      route_id: r.route_id,
      label: `${r.method} ${r.path}${r.summary ? '  · ' + r.summary : ''}`,
    }))
  } catch {
    ElMessage.error('获取路由失败')
  } finally {
    routesLoading.value = false
  }
}

// 验证登录
async function verifyLogin() {
  const { base_url, login_route_id, username, password, body_field_username, body_field_password } = importForm.value
  if (!login_route_id || !username || !password) {
    ElMessage.warning('请先选择登录接口并填写账号密码')
    return
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
      ElMessage.success('登录验证成功')
    } else {
      loginVerified.value = false
      ElMessage.error(data.message || '登录验证失败')
    }
  } catch {
    loginVerified.value = false
    ElMessage.error('验证请求失败')
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
    ElMessage.warning('项目名称、API 地址和本地源码路径均为必填项')
    return
  }

  // 如果填了账号密码但未通过登录验证，阻止提交
  if (importForm.value.username && loginVerified.value !== true) {
    ElMessage.warning('请先完成登录接口验证')
    return
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
    ElMessage.success('项目导入成功')
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
    ElMessage.success('项目发现任务已启动')
  } catch (error: any) {
    project.discovery_status = 'failed'
    ElMessage.error('发现失败: ' + (error?.response?.data?.detail || error.message || '未知错误'))
  }
}

// 处理点击发现按钮
async function handleDiscoveryClick(project: any) {
  if (project.discovery_status === 'completed') {
    try {
      await ElMessageBox.confirm(
        '重新建模将清除已生成的认知图谱和权限映射数据，并重新拉取 OpenAPI 进行分析。这个过程需要耗费一些时间，是否确定重新建模？',
        '重新建模确认',
        {
          confirmButtonText: '确定重构',
          cancelButtonText: '取消',
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
      '确定要删除该项目吗？删除后将无法恢复，所有关联的发现数据和会话记录都将被清除。',
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await projectStore.deleteProject(projectId)
    ElMessage.success('项目已删除')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error?.response?.data?.detail || error.message || '未知错误'))
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
    ElMessage.success('描述已保存')
  } catch {
    ElMessage.error('保存失败')
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
      return '已完成'
    case 'in_progress':
      return '进行中'
    case 'failed':
      return '失败'
    case 'pending':
      return '待处理'
    default:
      return status
  }
}
</script>

<template>
  <div class="projects-page">
    <div class="page-header">
      <h2>项目管理</h2>
      <el-button type="primary" @click="openImportDialog">
        <el-icon><Plus /></el-icon>
        导入项目
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
                placeholder="输入描述（可纳正 AI 生成的内容）"
                @keydown.esc="cancelEditDesc"
              />
              <div class="desc-actions">
                <el-button size="small" type="primary" :loading="descSaving" @click="saveDesc(project.id)">保存</el-button>
                <el-button size="small" @click="cancelEditDesc">取消</el-button>
              </div>
            </template>
            <!-- 展示状态 -->
            <template v-else>
              <p
                class="info-item desc-text"
                :title="'点击编辑描述'"
                @click="startEditDesc(project)"
              >
                <el-icon><Document /></el-icon>
                <span v-if="project.description">{{ project.description }}</span>
                <span v-else class="desc-placeholder">点击添加描述（AI 将在建图后自动填充）</span>
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
            <span class="progress-hint">{{ project.discovery_message || 'AI 正在建模、请稍候...' }}</span>
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
            :title="project.discovery_status !== 'completed' ? '请先完成项目发现' : ''"
          >
            <el-icon><ChatRound /></el-icon> 开始对话
          </el-button>
          <el-button
            size="small"
            :type="project.discovery_status === 'failed' ? 'danger' : 'default'"
            @click.stop="handleDiscoveryClick(project)"
            :loading="project.discovery_status === 'in_progress'"
            :disabled="project.discovery_status === 'in_progress'"
          >
            <template v-if="project.discovery_status === 'completed'">
              <Icon icon="solar:refresh-circle-bold-duotone" style="margin-right: 4px; vertical-align: middle;" />重新建模
            </template>
            <template v-else-if="project.discovery_status === 'in_progress'">
              建模中...
            </template>
            <template v-else>
              {{ project.discovery_status === 'failed' ? '重试发现' : '开始发现' }}
            </template>
          </el-button>
          <el-button
            size="small"
            type="danger"
            plain
            @click.stop="removeProject(project.id)"
          >
            删除
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 空状态 -->
    <el-empty v-else description="暂无项目">
      <el-button type="primary" @click="openImportDialog">导入第一个项目</el-button>
    </el-empty>

    <!-- 导入对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      title="导入项目"
      width="500px"
    >
      <el-form :model="importForm" label-width="100px">
        <el-form-item label="示例预置">
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
            <el-button size="small" text :loading="presetLoading" @click="fetchImportPresets">刷新</el-button>
          </div>
          <div class="preset-help">
            点击预置可自动填充 API 地址、OpenAPI 地址与源码目录。
          </div>
          <div v-if="selectedPreset" class="preset-selected">
            <div>{{ selectedPreset.description }}</div>
            <div class="preset-source">源码目录：{{ selectedPreset.source_path }}</div>
          </div>
        </el-form-item>
        <el-form-item label="项目名称" required>
          <el-input v-model="importForm.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="API 地址" required>
          <el-input v-model="importForm.base_url" placeholder="http://localhost:6689" />
        </el-form-item>
        <el-form-item label="OpenAPI 地址">
          <el-input v-model="importForm.openapi_url" placeholder="/openapi.json" />
        </el-form-item>
        <el-form-item label="源码路径" required>
          <el-input v-model="importForm.source_path" placeholder="例如：D:\Projects\my-backend" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="importForm.description"
            type="textarea"
            :rows="3"
            placeholder="项目描述"
          />
        </el-form-item>

        <el-divider>认证拦截解决方案</el-divider>
        <el-alert
          title="对于需要登录才能访问的系统，填写账号密码并选择登录接口。验证通过后，AI 每次执行任务时会自动先登录获取 token。"
          type="info"
          show-icon
          :closable="false"
          style="margin-bottom: 16px;"
        />
        <el-form-item label="Username">
          <el-input v-model="importForm.username" placeholder="管理员账号 (选填)" @change="loginVerified = null" />
        </el-form-item>
        <el-form-item label="Password">
          <el-input v-model="importForm.password" type="password" placeholder="管理员密码 (选填)" show-password @change="loginVerified = null" />
        </el-form-item>
        <template v-if="importForm.username">
          <el-form-item label="登录接口">
            <div style="display:flex;gap:8px;width:100%">
              <el-select
                v-model="importForm.login_route_id"
                filterable
                placeholder="选择或搜索登录接口"
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
              <el-button :loading="routesLoading" @click="fetchRoutes(true)">刷新</el-button>
            </div>
          </el-form-item>
          <el-form-item label="用户名字段">
            <el-input v-model="importForm.body_field_username" placeholder="username" @change="loginVerified = null" />
          </el-form-item>
          <el-form-item label="密码字段">
            <el-input v-model="importForm.body_field_password" placeholder="password" @change="loginVerified = null" />
          </el-form-item>
          <el-form-item label=" ">
            <el-button
              :loading="loginVerifying"
              :type="loginVerified === true ? 'success' : loginVerified === false ? 'danger' : 'primary'"
              @click="verifyLogin"
            >
              {{ loginVerified === true ? '✓ 验证通过' : loginVerified === false ? '✗ 验证失败，重试' : '验证登录' }}
            </el-button>
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          @click="submitImport"
          :loading="importLoading || testConnectionLoading"
        >
          导入项目
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.projects-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 32px 40px;
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
</style>
