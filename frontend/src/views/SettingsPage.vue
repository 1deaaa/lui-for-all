<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const settings = ref({
  // 安全与扩展配置
  safety_default_action: 'confirm',
  mcp_api_token: '',
  
  // 主模型配置
  llm_api_base: '',
  llm_api_key: '',
  llm_model_id: '',
  llm_extra_body: ''
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
    const [settingsRes, llmRes] = await Promise.all([
      axios.get('/api/settings'),
      axios.get('/api/llm-status/main')
    ])
    
    settings.value = {
      safety_default_action: settingsRes.data.safety_default_action || 'confirm',
      mcp_api_token: settingsRes.data.mcp_api_token || '',
      llm_api_base: llmRes.data.llm_api_base || '',
      llm_api_key: llmRes.data.llm_api_key || '',
      llm_model_id: llmRes.data.llm_model_id || '',
      llm_extra_body: llmRes.data.llm_extra_body || ''
    }
    
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '读取设置失败')
  } finally {
    loading.value = false
  }
}

// 保存设置
async function saveSettings(silent = false) {
  if (loading.value) return // 防止初始加载触发
  saving.value = true
  try {
    formatApiBase()
    formatExtraBody() // 保存前格式化
    
    await Promise.all([
      axios.put('/api/settings', {
        safety_default_action: settings.value.safety_default_action,
        mcp_api_token: settings.value.mcp_api_token
      }),
      axios.put('/api/llm-status/main', {
        llm_api_base: settings.value.llm_api_base,
        llm_api_key: settings.value.llm_api_key,
        llm_model_id: settings.value.llm_model_id,
        llm_extra_body: settings.value.llm_extra_body
      })
    ])
    if (!silent) {
      ElMessage.success('设置已保存并生效')
    }
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
  url = url.replace(/\/+$/, '')
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
  formatExtraBody()
  testing.value = true
  testStatus.value = null
  try {
    const response = await axios.post('/api/llm-status/test', {
      llm_api_base: settings.value.llm_api_base,
      llm_api_key: settings.value.llm_api_key,
      llm_model_id: settings.value.llm_model_id,
      llm_extra_body: settings.value.llm_extra_body
    })
    ElMessage.success(`测试成功！模型回复：\n${response.data.reply}`)
    testStatus.value = 'success'
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '测试连接失败')
    testStatus.value = 'error'
  } finally {
    testing.value = false
  }
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
    const response = await axios.post('/api/llm-status/probe', {
      llm_api_base: settings.value.llm_api_base,
      llm_api_key: settings.value.llm_api_key,
      llm_model_id: '',
      llm_extra_body: ''
    })
    availableModels.value = response.data.models || []
    if (availableModels.value.length === 0) {
      ElMessage.warning('获取到的模型列表为空')
    } else {
      ElMessage.success(`成功探测了 ${availableModels.value.length} 个模型`)
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '探测模型失败')
  } finally {
    fetchingModels.value = false
  }
}

function handleModelSelectVisible(visible: boolean) {
  if (visible && availableModels.value.length === 0) {
    fetchModels()
  }
}

