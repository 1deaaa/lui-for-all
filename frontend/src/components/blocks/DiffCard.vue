<script setup lang="ts">
defineProps<{
  block: {
    block_type: 'diff_card'
    title?: string
    description?: string
    items: Array<{
      key: string
      old_value: any
      new_value: any
      change_type: 'added' | 'removed' | 'modified'
    }>
  }
}>()

// 获取变更类型颜色
function getChangeColor(type: string): string {
  switch (type) {
    case 'added':
      return '#67c23a'
    case 'removed':
      return '#f56c6c'
    case 'modified':
      return '#e6a23c'
    default:
      return '#909399'
  }
}

// 获取变更类型文本
function getChangeText(type: string): string {
  switch (type) {
    case 'added':
      return '新增'
    case 'removed':
      return '删除'
    case 'modified':
      return '修改'
    default:
      return type
  }
}
</script>

<template>
  <el-card shadow="hover" class="diff-card">
    <template #header v-if="block.title">
      <span>{{ block.title }}</span>
    </template>
    
    <p class="description" v-if="block.description">{{ block.description }}</p>
    
    <div class="diff-list">
      <div
        v-for="(item, index) in block.items"
        :key="index"
        class="diff-item"
        :class="item.change_type"
      >
        <div class="diff-header">
          <span class="diff-key">{{ item.key }}</span>
          <el-tag
            :color="getChangeColor(item.change_type)"
            effect="dark"
            size="small"
          >
            {{ getChangeText(item.change_type) }}
          </el-tag>
        </div>
        
        <div class="diff-values">
          <div class="old-value" v-if="item.change_type !== 'added'">
            <span class="label">旧值:</span>
            <span class="value">{{ item.old_value }}</span>
          </div>
          <div class="new-value" v-if="item.change_type !== 'removed'">
            <span class="label">新值:</span>
            <span class="value">{{ item.new_value }}</span>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.diff-card {
  max-width: 100%;
}

.description {
  color: #909399;
  margin-bottom: 16px;
}

.diff-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.diff-item {
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  border-left: 3px solid;
}

.diff-item.added {
  border-color: #67c23a;
}

.diff-item.removed {
  border-color: #f56c6c;
}

.diff-item.modified {
  border-color: #e6a23c;
}

.diff-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.diff-key {
  font-weight: bold;
  color: #303133;
}

.diff-values {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.old-value, .new-value {
  display: flex;
  gap: 8px;
  font-size: 14px;
}

.label {
  color: #909399;
}

.value {
  color: #303133;
}

.old-value .value {
  text-decoration: line-through;
  color: #f56c6c;
}

.new-value .value {
  color: #67c23a;
}
</style>
