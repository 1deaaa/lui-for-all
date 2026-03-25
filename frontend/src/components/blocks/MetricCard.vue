<script setup lang="ts">
defineProps<{
  block: {
    block_type: 'metric_card'
    title?: string
    metrics: Array<{
      label: string
      value: string | number
      unit?: string
      trend?: 'up' | 'down' | 'stable'
      trend_value?: string
    }>
  }
}>()

// 获取趋势图标
function getTrendIcon(trend?: string): string {
  switch (trend) {
    case 'up':
      return 'CaretTop'
    case 'down':
      return 'CaretBottom'
    default:
      return 'Minus'
  }
}

// 获取趋势颜色
function getTrendColor(trend?: string): string {
  switch (trend) {
    case 'up':
      return '#67c23a'
    case 'down':
      return '#f56c6c'
    default:
      return '#909399'
  }
}
</script>

<template>
  <el-card shadow="hover" class="metric-card">
    <template #header v-if="block.title">
      <span>{{ block.title }}</span>
    </template>
    
    <div class="metrics-grid">
      <div v-for="(metric, index) in block.metrics" :key="index" class="metric-item">
        <div class="metric-label">{{ metric.label }}</div>
        <div class="metric-value">
          <span class="value">{{ metric.value }}</span>
          <span v-if="metric.unit" class="unit">{{ metric.unit }}</span>
          <el-icon
            v-if="metric.trend"
            :style="{ color: getTrendColor(metric.trend) }"
            class="trend-icon"
          >
            <component :is="getTrendIcon(metric.trend)" />
          </el-icon>
        </div>
        <div v-if="metric.trend_value" class="trend-value">
          {{ metric.trend_value }}
        </div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.metric-card {
  max-width: 100%;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 20px;
}

.metric-item {
  text-align: center;
}

.metric-label {
  color: #909399;
  font-size: 14px;
  margin-bottom: 8px;
}

.metric-value {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
}

.value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.unit {
  font-size: 14px;
  color: #909399;
}

.trend-icon {
  margin-left: 4px;
}

.trend-value {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
