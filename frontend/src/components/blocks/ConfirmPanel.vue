<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const props = defineProps<{
  block: {
    block_type: 'confirm_panel'
    approval_id: string
    title: string
    description: string
    action_summary: string
    risk_level: string
    details: Array<Record<string, any>>
    timeout_seconds: number
  }
}>()

const loading = ref(false)
const status = ref<'pending' | 'approved' | 'rejected'>('pending')

// 获取风险等级颜色
function getRiskColor(level: string): string {
  switch (level) {
    case 'low':
      return '#67c23a'
    case 'medium':
      return '#e6a23c'
    case 'high':
      return '#f56c6c'
    default:
      return '#909399'
  }
}

// 批准
async function handleApprove() {
  loading.value = true
  try {
    await axios.post(`/api/approvals/${props.block.approval_id}/approve`, {
      reason: '用户确认批准',
    })
    status.value = 'approved'
  } catch (error) {
    console.error('批准失败:', error)
  } finally {
    loading.value = false
  }
}

// 拒绝
async function handleReject() {
  loading.value = true
  try {
    await axios.post(`/api/approvals/${props.block.approval_id}/reject`, {
      reason: '用户拒绝',
    })
    status.value = 'rejected'
  } catch (error) {
    console.error('拒绝失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card shadow="hover" class="confirm-panel">
    <template #header>
      <div class="panel-header">
        <span>{{ block.title }}</span>
        <el-tag :color="getRiskColor(block.risk_level)" effect="dark">
          {{ block.risk_level }} 风险
        </el-tag>
      </div>
    </template>
    
    <div class="panel-content">
      <p class="description">{{ block.description }}</p>
      
      <el-alert
        :title="block.action_summary"
        type="warning"
        :closable="false"
        show-icon
        class="action-alert"
      />
      
      <div class="details" v-if="block.details.length > 0">
        <div v-for="(detail, index) in block.details" :key="index" class="detail-item">
          <span class="detail-key">{{ detail.key }}:</span>
          <span class="detail-value">{{ detail.value }}</span>
        </div>
      </div>
      
      <div class="actions" v-if="status === 'pending'">
        <el-button
          type="danger"
          @click="handleReject"
          :loading="loading"
        >
          拒绝
        </el-button>
        <el-button
          type="success"
          @click="handleApprove"
          :loading="loading"
        >
          批准
        </el-button>
      </div>
      
      <div class="result" v-else>
        <el-tag :type="status === 'approved' ? 'success' : 'danger'" size="large">
          {{ status === 'approved' ? '已批准' : '已拒绝' }}
        </el-tag>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.confirm-panel {
  max-width: 100%;
  border: 2px solid #e6a23c;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-content {
  padding: 10px 0;
}

.description {
  color: #606266;
  margin-bottom: 16px;
}

.action-alert {
  margin-bottom: 16px;
}

.details {
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 16px;
}

.detail-item {
  display: flex;
  gap: 8px;
  margin: 8px 0;
}

.detail-key {
  color: #909399;
  font-weight: bold;
}

.detail-value {
  color: #303133;
}

.actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.result {
  text-align: center;
  padding: 20px;
}
</style>
