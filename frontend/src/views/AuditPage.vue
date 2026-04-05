<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

// ==================== 状态 ====================
const activeTab = ref('tasks')
const loading = ref(false)

// 任务运行
const taskRuns = ref<any[]>([])

// HTTP 执行
const httpExecs = ref<any[]>([])
const expandedRows = ref<Set<string>>(new Set())

// 审批日志
const approvals = ref<any[]>([])

// ==================== 数据获取 ====================
async function fetchTaskRuns() {
  loading.value = true
  try {
    const res = await axios.get('/api/audit/task-runs?limit=50')
    taskRuns.value = res.data.task_runs || []
  } catch (e) {
    console.error('获取任务运行列表失败:', e)
  } finally {
    loading.value = false
  }
}

async function fetchHttpExecs() {
  loading.value = true
  try {
    const res = await axios.get('/api/audit/http-executions?limit=50')
    httpExecs.value = res.data.executions || []
  } catch (e) {
    console.error('获取 HTTP 执行记录失败:', e)
  } finally {
    loading.value = false
  }
}

async function fetchApprovals() {
  loading.value = true
  try {
    const res = await axios.get('/api/audit/approvals?limit=50')
    approvals.value = res.data.approvals || []
  } catch (e) {
    console.error('获取审批日志失败:', e)
  } finally {
    loading.value = false
  }
}

function handleTabChange(tab: string) {
  activeTab.value = tab
  if (tab === 'tasks') fetchTaskRuns()
  else if (tab === 'http') fetchHttpExecs()
  else if (tab === 'policy') fetchApprovals()
}

function refreshCurrent() {
  handleTabChange(activeTab.value)
}

// ==================== 工具函数 ====================
function formatTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function getTaskStatusType(status: string): string {
  if (['completed'].includes(status)) return 'success'
  if (['running', 'waiting_approval', 'waiting_params'].includes(status)) return 'warning'
  if (['failed', 'cancelled'].includes(status)) return 'danger'
  return 'info'
}

function getHttpStatusType(code: number | null): string {
  if (!code) return 'info'
  if (code >= 200 && code < 300) return 'success'
  if (code >= 400 && code < 500) return 'warning'
  if (code >= 500) return 'danger'
  return 'info'
}

function getApprovalStatusType(status: string): string {
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'pending') return 'warning'
  if (status === 'timeout') return 'info'
  return 'info'
}

function getRiskTagType(risk: string): string {
  if (risk === 'high' || risk === 'critical') return 'danger'
  if (risk === 'medium') return 'warning'
  return 'success'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    approved: '已批准', rejected: '已拒绝', pending: '待审批', timeout: '已超时'
  }
  return map[status] || status
}

function methodTagType(method: string): string {
  if (method === 'GET') return 'success'
  if (method === 'POST') return 'primary'
  if (method === 'PUT' || method === 'PATCH') return 'warning'
  if (method === 'DELETE') return 'danger'
  return 'info'
}

