<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useProjectStore } from '@/stores/project'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const projectId = computed(() => route.params.id as string)

// 项目状态
const project = ref<any>(null)
const routeMap = ref<any>(null)
const capabilities = ref<any[]>([])
const loading = ref(true)
const discoveringLoading = ref(false)

// 按 domain 分组能力
const capabilityGroups = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const cap of capabilities.value) {
    const domain = cap.domain || 'unknown'
    if (!groups[domain]) groups[domain] = []
    groups[domain].push(cap)
  }
  return groups
})

const domainInfo: Record<string, { label: string; icon: string }> = {
  auth: { label: '认证与授权', icon: 'solar:lock-password-bold-duotone' },
  user: { label: '用户管理', icon: 'solar:user-circle-bold-duotone' },
  admin: { label: '管理员操作', icon: 'solar:shield-check-bold-duotone' },
  finance: { label: '账务与计费', icon: 'solar:card-transfer-bold-duotone' },
  content: { label: '内容管理', icon: 'solar:document-text-bold-duotone' },
  storage: { label: '数据与存储', icon: 'solar:database-bold-duotone' },
  analytics: { label: '统计与分析', icon: 'solar:chart-square-bold-duotone' },
  notification: { label: '通知与推送', icon: 'solar:bell-bing-bold-duotone' },
  system: { label: '系统配置', icon: 'solar:settings-bold-duotone' },
  integration: { label: '集成与外部接口', icon: 'solar:link-round-bold-duotone' },
  unknown: { label: '未分类', icon: 'solar:help-circle-bold-duotone' },
}

function getDomainLabel(domain: string): string {
  return domainInfo[domain]?.label || domain
}

function getDomainIcon(domain: string): string {
  return domainInfo[domain]?.icon || 'solar:pin-bold-duotone'
}

function getSafetyType(safety: string): string {
  if (safety === 'readonly_safe') return 'success'
  if (safety === 'critical') return 'danger'
  return 'warning'
}

function getMethodType(method: string): string {
  if (method === 'GET') return 'success'
  if (method === 'DELETE') return 'danger'
  if (method === 'POST') return 'primary'
  return 'info'
}

// 获取项目详情
async function fetchProjectDetails() {
  loading.value = true
  try {
    const statusRes = await axios.get(`/api/projects/${projectId.value}/status`)
    project.value = statusRes.data

    try {
      const routeRes = await axios.get(`/api/projects/${projectId.value}/route-map`)
      routeMap.value = routeRes.data
    } catch {
      routeMap.value = null
    }

    try {
      const capRes = await axios.get(`/api/projects/${projectId.value}/capabilities`)
      capabilities.value = capRes.data.capabilities || []
    } catch {
      capabilities.value = []
    }
  } catch (error) {
    console.error('获取项目详情失败:', error)
    ElMessage.error('获取项目详情失败')
  } finally {
    loading.value = false
  }
}

// 触发发现
async function triggerDiscovery() {
  discoveringLoading.value = true
  try {
    await axios.post(`/api/projects/${projectId.value}/discover`)
    ElMessage.success('发现任务完成！')
    await fetchProjectDetails()
  } catch (error: any) {
    ElMessage.error('发现失败: ' + (error?.response?.data?.detail || error.message))
  } finally {
    discoveringLoading.value = false
  }
}

// 进入对话
async function enterChat() {
  // 从列表中找到这个项目，并设置为当前项目
  const found = projectStore.projects.find((p) => p.id === projectId.value)
  if (found) {
    projectStore.currentProject = found
  }
  router.push('/chat')
}

onMounted(() => {
  fetchProjectDetails()
})
</script>