// 生成随机 Token 并立即保存
async function generateMcpToken() {
  settings.value.mcp_api_token = crypto.randomUUID().replace(/-/g, '')
  await saveSettings(true)
  ElMessage.success('已生成随机 Token 并已保存')
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

function resolveMcpGatewayOrigin(): string {
  const isViteDevServer = import.meta.env.DEV && window.location.port === '5173'
  if (isViteDevServer) {
    const devBackend = import.meta.env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:6689'
    return devBackend.replace(/\/+$/, '')
  }
  return `${window.location.protocol}//${window.location.host}`.replace(/\/+$/, '')
}

const mcpGatewayOrigin = computed(() => resolveMcpGatewayOrigin())
const mcpGatewayUrl = computed(() => `${mcpGatewayOrigin.value}/mcp/`)
const mcpJsonExample = computed(() => {
  const token = settings.value.mcp_api_token || '在这里填入您的Token'
  const url = mcpGatewayUrl.value
  
  // 提供标准的 Streamable HTTP 连接 JSON
  return JSON.stringify({
    "mcpServers": {
      "lui-for-all-remote": {
        "type": "streamable-http",
        "url": url,
        "headers": {
          "Authorization": `Bearer ${token}`
        }
      }
    }
  }, null, 2)
})

async function copyMcpJson() {
  try {
    await navigator.clipboard.writeText(mcpJsonExample.value)
    ElMessage.success('JSON 已复制到剪贴板！')
  } catch (e) {
    ElMessage.error('复制失败，请手动选取复制。')
  }
}

function highlightJson(code: string) {
  // @ts-ignore
  if (window.hljs) {
    // @ts-ignore
    return window.hljs.highlight(code, { language: 'json' }).value
  }
  return code
}

onMounted(loadSettings)
</script>

<template>
  <div class="settings-page">
    <div class="header-section">
      <div class="header-titles">
        <h2>系统与核心配置</h2>
        <p class="subtitle">管理主干模型策略与服务端点暴露，所有更改即时生效</p>
      </div>
    </div>

    <div class="content-scroll" v-loading="loading">
      <el-form :model="settings" label-position="top" class="settings-form">
        <div class="cards-grid">
          
          <!-- LLM Config Card -->
          <el-card class="setting-card fade-in-up llm-card" shadow="never" style="animation-delay: 0.05s;">
            <template #header>
              <div class="card-header">
                <Icon icon="lucide:cpu" class="card-icon" />
                <div style="flex: 1;">
                  <div class="card-title">主模型配置</div>
                  <div class="card-desc">配置核心智能体所依赖的模型接口与凭据</div>
                </div>
                
                <div class="llm-actions">
                  <transition name="el-fade-in">
                    <div v-if="testStatus === 'success'" class="status-indicator success">
                      <Icon icon="lucide:check-circle-2" /> <span>连通</span>
                    </div>
                  </transition>
                  <transition name="el-fade-in">
                    <div v-if="testStatus === 'error'" class="status-indicator error">
                      <Icon icon="lucide:x-circle" /> <span>失败</span>
                    </div>
                  </transition>
                  <el-button @click="testConnection" :loading="testing" plain round size="default" class="test-btn">
                    <Icon icon="lucide:zap" class="btn-icon" /> 测试连接
                  </el-button>
                </div>
              </div>
            </template>
            
            <el-row :gutter="24">
              <el-col :span="24" :md="12">
                <el-form-item label="API 服务端点 (Base URL)">
                  <el-input 
                    v-model="settings.llm_api_base" 
                    placeholder="如: https://api.openai.com/v1" 
                    @blur="formatApiBase"
                    @change="() => saveSettings(false)"
                  >
                    <template #prefix>
                      <Icon icon="lucide:globe" />
                    </template>
                  </el-input>
                </el-form-item>
              </el-col>
              <el-col :span="24" :md="12">
                <el-form-item label="API 秘钥 (API Key)">
                  <el-input 
                    v-model="settings.llm_api_key" 
                    type="password" 
                    show-password 
                    placeholder="系统管理密钥不会在前端明文显示" 
                    @change="() => saveSettings(false)"
                  >
                    <template #prefix>
                      <Icon icon="lucide:key" />
                    </template>
                  </el-input>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="24">
              <el-col :span="24" :md="12">
                <el-form-item label="主分配模型 (Model ID)">
                  <div class="model-select-wrap">
                    <el-select 
                      v-model="settings.llm_model_id" 
                      placeholder="选择或输入模型 ID" 
                      filterable 
                      allow-create 
                      default-first-option
                      :loading="fetchingModels"
                      @visible-change="handleModelSelectVisible"
                      @change="() => saveSettings(false)"
                      class="model-select"
                    >
                      <template #prefix>
                        <Icon icon="lucide:bot" />
                      </template>
                      <el-option
                        v-for="model in availableModels"
                        :key="model"
                        :label="model"
                        :value="model"
                      />
                    </el-select>
                    <el-button @click="fetchModels" :loading="fetchingModels" plain>
                      <Icon icon="lucide:radar" /> 探测
                    </el-button>
                  </div>
                </el-form-item>
              </el-col>
              <el-col :span="24" :md="12">
                <el-form-item label="模型附加参数 (Extra JSON Body)">
                  <el-input 
                    v-model="settings.llm_extra_body" 
                    type="textarea"
                    :rows="2"
                    placeholder='如: {"custom_field": "value"}'
                    @blur="formatExtraBody"
                    @change="() => saveSettings(false)"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-card>

          <!-- Safety Config Card -->
          <el-card class="setting-card fade-in-up" shadow="never" style="animation-delay: 0.15s;">
            <template #header>
              <div class="card-header">
                <Icon icon="lucide:shield-alert" class="card-icon" />
                <div>
                  <div class="card-title">全局安全放行策略</div>
                  <div class="card-desc">控制终端与读写能力的审批机制</div>
                </div>
              </div>
            </template>
            
            <el-form-item label="默认审批动作">
              <el-select v-model="settings.safety_default_action" @change="handleSafetyActionChange" style="width: 100%;">
                <el-option label="全部允许" value="allow">
                  <div class="flex-option">
                    <Icon icon="lucide:unlock" class="text-danger" />
                    <span class="text-danger">全部允许</span>
                  </div>
                </el-option>
                <el-option label="手动审批" value="confirm">
                  <div class="flex-option">
                    <Icon icon="lucide:user-check" class="text-success" />
                    <span>手动审批</span>
                  </div>
                </el-option>
                <el-option label="直接阻止" value="block">
                  <div class="flex-option">
                    <Icon icon="lucide:ban" />
                    <span>直接阻止</span>
                  </div>
                </el-option>
              </el-select>
              
              <transition name="el-zoom-in-top">
                <div v-if="settings.safety_default_action === 'allow'" class="allow-warning">
                  <Icon icon="lucide:flame" class="warning-icon" />
                  <div class="warning-text">
                    <strong>风险警告：</strong>当前模式下，AI将无需任何审批，可以执行任何请求。绝对禁止在有重要数据和无法回滚的环境中使用！<br/>
                    如果你不知道自己在做什么，禁止选择此项，请选择手动审批！
                    如果您是在使用外部 MCP 客户端，则<strong>必须开启此项</strong>以实现全自动！务必使用信任的模型和环境！
                  </div>
                </div>
              </transition>
            </el-form-item>
          </el-card>

          <!-- MCP Config Card -->
          <el-card class="setting-card fade-in-up" shadow="never" style="animation-delay: 0.25s;">
            <template #header>
              <div class="card-header">
                <Icon icon="lucide:network" class="card-icon" />
                <div>
                  <div class="card-title">对外暴露协议代理 (MCP)</div>
                  <div class="card-desc">将系统能力通过 Streamable HTTP 协议暴露给其他智能体</div>
                </div>
              </div>
            </template>

            <el-alert
              title="操作规避声明"
              type="error"
              show-icon
              :closable="false"
              style="margin-bottom: 24px;"
            >
              <template #title>AI将无需任何审批，可以执行任何请求。绝对禁止在有重要数据和无法回滚的环境中使用！</template>
            </el-alert>

            <el-form-item label="网关防御 Token (API Secret)">
              <el-input 
                v-model="settings.mcp_api_token" 
                type="password"
                show-password
                placeholder="如果设定，则外部访问必定需要 Bearer 鉴权。"
                @change="() => saveSettings(false)"
              >
                <template #append>
                  <el-button @click="generateMcpToken">
                    <Icon icon="lucide:dices" /> 随机生成
                  </el-button>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="配置外部大模型客户端连接 (以 VS Code / Cline 为例)">
              <div class="mcp-instructions">
                <div class="instruction-box">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h4>
                      <Icon icon="lucide:terminal" />
                      cline_mcp_settings.json 等配置文件
                    </h4>
                    <el-button size="small" @click="copyMcpJson" plain round>
                      <Icon icon="lucide:copy" style="margin-right: 4px;" /> 复制完整 JSON
                    </el-button>
                  </div>
                  <p>在 VS Code 的 Cline 或 Roo Code 等多模型插件中，建议将连接类型设置为 <code>streamable-http</code>，并桥接本远程网关：</p>
                  <p class="instruction-note">
                    <Icon icon="lucide:server" /> 当前示例网关地址：<code>{{ mcpGatewayUrl }}</code>
                  </p>
                  <div class="code-block" v-html="highlightJson(mcpJsonExample)"></div>
                  <p class="instruction-note">
                    <Icon icon="lucide:info" /> 开发模式下（5173）示例会自动指向后端端口（默认 6689）；部署模式下示例会自动使用当前同源端口。请确保启用了正确的 Bearer Header（如已启用防御）。
                  </p>
                </div>
              </div>
            </el-form-item>
          </el-card>
        </div>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color-page);
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 40px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  z-index: 10;
}

