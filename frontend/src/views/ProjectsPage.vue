<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/stores/project'

const projectStore = useProjectStore()
const router = useRouter()
let pollingTimer: number | null = null

// 导入表单
const importForm = ref({
  name: '',
  base_url: 'http://localhost:',
  openapi_url: '',
  description: '',
  source_path: '',
  username: '',
  password: '',
})

const importDialogVisible = ref(false)
const importLoading = ref(false)
const testConnectionLoading = ref(false)
const connectionStatus = ref<'untested' | 'success' | 'warning' | 'error'>('untested')

// 打开导入对话框
function openImportDialog() {
  importForm.value = {
    name: '',
    base_url: 'http://localhost:',
    openapi_url: '',
    description: '',
    source_path: '',
    username: '',
    password: '',
  }
  connectionStatus.value = 'untested'
  importDialogVisible.value = true
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

async function removeProject(projectId: string) {
  try {
    await projectStore.deleteProject(projectId)
    ElMessage.success('项目已删除')
  } catch (error: any) {
    ElMessage.error('删除失败: ' + (error?.response?.data?.detail || error.message || '未知错误'))
  }
}

// 进入项目聊天
function enterProject(projectId: string) {
  router.push({ path: '/', query: { project: projectId } })
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
          <p class="info-item" v-if="project.description">
            <el-icon><Document /></el-icon>
            <span>{{ project.description }}</span>
          </p>
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
            @click.stop="triggerDiscovery(project.id); startPolling()"
            :loading="project.discovery_status === 'in_progress'"
            :disabled="project.discovery_status === 'completed' || project.discovery_status === 'in_progress'"
          >
            <template v-if="project.discovery_status === 'completed'">
              ✓ 已建模
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
        <el-form-item label="项目名称" required>
          <el-input v-model="importForm.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="API 地址" required>
          <el-input v-model="importForm.base_url" placeholder="http://localhost:8000" />
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
          title="强烈建议：对于必须登录才能使用大部分接口的私有系统，请务必填写预置账密！如果接口出现401，这将赋权大模型替您主动调用目标系统的 /login 或 /token 进而捕获授权供后续接力使用。" 
          type="warning" 
          show-icon 
          :closable="false"
          style="margin-bottom: 20px;"
        />
        <el-form-item label="Username">
          <el-input v-model="importForm.username" placeholder="预置自动化大模型登录账号 (选填)" />
        </el-form-item>
        <el-form-item label="Password">
          <el-input v-model="importForm.password" type="password" placeholder="预置自动化大模型登录密码 (选填)" show-password />
        </el-form-item>
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
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  color: var(--color-text-primary);
  letter-spacing: -0.5px;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
  padding-bottom: 20px;
}

.project-card {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 200px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.project-name {
  font-weight: 700;
  font-size: 18px;
  color: var(--color-text-primary);
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
  color: var(--color-text-secondary);
  font-size: 14px;
}

.project-actions {
  display: flex;
  gap: 12px;
  margin-top: auto;
  border-top: 1px solid var(--border-color-light);
  padding-top: 16px;
}
</style>
