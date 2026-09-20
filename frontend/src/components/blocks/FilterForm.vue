<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

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
const { t } = useI18n()

// 初始化表单数据
props.block.fields.forEach(field => {
  formData[field.key] = field.default ?? null
})

// 提交表单
// 说明：filter_form 为协议保留类型，当前后端无 /params 收集端点。
// 为避免 404 死链，提交仅做本地校验与提示，不发起网络请求。
async function handleSubmit() {
  loading.value = true
  try {
    const missing = props.block.fields.filter((f) => f.required && (formData[f.key] === null || formData[f.key] === '' || formData[f.key] === undefined))
    if (missing.length > 0) {
      ElMessage.warning(`${t('filterForm.missingRequired')}：${missing.map((f) => f.label).join('、')}`)
      return
    }
    ElMessage.info(t('filterForm.notSupported'))
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
          {{ t('filterForm.submit') }}
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
