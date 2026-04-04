<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Close } from '@element-plus/icons-vue'

const settings = ref({
  llm_api_base: '',
  llm_api_key: '',
  llm_model_id: '',
  llm_extra_body: '',
  safety_default_action: 'confirm',
  mcp_api_token: '',
})

const saving = ref(false)
const testing = ref(false)
const loading = ref(false)
const fetchingModels = ref(false)
const testStatus = ref<'success' | 'error' | null>(null)
const availableModels = ref<string[]>([])

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
      mcp_api_token: response.data.mcp_api_token || '',
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
  // 先清理掉末尾所有的冗余斜杠
  url = url.replace(/\/+$/, '')
  // 如果清理完后没有加上 /v1，则自动补全即可兼容绝大多数兼容端点
  if (!url.endsWith('/v1')) {
    url = url + '/v1'
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

// 生成随机 Token
function generateMcpToken() {
  settings.value.mcp_api_token = crypto.randomUUID().replace(/-/g, '')
  ElMessage.success('已生成随机 Token（保存后生效）')
}

// 获取模型列表
async function fetchModels() {
  if (!settings.value.llm_api_base) {
    ElMessage.warning('请先填写 API 端点')
    return
  }
  formatApiBase()
  fetchingModels.value = true
  try {
    const response = await axios.post('/api/settings/models', settings.value)
    availableModels.value = response.data.models || []
    if (availableModels.value.length === 0) {
      ElMessage.warning('获取到的模型列表为空')
    } else {
      ElMessage.success(`成功获取了 ${availableModels.value.length} 个模型`)
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '获取模型列表失败，请检查 Base URL 和 API Key')
  } finally {
    fetchingModels.value = false
  }
}

function handleModelSelectVisible(visible: boolean) {
  if (visible && availableModels.value.length === 0) {
    fetchModels()
  }
}

async function handleSafetyActionChange(val: string) {
  if (val === 'allow') {
    try {
      await ElMessageBox.confirm(
        '您正在开启全局默认允许（跳过审批）。所有工具调用将等同于人类默认批准，包括写文件和执行毁灭性指令等。确定开启吗？',
        '高危操作确认',
        { type: 'warning', confirmButtonText: '继续', cancelButtonText: '取消' }
      )
      await ElMessageBox.confirm(
        '请再次确认：如果您开启此选项以开放给 MCP 客户端调用，系统的一切安全门槛都将被彻底移除以实现全自动。如果接入的外部 AI 具有破坏性，系统将直接放行！您确实要继续吗？',
        '最后严重警告',
        { type: 'error', confirmButtonText: '我确定并承担风险', cancelButtonText: '放弃' }
      )
    } catch {
      settings.value.safety_default_action = 'confirm'
    }
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

        <el-form-item label="API Key">
          <el-input v-model="settings.llm_api_key" type="password" show-password placeholder="LLM API Key" />
        </el-form-item>

        <el-form-item label="模型 ID">
          <div style="display: flex; gap: 8px; width: 100%;">
            <el-select 
              v-model="settings.llm_model_id" 
              placeholder="选择或输入模型 ID" 
              filterable 
              allow-create 
              default-first-option
              :loading="fetchingModels"
              @visible-change="handleModelSelectVisible"
              style="flex-grow: 1;"
            >
              <el-option
                v-for="model in availableModels"
                :key="model"
                :label="model"
                :value="model"
              />
            </el-select>
            <el-button @click="fetchModels" :loading="fetchingModels" title="刷新获取服务器上的模型列表">
              探测模型
            </el-button>
          </div>
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
          <div style="width: 100%;">
            <el-select v-model="settings.safety_default_action" @change="handleSafetyActionChange">
              <el-option label="⚠️全部允许" value="allow" />
              <el-option label="✅需要审批" value="confirm" />
              <el-option label="🚫直接阻止" value="block" />
            </el-select>
            <div v-if="settings.safety_default_action === 'allow'" class="allow-warning">
              ⚠️ 警告：当前已开启全局默认允许，将跳过一切人类审批。如果您是在使用 MCP 模式（开放给其他 AI 客户端独立调用本应用的能力以实现全自动），则必须开启此项。请务必信任您所接入的外部大模型。
            </div>
          </div>
        </el-form-item>

        <el-divider content-position="left">MCP 对外服务网关</el-divider>

        <div style="padding: 0 40px 20px; width: 100%; box-sizing: border-box;">
          <el-alert
            title="绝对警告：MCP 使用风险"
            type="error"
            description="绝对禁止在重要且无法回滚的环境（如线上生产数据库、重要资金账户等）中使用此功能。由于外部大模型的严重幻觉可能导致非预期的灾难性写入和执行操作，带来不可估量的后果。如果你不知道自己在干什么，请不要使用此功能。"
            show-icon
            :closable="false"
            style="margin-bottom: 20px"
          />
        </div>

        <el-form-item label="使用前提">
          <div style="font-size: 14px; color: #E6A23C; font-weight: bold; background: #fdf6ec; padding: 8px 12px; border-radius: 4px; width: 100%;">
            如果要开放 MCP 服务给外部客户端调用，必须在上方安全配置中将「默认动作」切换为「全部允许」！否则外部调用将全部失败。
          </div>
        </el-form-item>

        <el-form-item label="API Token">
          <el-input 
            v-model="settings.mcp_api_token" 
            type="password"
            show-password
            placeholder="必须配置 Token 才能允许外部 Agent 访问 (请求必须带 Bearer Token)"
          >
            <template #append>
              <el-button @click="generateMcpToken">随机生成</el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="客户端配置">
          <div style="width: 100%; font-size: 13px; color: #606266; line-height: 1.6;">
            <strong>【 Cursor 配置方式 (SSE) 】</strong>
            <pre class="code-block">
Type: sse
Name: lui-for-all
URL: http://127.0.0.1:6687/mcp/sse</pre>
            
            <strong>【 标准 MCP 客户端配置示例 (如 Claude Desktop 等基于 stdio 的客户端) 】</strong><br/>
            请将以下内容填入客户端的 `mcp.json` 或 `claude_desktop_config.json` 中，并注意替换对应环境变量。
            <pre class="code-block">
{
  "mcpServers": {
    "lui-for-all": {
      "command": "fastmcp",
      "args": ["run", "app/mcp/server.py:mcp"],
      "env": {
        "LUI_MCP_API_TOKEN": "{{ settings.mcp_api_token || '您的TOKEN' }}"
      }
    }
  }
}</pre>
          </div>
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
  padding: 32px 40px;
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
  animation: fadeIn 0.35s cubic-bezier(0.16, 1, 0.3, 1);
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

.allow-warning {
  margin-top: 8px;
  font-size: 13px;
  color: #cf222e;
  line-height: 1.5;
  background: #ffebe9;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255, 129, 130, 0.4);
  animation: fadeIn 0.3s ease-out;
}

.code-block {
  background: #f5f7fa;
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  overflow-x: auto;
  margin: 6px 0 16px;
  color: #303133;
}
</style>
