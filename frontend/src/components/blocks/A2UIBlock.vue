<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { A2UIAction, A2UIBlock, A2UIComponent } from '@/vite-env.d'

const props = defineProps<{ block: A2UIBlock }>()

const emit = defineEmits<{
  action: [payload: { componentId: string; action: A2UIAction }]
}>()

const components = computed(() => props.block.components || [])

function propString(component: A2UIComponent, key: string, fallback = ''): string {
  const value = component.props?.[key]
  return value === undefined || value === null ? fallback : String(value)
}

function headingTag(component: A2UIComponent): string {
  const level = Number(component.props?.level)
  return level === 1 || level === 3 ? `h${level}` : 'h2'
}

function rows(component: A2UIComponent): Array<Record<string, unknown>> {
  return Array.isArray(component.props?.rows) ? component.props.rows : []
}

function columns(component: A2UIComponent): Array<{ key: string; label: string }> {
  if (!Array.isArray(component.props?.columns)) return []
  return component.props.columns.filter(
    (column: unknown): column is { key: string; label: string } =>
      Boolean(column) && typeof column === 'object' &&
      typeof (column as { key?: unknown }).key === 'string' &&
      typeof (column as { label?: unknown }).label === 'string',
  )
}

function actions(component: A2UIComponent): A2UIAction[] {
  return Array.isArray(component.actions) ? component.actions : []
}

async function handleAction(component: A2UIComponent, action: A2UIAction) {
  if (action.action_type === 'copy') {
    const text = typeof action.payload?.text === 'string' ? action.payload.text : ''
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      ElMessage.success('已复制')
    } catch {
      ElMessage.error('复制失败')
    }
    return
  }

  emit('action', { componentId: component.component_id, action })
  window.dispatchEvent(new CustomEvent('lui-a2ui-action', {
    detail: { surfaceId: props.block.surface_id, componentId: component.component_id, action },
  }))
}
</script>

<template>
  <el-card shadow="hover" class="a2ui-block">
    <div
      v-for="component in components"
      :key="component.component_id"
      class="a2ui-component"
    >
      <component
        :is="headingTag(component)"
        v-if="component.component_type === 'heading'"
        class="a2ui-heading"
      >
        {{ propString(component, 'text') }}
      </component>

      <p v-else-if="component.component_type === 'text'" class="a2ui-text" :data-tone="propString(component, 'tone', 'default')">
        {{ propString(component, 'text') }}
      </p>

      <div v-else-if="component.component_type === 'metric'" class="a2ui-metric">
        <span class="a2ui-label">{{ propString(component, 'label') }}</span>
        <strong>{{ propString(component, 'value') }}</strong>
        <span v-if="propString(component, 'unit')" class="a2ui-unit">{{ propString(component, 'unit') }}</span>
        <span v-if="propString(component, 'trend')" class="a2ui-trend">{{ propString(component, 'trend') }}</span>
      </div>

      <div v-else-if="component.component_type === 'status'" class="a2ui-status" :data-tone="propString(component, 'tone', 'default')">
        <span>{{ propString(component, 'label') }}</span>
        <strong>{{ propString(component, 'value') }}</strong>
      </div>

      <el-table v-else-if="component.component_type === 'table'" :data="rows(component)" size="small" class="a2ui-table">
        <el-table-column
          v-for="column in columns(component)"
          :key="column.key"
          :prop="column.key"
          :label="column.label"
        />
      </el-table>

      <div v-else-if="component.component_type === 'button'" class="a2ui-actions">
        <el-button
          v-for="(action, actionIndex) in actions(component)"
          :key="`${component.component_id}-${actionIndex}`"
          :type="propString(component, 'variant', 'primary') === 'plain' ? 'default' : 'primary'"
          :plain="propString(component, 'variant') === 'plain'"
          :disabled="Boolean(component.props?.disabled)"
          @click="handleAction(component, action)"
        >
          {{ action.label || propString(component, 'label', '执行') }}
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.a2ui-block {
  max-width: 100%;
}

.a2ui-component + .a2ui-component {
  margin-top: 14px;
}

.a2ui-heading {
  margin: 0;
  color: #1f2937;
}

.a2ui-text {
  margin: 0;
  color: #374151;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.a2ui-text[data-tone='muted'] {
  color: #6b7280;
}

.a2ui-metric,
.a2ui-status {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.a2ui-label {
  color: #6b7280;
}

.a2ui-metric strong,
.a2ui-status strong {
  color: #111827;
  font-size: 20px;
}

.a2ui-unit,
.a2ui-trend {
  color: #6b7280;
  font-size: 12px;
}

.a2ui-status[data-tone='success'] {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.a2ui-status[data-tone='warning'] {
  border-color: #fde68a;
  background: #fffbeb;
}

.a2ui-status[data-tone='error'] {
  border-color: #fecaca;
  background: #fef2f2;
}

.a2ui-table {
  width: 100%;
}

.a2ui-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
