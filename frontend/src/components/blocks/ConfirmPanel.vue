<script setup lang="ts">
import { ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Check, Close, Warning } from '@element-plus/icons-vue'

const props = defineProps<{
  block: {
    block_type: 'confirm_panel'
    approval_id: string
    title: string
    description: string
    risk_level: string
    timeout_seconds: number
  }
}>()

const sessionStore = useSessionStore()
const loading = ref(false)
const resolved = ref(false)
const actionResult = ref<'approved' | 'rejected' | null>(null)

async function handleAction(action: 'approve' | 'reject') {
  if (loading.value || resolved.value) return
  
  loading.value = true
  try {
    const sessionId = sessionStore.currentSession?.id
    if (!sessionId) {
      // 尝试从最近的消息或路由中找？通常 store 里的就是当前的
      throw new Error('当前会话未选中')
    }
    
    console.log(`[ConfirmPanel] Sending ${action} for ${props.block.approval_id} in session ${sessionId}`)
    
    await axios.post(`/api/sessions/${sessionId}/approvals/${props.block.approval_id}`, {
      action
    })
    
    resolved.value = true
    actionResult.value = action === 'approve' ? 'approved' : 'rejected'
    ElMessage.success(action === 'approve' ? '已批准操作' : '已拒绝操作')
    
  } catch (e: any) {
    console.error('[ConfirmPanel] Error:', e)
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card shadow="always" class="confirm-panel-card" :class="{ 'is-resolved': resolved, [block.risk_level]: true }">
    <template #header>
      <div class="panel-header">
        <el-icon class="header-icon"><Warning /></el-icon>
        <span class="header-title">{{ block.title }}</span>
        <el-tag :type="block.risk_level === 'critical' ? 'danger' : 'warning'" size="small" effect="dark">
          {{ block.risk_level }} 风险
        </el-tag>
      </div>
    </template>
    
    <div class="panel-content">
      <p class="description">{{ block.description }}</p>
      
      <div v-if="!resolved" class="actions">
        <el-button
          type="danger"
          plain
          :icon="Close"
          @click="handleAction('reject')"
          :loading="loading && actionResult === 'rejected'"
        >
          取消执行
        </el-button>
        <el-button
          type="primary"
          :icon="Check"
          @click="handleAction('approve')"
          :loading="loading && actionResult === 'approved'"
        >
          确认执行
        </el-button>
      </div>
      
      <div v-else class="result">
        <el-result
          :icon="actionResult === 'approved' ? 'success' : 'error'"
          :title="actionResult === 'approved' ? '已批准' : '已取消'"
          sub-title="请等待后续处理结果..."
        >
        </el-result>
      </div>
    </div>
    
    <div v-if="!resolved" class="panel-footer">
      <span class="timeout-text">此操作将在 {{ block.timeout_seconds }} 秒后自动过期</span>
    </div>
  </el-card>
</template>

<style scoped>
.confirm-panel-card {
  margin: 12px 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #fee2e2;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.1);
}

.is-resolved {
  opacity: 0.8;
  box-shadow: none;
  border-color: #e5e7eb;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  color: #ef4444;
  font-size: 18px;
}

.header-title {
  font-weight: 700;
  flex: 1;
}

.panel-content {
  padding: 10px 0;
}

.description {
  color: #374151;
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 20px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.panel-footer {
  margin-top: 15px;
  padding-top: 10px;
  border-top: 1px solid #f3f4f6;
  text-align: right;
}

.timeout-text {
  font-size: 12px;
  color: #94a3b8;
}

:deep(.el-result) {
  padding: 10px 0;
}
:deep(.el-result__title) {
  font-size: 16px;
  margin-top: 8px;
}
</style>
