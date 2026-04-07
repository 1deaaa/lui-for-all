<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import { ElMessage } from 'element-plus'
import { Check, Close, Warning, List } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import type { ApprovalBlock } from '@/vite-env.d'

const props = defineProps<{
  block: ApprovalBlock
}>()

const sessionStore = useSessionStore()
const { t } = useI18n()
const loading = ref(false)

// 统一处理 items 逻辑
const items = computed(() => {
  if (props.block.items && props.block.items.length > 0) {
    return props.block.items
  }
  // 兼容旧的单条模式
  return [{
    write_id: props.block.approval_id || '',
    route_id: (props.block as any).route_id || '',
    method: (props.block as any).method || '',
    path: (props.block as any).path || '',
    parameters: (props.block as any).parameters || {},
    reasoning: props.block.description || '',
    safety_level: props.block.risk_level || 'soft_write'
  }]
})

const isBatch = computed(() => items.value.length > 1)
const riskLevel = computed(() => {
  if (props.block.risk_level) return props.block.risk_level
  return items.value.some(i => i.safety_level === 'critical') ? 'critical' : 'warning'
})

// 已决策状态直接来自 block（由 store 控制）
const resolved = computed(() => !!props.block.resolved_action)
const actionResult = computed(() => props.block.resolved_action ?? null)

async function handleAction(action: 'approve' | 'reject') {
  if (loading.value || resolved.value) return
  loading.value = true
  try {
    const taskRunId = sessionStore.currentTaskRun?.id
    if (!taskRunId) throw new Error(t('confirmPanel.messages.taskNotSelected'))

    const approvedIds = action === 'approve' ? items.value.map(i => i.write_id) : []

    // 先在 store 中标记为已决策（保证 UI 即时反映，位置固定）
    sessionStore.markApprovalResolved(props.block.batch_id, props.block.approval_id, action === 'approve' ? 'approved' : 'rejected')

    // 恢复图执行（开启新的事件流）
    sessionStore.startEventStream(taskRunId, {
      resumeBatchId: props.block.batch_id,
      resumeWriteId: props.block.approval_id,
      resumeAction: action,
      approvedIds,
    })

    ElMessage.success(action === 'approve' ? t('confirmPanel.messages.approved') : t('confirmPanel.messages.rejected'))
  } catch (e: any) {
    ElMessage.error(t('confirmPanel.messages.failed', { reason: e.message || t('common.unknown') }))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="confirm-panel" :class="[riskLevel, { 'is-resolved': resolved }]">
    <div class="panel-header">
      <el-icon class="panel-icon"><Warning v-if="!isBatch" /><List v-else /></el-icon>
      <span class="panel-title">
        {{ isBatch ? t('confirmPanel.batchTitle', { count: items.length }) : (block.title || t('confirmPanel.singleTitle')) }}
      </span>
      <el-tag :type="riskLevel === 'critical' ? 'danger' : 'warning'" size="small" effect="plain">
        {{ riskLevel === 'critical' ? t('confirmPanel.riskCritical') : t('confirmPanel.riskWarning') }}
      </el-tag>
    </div>

    <div class="panel-content">
      <div v-if="!isBatch" class="single-item">
        <div class="item-route" v-if="items[0].method">
          <el-tag size="small" :type="items[0].method === 'GET' ? '' : 'warning'" effect="dark" class="method-tag">{{ items[0].method }}</el-tag>
          <code class="path-text">{{ items[0].path }}</code>
        </div>
        <p class="reasoning">{{ items[0].reasoning }}</p>
      </div>

      <div v-else class="batch-list">
        <div v-for="item in items" :key="item.write_id" class="batch-item">
          <div class="item-main">
            <el-tag size="small" class="method-tag">{{ item.method }}</el-tag>
            <code class="path-text">{{ item.path }}</code>
          </div>
          <div class="item-reason">{{ item.reasoning }}</div>
        </div>
      </div>
    </div>

    <div class="panel-actions">
      <template v-if="!resolved">
        <el-button size="small" plain :icon="Close" :loading="loading" @click="handleAction('reject')">{{ t('confirmPanel.reject') }}</el-button>
        <el-button size="small" type="primary" :icon="Check" :loading="loading" @click="handleAction('approve')">
          {{ isBatch ? t('confirmPanel.approveAll') : t('confirmPanel.approve') }}
        </el-button>
      </template>
      <template v-else>
        <span class="status-text" :class="actionResult!">
          {{ actionResult === 'approved' ? t('confirmPanel.approved') : t('confirmPanel.rejected') }}
        </span>
      </template>
    </div>
  </div>
</template>

<style scoped>
.confirm-panel {
  display: flex;
  flex-direction: column;
  padding: 8px 12px;
  margin: 6px 0;
  border-radius: 6px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-left: 3px solid #f59e0b;
  transition: all 0.2s ease;
}

.confirm-panel.critical {
  background: #fff5f5;
  border-color: #fecaca;
  border-left-color: #ef4444;
}

.confirm-panel.is-resolved {
  opacity: 0.7;
  background: #f9fafb;
  border-color: #e5e7eb;
  border-left-color: #9ca3af;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.panel-icon {
  font-size: 14px;
  color: #f59e0b;
}
.critical .panel-icon { color: #ef4444; }

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  flex: 1;
}

.panel-content {
  margin-bottom: 8px;
  padding-left: 22px;
}

.item-route {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.method-tag {
  font-weight: bold;
  font-family: var(--font-mono);
  transform: scale(0.85);
  transform-origin: left;
}

.path-text {
  font-family: var(--font-mono);
  font-size: 12px;
  color: #4b5563;
  background: rgba(0,0,0,0.05);
  padding: 1px 4px;
  border-radius: 3px;
}

.reasoning {
  font-size: 12px;
  color: #6b7280;
  margin: 0;
}

.batch-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.batch-item {
  padding: 4px 0;
  border-bottom: 1px dashed rgba(0,0,0,0.05);
}
.batch-item:last-child { border-bottom: none; }

.item-main { display: flex; align-items: center; gap: 4px; }
.item-reason { font-size: 11px; color: #9ca3af; margin-top: 2px; padding-left: 4px; }

.panel-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  border-top: 1px solid rgba(0,0,0,0.05);
  padding-top: 6px;
}

.status-text {
  font-size: 12px;
  font-weight: 600;
}
.status-text.approved { color: #059669; }
.status-text.rejected { color: #dc2626; }
</style>