<template>
  <div class="project-detail-page">
    <div class="page-header">
      <el-button @click="$router.push('/projects')" :icon="'ArrowLeft'" text>
        返回项目列表
      </el-button>
      <h2>{{ project?.name || '项目详情' }}</h2>
      <div class="header-actions">
        <el-button
          type="primary"
          @click="enterChat"
          :disabled="project?.status !== 'completed'"
          :title="project?.status !== 'completed' ? '请先完成发现流程' : ''"
        >
          <Icon icon="solar:chat-round-dots-bold-duotone" style="margin-right: 6px; font-size: 16px; vertical-align: -2px;" />
          进入对话
        </el-button>
        <el-button
          @click="triggerDiscovery"
          :loading="discoveringLoading"
          :disabled="project?.status === 'in_progress' || discoveringLoading"
        >
          {{ project?.status === 'completed' ? '重新发现' : '开始发现' }}
        </el-button>
      </div>
    </div>

    <el-skeleton :loading="loading" animated :rows="8">
      <template #default>
        <!-- 项目概览 -->
        <el-card class="info-card">
          <template #header>
            <div class="card-header">
              <span>项目概览</span>
              <el-tag :type="project?.status === 'completed' ? 'success' : project?.status === 'in_progress' ? 'warning' : 'info'">
                {{ ({'completed': '已完成', 'in_progress': '发现中', 'failed': '失败', 'pending': '待发现'} as Record<string, string>)[project?.status] || project?.status }}
              </el-tag>
            </div>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="API 地址">{{ project?.base_url }}</el-descriptions-item>
            <el-descriptions-item label="路由数量">{{ project?.route_count || 0 }} 条</el-descriptions-item>
            <el-descriptions-item label="能力数量">{{ project?.capability_count || 0 }} 个</el-descriptions-item>
            <el-descriptions-item label="项目ID"><code style="font-size:11px">{{ projectId }}</code></el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 路由地图 -->
        <el-card class="info-card" v-if="routeMap">
          <template #header>
            <div class="card-header">
              <span>路由地图</span>
              <el-tag type="info">共 {{ routeMap.route_count }} 条</el-tag>
            </div>
          </template>
          <el-table :data="routeMap.routes?.slice(0, 20)" style="width: 100%" stripe>
            <el-table-column prop="method" label="方法" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="getMethodType(row.method)">{{ row.method }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="path" label="路径" min-width="180" />
            <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
          </el-table>
          <div class="more-hint" v-if="routeMap.route_count > 20">
            仅显示前 20 条，共 {{ routeMap.route_count }} 条路由
          </div>
        </el-card>

        <!-- 能力图谱（按领域分组） -->
        <el-card class="info-card" v-if="capabilities.length > 0">
          <template #header>
            <div class="card-header">
              <span>能力图谱</span>
              <el-tag>共 {{ capabilities.length }} 个能力 · {{ Object.keys(capabilityGroups).length }} 个领域</el-tag>
            </div>
          </template>

          <div v-for="(caps, domain) in capabilityGroups" :key="domain" class="domain-group">
            <div class="domain-label">
              <Icon :icon="getDomainIcon(domain as string)" style="margin-right: 8px; vertical-align: middle; font-size: 18px;" />
              <span>{{ getDomainLabel(domain as string) }}</span>
            </div>
            <div class="capability-grid">
              <el-card
                v-for="cap in caps"
                :key="cap.capability_id"
                shadow="hover"
                class="capability-card"
              >
                <div class="cap-name">{{ cap.name }}</div>
                <div class="cap-tags">
                  <el-tag size="small" :type="getSafetyType(cap.safety_level)">
                    {{ cap.safety_level }}
                  </el-tag>
                  <el-tag size="small" type="info" v-if="cap.permission_level">
                    {{ cap.permission_level }}
                  </el-tag>
                </div>
                <div class="cap-desc" v-if="cap.description">{{ cap.description }}</div>
              </el-card>
            </div>
          </div>
        </el-card>

        <el-empty
          v-if="!loading && capabilities.length === 0"
          description="尚无能力图谱数据，请先触发发现流程"
        />
      </template>
    </el-skeleton>
  </div>
</template>

<style scoped>
.project-detail-page {
  height: 100%;
  overflow-y: auto;
  padding: 32px 40px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.page-header h2 {
  flex: 1;
  margin: 0;
  font-size: 20px;
  font-weight: 700;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.info-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.more-hint {
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 12px;
  margin-top: 10px;
}

.domain-group {
  margin-bottom: 24px;
}

.domain-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
  padding-left: 4px;
  border-left: 3px solid var(--el-color-primary);
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.capability-card {
  cursor: default;
  font-size: 13px;
}

.cap-name {
  font-weight: 600;
  margin-bottom: 8px;
  line-height: 1.4;
}

.cap-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 6px;
}

.cap-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