.header-titles h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* .global-actions 已移除，无全局保存按钮 */

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  animation: fadeIn 0.3s ease;
}
.status-indicator.success { color: var(--el-color-success); }
.status-indicator.error { color: var(--el-color-danger); }

.btn-icon {
  margin-right: 6px;
  font-size: 1.1em;
}

.content-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px;
}

.settings-form {
  max-width: 1400px;
  margin: 0 auto;
}

.cards-grid {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.setting-card {
  border-radius: 12px;
  border: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.llm-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
}
.status-indicator.success { color: var(--el-color-success); }
.status-indicator.error { color: var(--el-color-danger); }

.test-btn {
  margin-left: 8px;
}

.card-icon {
  font-size: 20px;
  margin-right: 4px;
  color: var(--el-color-primary);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}

.card-desc {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-weight: normal;
  margin-top: 4px;
}

.model-select-wrap {
  display: flex;
  width: 100%;
  gap: 12px;
}

.model-select {
  flex-grow: 1;
}

.flex-option {
  display: flex;
  align-items: center;
  gap: 8px;
}
.text-danger { color: var(--el-color-danger) !important; }
.text-success { color: var(--el-color-success) !important; }

/* 警示区动效与样式 */
.allow-warning {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: #fff0f0;
  border: 1px solid #ffcccc;
}
.warning-icon {
  font-size: 20px;
  color: #c9302c;
  line-height: 1;
}
.warning-text {
  font-size: 13px;
  color: #c9302c;
  line-height: 1.6;
}

.mcp-instructions {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 8px;
  width: 100%;
}
.instruction-box {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
}
.instruction-box h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: var(--el-text-color-regular);
  display: flex;
  align-items: center;
  gap: 6px;
}
.instruction-box p {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.instruction-note {
  font-size: 12px !important;
  color: var(--el-text-color-placeholder) !important;
  margin-top: 12px !important;
  margin-bottom: 0 !important;
}
.code-block {
  background: #f8f9fa;
  color: #24292e;
  padding: 14px;
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 13px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  border: 1px solid var(--el-border-color-lighter);
}

/* 入场动画 */
.fade-in-up {
  opacity: 0;
  animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes fadeInUp {
  0% { opacity: 0; transform: translateY(15px); }
  100% { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--el-text-color-regular);
}
</style>
