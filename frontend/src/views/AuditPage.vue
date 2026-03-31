<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

// 任务运行列表
const taskRuns = ref<any[]>([])
const loading = ref(true)
const activeTab = ref('tasks')

// 获取任务运行列表
async function fetchTaskRuns() {
  loading.value = true
  try {
    const res = await axios.get('/api/audit/task-runs?limit=50')
    taskRuns.value = res.data.task_runs || []
  } catch (error) {
    console.error('获取任务运行列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取状态类型
function getStatusType(status: string): string {
  switch (status) {
    case 'completed':
      return 'success'
    case 'running':
    case 'waiting_approval':
    case 'waiting_params':
      return 'warning'
    case 'failed':
    case 'cancelled':
      return 'danger'
    default:
      return 'info'
  }
}

// 格式化时间
function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}

onMounted(() => {
  fetchTaskRuns()
})
</script>

<template>
  <div class="audit-page">
    <div class="page-header">
      <h2>审计日志</h2>
      <el-button @click="fetchTaskRuns" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="任务运行" name="tasks">
        <el-table :data="taskRuns" style="width: 100%" v-loading="loading">
          <el-table-column prop="id" label="任务ID" width="280">
            <template #default="{ row }">
              <el-text truncated>{{ row.id }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="user_message" label="用户消息" min-width="200">
            <template #default="{ row }">
              <el-text truncated>{{ row.user_message }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="trace_id" label="追踪ID" width="280">
            <template #default="{ row }">
              <el-text truncated>{{ row.trace_id }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default>
              <el-button size="small" text type="primary">
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="HTTP 执行" name="http">
        <el-empty description="暂无 HTTP 执行记录" />
      </el-tab-pane>

      <el-tab-pane label="策略判定" name="policy">
        <el-empty description="暂无策略判定记录" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.audit-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 32px 40px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}
</style>
