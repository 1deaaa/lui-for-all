<script setup lang="ts">
import { ref, reactive } from 'vue'
import axios from 'axios'

const props = defineProps<{
  block: {
    block_type: 'filter_form'
    title?: string
    description?: string
    fields: Array<{
      key: string
      label: string
      type: string
      required: boolean
      default?: any
      options?: Array<{ label: string; value: string }>
      placeholder?: string
    }>
    session_id: string
    request_id: string
  }
}>()

const formData = reactive<Record<string, any>>({})
const loading = ref(false)

// 初始化表单数据
props.block.fields.forEach(field => {
  formData[field.key] = field.default ?? null
})

// 提交表单
async function handleSubmit() {
  loading.value = true
  try {
    await axios.post(`/api/sessions/${props.block.session_id}/params`, {
      request_id: props.block.request_id,
      params: formData,
    })
  } catch (error) {
    console.error('提交参数失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card shadow="hover" class="filter-form">
    <template #header v-if="block.title">
      <span>{{ block.title }}</span>
    </template>
    
    <p class="description" v-if="block.description">{{ block.description }}</p>
    
    <el-form :model="formData" label-width="100px">
      <el-form-item
        v-for="field in block.fields"
        :key="field.key"
        :label="field.label"
        :required="field.required"
      >
        <!-- 文本输入 -->
        <el-input
          v-if="field.type === 'text'"
          v-model="formData[field.key]"
          :placeholder="field.placeholder"
        />
        
        <!-- 数字输入 -->
        <el-input-number
          v-else-if="field.type === 'number'"
          v-model="formData[field.key]"
        />
        
        <!-- 日期选择 -->
        <el-date-picker
          v-else-if="field.type === 'date'"
          v-model="formData[field.key]"
          type="date"
          :placeholder="field.placeholder"
        />
        
        <!-- 日期时间选择 -->
        <el-date-picker
          v-else-if="field.type === 'datetime'"
          v-model="formData[field.key]"
          type="datetime"
          :placeholder="field.placeholder"
        />
        
        <!-- 下拉选择 -->
        <el-select
          v-else-if="field.type === 'select'"
          v-model="formData[field.key]"
          :placeholder="field.placeholder"
        >
          <el-option
            v-for="opt in field.options"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        
        <!-- 复选框 -->
        <el-checkbox
          v-else-if="field.type === 'checkbox'"
          v-model="formData[field.key]"
        />
        
        <!-- 默认文本输入 -->
        <el-input
          v-else
          v-model="formData[field.key]"
          :placeholder="field.placeholder"
        />
      </el-form-item>
      
      <el-form-item>
        <el-button type="primary" @click="handleSubmit" :loading="loading">
          提交
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.filter-form {
  max-width: 100%;
}

.description {
  color: #909399;
  margin-bottom: 16px;
}
</style>
