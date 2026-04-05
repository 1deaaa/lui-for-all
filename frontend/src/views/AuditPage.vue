<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'

// ==================== 状态 ====================
const activeTab = ref('tasks')
const loading = ref(false)

// 任务运行
const taskRuns = ref<any[]>([])

// HTTP 执行
const httpExecs = ref<any[]>([])
const expandedRowKeys = ref<string[]>([])
const httpFilter = ref({ keyword: '', method: '' })
const httpPage = ref(1)
const httpPageSize = ref(20)

// 审批日志
const approvals = ref<any[]>([])
const policyFilter = ref({ keyword: '', status: '' })
const policyPage = ref(1)
const policyPageSize = ref(20)

const httpTotal = ref(0)
const policyTotal = ref(0)

// ==================== 数据获取 ====================
async function fetchTaskRuns() {
  loading.value = true
  try {
    const res = await axios.get('/api/audit/task-runs?limit=100')
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
    const offset = (httpPage.value - 1) * httpPageSize.value
    let url = `/api/audit/http-executions?limit=${httpPageSize.value}&offset=${offset}`
    if (httpFilter.value.keyword) url += `&keyword=${encodeURIComponent(httpFilter.value.keyword)}`
    
    // Note: If you want to support method filtering in the backend as well later, you can add it here.
    // For now we just filter keyword since we added it to backend.

    const res = await axios.get(url)
    // 如果想要本地支持 method 过滤，可以叠加，或者后端加上 method
    let data = res.data.executions || []
    if (httpFilter.value.method) {
      data = data.filter((e: any) => e.method === httpFilter.value.method)
    }
    httpExecs.value = data
    httpTotal.value = res.data.total || 0
    expandedRowKeys.value = []
  } catch (e) {
    console.error('获取 HTTP 执行记录失败:', e)
  } finally {
    loading.value = false
  }
}

async function fetchApprovals() {
  loading.value = true
  try {
    const offset = (policyPage.value - 1) * policyPageSize.value
    let url = `/api/audit/approvals?limit=${policyPageSize.value}&offset=${offset}`
    if (policyFilter.value.status) url += `&status=${encodeURIComponent(policyFilter.value.status)}`
    if (policyFilter.value.keyword) url += `&keyword=${encodeURIComponent(policyFilter.value.keyword)}`

    const res = await axios.get(url)
    approvals.value = res.data.approvals || []
    policyTotal.value = res.data.total || 0
  } catch (e) {
    console.error('获取审批日志失败:', e)
  } finally {
    loading.value = false
  }
}



watch([httpPage, httpPageSize], fetchHttpExecs)
watch([policyPage, policyPageSize], fetchApprovals)

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
  if (risk === 'critical' || risk === 'hard_write') return 'danger'
  if (risk === 'soft_write' || risk === 'medium') return 'warning'
  return 'success'
}

