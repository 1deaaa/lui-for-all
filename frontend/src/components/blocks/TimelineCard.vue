<script setup lang="ts">
defineProps<{
  block: {
    block_type: 'timeline_card'
    title?: string
    events: Array<{
      timestamp: string
      title: string
      description?: string
      status: 'pending' | 'in_progress' | 'completed' | 'failed'
      icon?: string
    }>
  }
}>()

// 获取状态颜色
function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return '#67c23a'
    case 'in_progress':
      return '#409eff'
    case 'failed':
      return '#f56c6c'
    default:
      return '#909399'
  }
}

// 获取状态图标
function getStatusIcon(status: string): string {
  switch (status) {
    case 'completed':
      return 'CircleCheck'
    case 'in_progress':
      return 'Loading'
    case 'failed':
      return 'CircleClose'
    default:
      return 'Clock'
  }
}

// 格式化时间
function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleString()
}
</script>

<template>
  <el-card shadow="hover" class="timeline-card">
    <template #header v-if="block.title">
      <span>{{ block.title }}</span>
    </template>
    
    <div class="timeline">
      <div
        v-for="(event, index) in block.events"
        :key="index"
        class="timeline-item"
        :class="event.status"
      >
        <div class="timeline-icon">
          <el-icon :style="{ color: getStatusColor(event.status) }">
            <component :is="getStatusIcon(event.status)" />
          </el-icon>
        </div>
        <div class="timeline-content">
          <div class="event-header">
            <span class="event-title">{{ event.title }}</span>
            <span class="event-time">{{ formatTime(event.timestamp) }}</span>
          </div>
          <p v-if="event.description" class="event-description">
            {{ event.description }}
          </p>
        </div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.timeline-card {
  max-width: 100%;
}

.timeline {
  position: relative;
  padding-left: 30px;
}

.timeline-item {
  position: relative;
  padding-bottom: 20px;
}

.timeline-item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: -23px;
  top: 24px;
  width: 2px;
  height: calc(100% - 24px);
  background-color: #e4e7ed;
}

.timeline-icon {
  position: absolute;
  left: -30px;
  top: 4px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: white;
  border-radius: 50%;
}

.timeline-content {
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
}

.event-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.event-title {
  font-weight: bold;
  color: #303133;
}

.event-time {
  font-size: 12px;
  color: #909399;
}

.event-description {
  color: #606266;
  margin: 0;
  font-size: 14px;
}
</style>