function formatJson(val: any): string {
  if (!val) return '(空)'
  try {
    return JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}

function toggleExpand(id: string) {
  if (expandedRows.value.has(id)) {
    expandedRows.value.delete(id)
  } else {
    expandedRows.value.add(id)
  }
}

onMounted(() => {
  fetchTaskRuns()
})
</script>

<template>
  <div class="audit-page">
    <div class="page-header">
      <div>
        <h2>审计日志</h2>
        <p class="subtitle">查看任务运行、HTTP 调用与审批操作的完整记录</p>
      </div>
      <el-button @click="refreshCurrent" :loading="loading" round>
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <el-tabs v-model="activeTab" @tab-change="handleTabChange" class="audit-tabs">

      <!-- ========== 任务运行 ========== -->
      <el-tab-pane label="任务运行" name="tasks">
        <el-table :data="taskRuns" style="width: 100%" v-loading="loading" stripe>
          <el-table-column prop="id" label="任务ID" width="260">
            <template #default="{ row }">
              <el-text truncated class="mono">{{ row.id }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="getTaskStatusType(row.status)" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="user_message" label="用户消息" min-width="200">
            <template #default="{ row }">
              <el-text truncated>{{ row.user_message }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
        <div v-if="!loading && taskRuns.length === 0" class="empty-hint">
          <el-empty description="暂无任务运行记录" />
        </div>
      </el-tab-pane>

      <!-- ========== HTTP 执行 ========== -->
      <el-tab-pane label="HTTP 执行" name="http">
        <el-table :data="httpExecs" style="width: 100%" v-loading="loading" stripe>
          <el-table-column prop="created_at" label="时间" width="180">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="method" label="方法" width="80">
            <template #default="{ row }">
              <el-tag :type="methodTagType(row.method)" size="small" effect="plain">{{ row.method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="url_redacted" label="请求 URL" min-width="240">
            <template #default="{ row }">
              <el-text truncated class="mono url-text">{{ row.url_redacted }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="status_code" label="状态码" width="90">
            <template #default="{ row }">
              <el-tag :type="getHttpStatusType(row.status_code)" size="small">
                {{ row.status_code ?? '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="duration_ms" label="耗时" width="90">
            <template #default="{ row }">
              <span class="duration">{{ row.duration_ms != null ? row.duration_ms + ' ms' : '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="详情" width="80" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                text
                type="primary"
                @click="toggleExpand(row.id)"
              >
                {{ expandedRows.has(row.id) ? '收起' : '展开' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 展开详情面板 -->
        <template v-for="exec in httpExecs" :key="exec.id + '_detail'">
          <transition name="el-zoom-in-top">
            <div v-if="expandedRows.has(exec.id)" class="detail-panel">
              <div class="detail-header">
                <span class="mono">{{ exec.method }} {{ exec.url_redacted }}</span>
                <span class="detail-time">{{ formatTime(exec.created_at) }}</span>
              </div>
              <el-row :gutter="16">
                <el-col :span="24" :md="12">
                  <div class="detail-section">
                    <div class="detail-label">请求 Headers</div>
                    <pre class="json-block">{{ formatJson(exec.headers_redacted) }}</pre>
                  </div>
                  <div class="detail-section">
                    <div class="detail-label">请求 Body</div>
                    <pre class="json-block">{{ formatJson(exec.request_body_redacted) }}</pre>
                  </div>
                </el-col>
                <el-col :span="24" :md="12">
                  <div class="detail-section">
                    <div class="detail-label">
                      响应内容
                      <el-tag :type="getHttpStatusType(exec.status_code)" size="small" style="margin-left:8px">
                        {{ exec.status_code ?? '无响应' }}
                      </el-tag>
                    </div>
                    <pre class="json-block">{{ formatJson(exec.response_body_redacted) }}</pre>
                  </div>
                  <div v-if="exec.error" class="detail-section">
                    <div class="detail-label error-label">错误</div>
                    <pre class="json-block error-block">{{ exec.error }}</pre>
                  </div>
                </el-col>
              </el-row>
            </div>
          </transition>
        </template>

        <div v-if="!loading && httpExecs.length === 0" class="empty-hint">
          <el-empty description="暂无 HTTP 执行记录" />
        </div>
      </el-tab-pane>

      <!-- ========== 策略判定（审批日志）========== -->
      <el-tab-pane label="策略判定" name="policy">
        <el-table :data="approvals" style="width: 100%" v-loading="loading" stripe>
          <el-table-column prop="created_at" label="发起时间" width="180">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="title" label="审批标题" min-width="200">
            <template #default="{ row }">
              <el-text truncated>{{ row.title }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="action_summary" label="操作摘要" min-width="200">
            <template #default="{ row }">
              <el-text truncated>{{ row.action_summary }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="risk_level" label="风险等级" width="100">
            <template #default="{ row }">
              <el-tag :type="getRiskTagType(row.risk_level)" size="small">{{ row.risk_level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="审批结果" width="100">
            <template #default="{ row }">
              <el-tag :type="getApprovalStatusType(row.status)" size="small">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="decided_at" label="决策时间" width="180">
            <template #default="{ row }">{{ formatTime(row.decided_at) }}</template>
          </el-table-column>
          <el-table-column prop="decided_by" label="操作人" width="100">
            <template #default="{ row }">{{ row.decided_by || '-' }}</template>
          </el-table-column>
          <el-table-column prop="decision_reason" label="备注" min-width="140">
            <template #default="{ row }">
              <el-text truncated>{{ row.decision_reason || '-' }}</el-text>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!loading && approvals.length === 0" class="empty-hint">
          <el-empty description="暂无审批操作记录" />
        </div>
      </el-tab-pane>

    </el-tabs>
  </div>
</template>

<style scoped>
.audit-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 28px 36px;
  background: var(--el-bg-color-page);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.audit-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
}

.url-text {
  color: var(--el-color-primary);
}

.duration {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.empty-hint {
  padding: 40px 0;
}

/* 展开详情面板 */
.detail-panel {
  margin: 4px 0 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-light);
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--el-fill-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  color: var(--el-text-color-regular);
}

.detail-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-family: inherit;
}

.detail-section {
  padding: 12px 16px;
}

.detail-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
}

.error-label {
  color: var(--el-color-danger);
}

.json-block {
  margin: 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 260px;
  overflow-y: auto;
}

.error-block {
  background: #2d1414;
  color: #f97171;
}
</style>
