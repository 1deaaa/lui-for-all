<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Check, Close } from '@element-plus/icons-vue'

// 设置表单
const settings = ref({
  llm_api_base: '',
  llm_api_key: '',
  llm_model_id: '',
  llm_extra_body: '',
  safety_default_action: 'confirm',
})

const saving = ref(false)
const testing = ref(false)
const loading = ref(false)
const testStatus = ref<'success' | 'error' | null>(null)

async function loadSettings() {
  loading.value = true
  try {
    const response = await axios.get('/api/settings')
    settings.value = {
      llm_api_base: response.data.llm_api_base || '',
      llm_api_key: response.data.llm_api_key || '',
      llm_model_id: response.data.llm_model_id || '',
      llm_extra_body: response.data.llm_extra_body || '',
      safety_default_action: response.data.safety_default_action || 'confirm',
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '读取设置失败')
  } finally {
    loading.value = false
  }
}

// 保存设置
async function saveSettings() {
  saving.value = true
  try {
    await axios.put('/api/settings', settings.value)
    ElMessage.success('设置已保存到 backend/.env')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '保存设置失败')
  } finally {
    saving.value = false
  }
}

// 自动格式化 API Endpoint
function formatApiBase() {
  let url = settings.value.llm_api_base.trim()
  if (!url) return
  if (url.endsWith('/')) {
    url = url.replace(/\/+$/, '')
  }
  settings.value.llm_api_base = url
}

// 自动修复并格式化 JSON
function formatExtraBody() {
  let body = settings.value.llm_extra_body.trim()
  if (!body) return
  
  if (!body.startsWith('{')) body = '{' + body
  if (!body.endsWith('}')) body = body + '}'
  
  try {
    const parsed = JSON.parse(body)
    settings.value.llm_extra_body = JSON.stringify(parsed, null, 2)
  } catch (e) {
    ElMessage.warning('附加参数 (Extra Body) 似乎不是标准的 JSON 格式，请检查')
    settings.value.llm_extra_body = body
  }
}

// 测试连接
async function testConnection() {
  formatApiBase()
  formatExtraBody() // 测试前自动修复 JSON
  testing.value = true
  testStatus.value = null
  try {
    const response = await axios.post('/api/settings/test-llm', settings.value)
    ElMessage.success(`测试成功！模型回复：\n${response.data.reply}`)
    testStatus.value = 'success'
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '测试连接失败')
    testStatus.value = 'error'
  } finally {
    testing.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-card class="settings-card" v-loading="loading">
      <el-form :model="settings" label-width="120px">
        <el-divider content-position="left">LLM 配置</el-divider>
        
        <el-form-item label="API 端点">
          <el-input 
            v-model="settings.llm_api_base" 
            placeholder="例如: https://api.openai.com/v1 (以 v1 结尾，无需末尾斜线)" 
            @blur="formatApiBase"
          />
        </el-form-item>
        
        <el-form-item label="模型 ID">
          <el-input v-model="settings.llm_model_id" placeholder="模型 ID" />
        </el-form-item>

        <el-form-item label="API Key">
          <el-input v-model="settings.llm_api_key" type="password" show-password placeholder="LLM API Key" />
        </el-form-item>

        <el-form-item label="附加参数(JSON)">
          <el-input 
            v-model="settings.llm_extra_body" 
            type="textarea"
            :rows="3"
            placeholder='传给 LLM 的额外 JSON 参数（将自动修复首尾大括号），例如: "custom_field": "value"'
            @blur="formatExtraBody"
          />
        </el-form-item>

        <el-divider content-position="left">安全配置</el-divider>
        
        <el-form-item label="默认动作">
          <el-select v-model="settings.safety_default_action">
            <el-option label="允许" value="allow" />
            <el-option label="确认" value="confirm" />
            <el-option label="阻断" value="block" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <div class="form-actions">
            <el-button type="primary" @click="saveSettings" :loading="saving">
              保存设置
            </el-button>
            <el-button type="success" @click="testConnection" :loading="testing">
              测试连接
            </el-button>
            
            <div v-if="testStatus === 'success'" class="status-indicator success">
              <el-icon><Check /></el-icon>
              <span>连接成功</span>
            </div>
            <div v-if="testStatus === 'error'" class="status-indicator error">
              <el-icon><Close /></el-icon>
              <span>连接失败</span>
            </div>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page {
  height: 100%;
  overflow-y: auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.settings-card {
  max-width: 600px;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  animation: fadeIn 0.3s ease;
}

.status-indicator.success {
  color: var(--el-color-success);
}

.status-indicator.error {
  color: var(--el-color-danger);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