function riskLabel(risk: string): string {
  const map: Record<string, string> = {
    critical: '极高风险',
    hard_write: '高风险',
    soft_write: '中风险',
    readonly_sensitive: '敏感只读',
    readonly_safe: '安全只读',
  }
  return map[risk] || risk
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

function safeParse(val: any): Record<string, any> | null {
  if (!val) return null
  if (typeof val === 'object') return val
  try {
    const p = typeof val === 'string' ? JSON.parse(val) : val
    if (typeof p === 'object' && !Array.isArray(p) && p !== null) return p
    return null
  } catch {
    return null
  }
}

function highlightJson(val: any): string {
  if (!val) return '<span style="color:#999;font-size:13px">(空)</span>'
  let parsed = val
  if (typeof val === 'string') {
    try { parsed = JSON.parse(val) } catch {}
  }
  const str = typeof parsed === 'string' ? parsed : JSON.stringify(parsed, null, 2)
  // @ts-ignore
  if (window.hljs) {
    // @ts-ignore
    return window.hljs.highlight(str, { language: 'json' }).value
  }
  return str
}

function handleExpandChange(_row: any, expandedRows: any[]) {
  expandedRowKeys.value = expandedRows.map((r: any) => r.id)
}

function onHttpFilterChange() {
  httpPage.value = 1
  fetchHttpExecs()
}

function onPolicyFilterChange() {
  policyPage.value = 1
  fetchApprovals()
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
        <!-- 筛选栏 -->
        <div class="filter-bar">
          <el-input
            v-model="httpFilter.keyword"
            placeholder="搜索请求 URL..."
            clearable
            @input="onHttpFilterChange"
            class="filter-input"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select
            v-model="httpFilter.method"
            placeholder="请求方法"
            clearable
            @change="onHttpFilterChange"
            class="filter-select"
          >
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="PATCH" value="PATCH" />
            <el-option label="DELETE" value="DELETE" />
          </el-select>
          <span class="filter-count">共 {{ httpTotal }} 条</span>
        </div>

        <!-- 内联展开表格 -->
        <el-table
          :data="httpExecs"
          row-key="id"
          :expand-row-keys="expandedRowKeys"
          @expand-change="handleExpandChange"
          v-loading="loading"
          stripe
          style="width: 100%"
        >
          <!-- 展开列：详情面板 -->
          <el-table-column type="expand" width="40">
            <template #default="{ row }">
              <div class="expand-detail">
                <!-- 顶部信息条 -->
                <div class="detail-header">
                  <div class="detail-header-left">
                    <el-tag :type="methodTagType(row.method)" size="small" effect="dark" style="margin-right:10px">{{ row.method }}</el-tag>
                    <code class="mono url-full">{{ row.url_redacted }}</code>
                  </div>
                  <div class="detail-header-right">
                    <el-tag :type="getHttpStatusType(row.status_code)" size="small">HTTP {{ row.status_code ?? '无状态码' }}</el-tag>
                    <span class="detail-time" style="margin-left:12px">{{ formatTime(row.created_at) }}</span>
                    <span v-if="row.duration_ms != null" class="detail-time" style="margin-left:12px">⏱ {{ row.duration_ms }} ms</span>
                  </div>
                </div>

                <el-row :gutter="16">
                  <!-- 左列：请求 -->
                  <el-col :span="24" :md="12">
                    <!-- Headers 友好表格 -->
                    <div class="detail-section">
                      <div class="detail-label">
                        <Icon icon="lucide:list" style="margin-right:4px"/> 请求 Headers
                      </div>
                      <template v-if="safeParse(row.headers_redacted) && Object.keys(safeParse(row.headers_redacted)!).length">
                        <el-descriptions border size="small" :column="1" class="compact-desc">
                          <el-descriptions-item v-for="(v, k) in safeParse(row.headers_redacted)" :key="k" :label="String(k)">
                            <span class="mono" style="word-break:break-all;font-size:12px">{{ v }}</span>
                          </el-descriptions-item>
                        </el-descriptions>
                      </template>
                      <div v-else-if="row.headers_redacted" class="code-block" v-html="highlightJson(row.headers_redacted)"></div>
                      <div v-else class="empty-tip">（无 Headers）</div>
                    </div>

                    <!-- 请求 Body -->
                    <div class="detail-section" v-if="row.request_body_redacted != null">
                      <div class="detail-label">
                        <Icon icon="lucide:file-json" style="margin-right:4px"/> 请求 Body
                      </div>
                      <div class="code-block" v-html="highlightJson(row.request_body_redacted)"></div>
                    </div>
                  </el-col>

                  <!-- 右列：响应 -->
                  <el-col :span="24" :md="12">
                    <div class="detail-section">
                      <div class="detail-label">
                        <Icon icon="lucide:download-cloud" style="margin-right:4px"/> 响应内容
                      </div>
                      <!-- 浅层对象用键值表格 + 嵌套部分仍然用高亮代码块 -->
                      <template v-if="safeParse(row.response_body_redacted)">
                        <el-descriptions border size="small" :column="1" class="compact-desc">
                          <el-descriptions-item v-for="(v, k) in safeParse(row.response_body_redacted)" :key="k" :label="String(k)">
                            <template v-if="typeof v === 'object' && v !== null">
                              <div class="code-block nested-code" v-html="highlightJson(v)"></div>
                            </template>
                            <template v-else-if="String(v).length > 100">
                              <div class="long-val">{{ String(v) }}</div>
                            </template>
                            <span v-else class="mono" style="font-size:12px">{{ String(v) }}</span>
                          </el-descriptions-item>
                        </el-descriptions>
                      </template>
                      <template v-else>
                        <div class="code-block" v-html="highlightJson(row.response_body_redacted)"></div>
                      </template>
                    </div>

                    <div v-if="row.error" class="detail-section">
                      <div class="detail-label error-label">
                        <Icon icon="lucide:alert-circle" style="margin-right:4px"/> 错误信息
                      </div>
                      <div class="error-block">{{ row.error }}</div>
                    </div>
                  </el-col>
                </el-row>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="created_at" label="时间" width="165">
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
        </el-table>

        <!-- 分页 -->
        <div class="pagination-bar">
          <el-pagination
            v-model:current-page="httpPage"
            v-model:page-size="httpPageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="httpTotal"
            layout="total, sizes, prev, pager, next"
            background
            small
          />
        </div>

        <div v-if="!loading && httpExecs.length === 0" class="empty-hint">
          <el-empty description="暂无 HTTP 执行记录" />
        </div>
      </el-tab-pane>

      <!-- ========== 策略判定（人类批准日志）========== -->
      <el-tab-pane label="策略判定" name="policy">
        <!-- 筛选栏 -->
        <div class="filter-bar">
          <el-input
            v-model="policyFilter.keyword"
            placeholder="搜索标题或操作摘要..."
            clearable
            @input="onPolicyFilterChange"
            class="filter-input"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select
            v-model="policyFilter.status"
            placeholder="审批状态"
            clearable
            @change="onPolicyFilterChange"
            class="filter-select"
          >
            <el-option label="待审批" value="pending" />
            <el-option label="已批准" value="approved" />
            <el-option label="已拒绝" value="rejected" />
            <el-option label="已超时" value="timeout" />
          </el-select>
          <span class="filter-count">共 {{ policyTotal }} 条</span>
        </div>

        <el-table :data="approvals" style="width: 100%" v-loading="loading" stripe>
          <el-table-column prop="created_at" label="发起时间" width="165">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="title" label="审批标题" min-width="180">
            <template #default="{ row }">
              <el-text truncated class="mono">{{ row.title || '-' }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="action_summary" label="操作摘要" min-width="200">
            <template #default="{ row }">
              <el-text truncated>{{ row.action_summary || '-' }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="risk_level" label="风险等级" width="110">
            <template #default="{ row }">
              <el-tag :type="getRiskTagType(row.risk_level)" size="small">{{ riskLabel(row.risk_level) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="审批结果" width="100">
            <template #default="{ row }">
              <el-tag :type="getApprovalStatusType(row.status)" size="small">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="decided_at" label="决策时间" width="165">
            <template #default="{ row }">{{ formatTime(row.decided_at) }}</template>
          </el-table-column>
          <el-table-column prop="decided_by" label="操作人" width="90">
            <template #default="{ row }">{{ row.decided_by || '-' }}</template>
          </el-table-column>
          <el-table-column prop="decision_reason" label="备注" min-width="130">
            <template #default="{ row }">
              <el-text truncated>{{ row.decision_reason || '-' }}</el-text>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-bar">
          <el-pagination
            v-model:current-page="policyPage"
            v-model:page-size="policyPageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="policyTotal"
            layout="total, sizes, prev, pager, next"
            background
            small
          />
        </div>

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
  min-height: 0;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0 14px;
}

.filter-input {
  width: 280px;
}

.filter-select {
  width: 140px;
}

.filter-count {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  margin-left: 4px;
}

/* 分页栏 */
.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding: 14px 0 4px;
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

/* ===== 展开详情面板（行内联） ===== */
.expand-detail {
  margin: 0;
  background: var(--el-fill-color-light);
  border-top: 1px solid var(--el-border-color-lighter);
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
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
  padding: 12px 20px;
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

/* ===== 亮色代码高亮块 ===== */
.code-block {
  margin: 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: #f6f8fb;
  border: 1px solid #e2e8f0;
  font-family: ui-monospace, SFMono-Regular, Consolas, "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  color: #24292e;
}

/* highlight.js 亮色主题的padding修正 */
.code-block .hljs {
  background: transparent;
  padding: 0;
}

.nested-code {
  max-height: 160px;
  font-size: 11px;
  padding: 6px 10px;
  margin-top: 4px;
}

.error-block {
  background: #fff1f0;
  border: 1px solid #ffa39e;
  border-radius: 6px;
  padding: 10px 12px;
  color: #cf1322;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
}

.detail-header-left {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.detail-header-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.url-full {
  color: var(--el-color-primary);
  word-break: break-all;
  font-size: 12px;
}

.empty-tip {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  padding: 6px 0;
}

.long-val {
  font-size: 12px;
  color: var(--el-text-color-regular);
  word-break: break-all;
  line-height: 1.5;
  max-height: 80px;
  overflow-y: auto;
}

/* el-descriptions 紧凑样式 */
.compact-desc {
  width: 100%;
}

:deep(.compact-desc .el-descriptions__label) {
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  white-space: nowrap;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light) !important;
  min-width: 120px;
}

:deep(.compact-desc .el-descriptions__content) {
  font-size: 12px;
}
</style>
