<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useProjectStore } from '@/stores/project'
import BlockRenderer from '@/components/BlockRenderer.vue'
import { ElMessage } from 'element-plus'

const sessionStore = useSessionStore()
const projectStore = useProjectStore()
const route = useRoute()

const inputMessage = ref('')
const messageContainer = ref<HTMLElement | null>(null)
const sessionCreating = ref(false)

// 当前选中的项目（优先 store 里的，没有就取第一个已完成的）
const selectedProject = computed(() =>
  projectStore.currentProject ||
  projectStore.projects.find((p) => p.discovery_status === 'completed') ||
  null
)

// 已完成发现的项目列表（才能聊天）
const readyProjects = computed(() =>
  projectStore.projects.filter((p) => p.discovery_status === 'completed')
)

// 快速切换项目：选中 -> 创建新会话
async function selectProject(projectId: string) {
  const found = projectStore.projects.find((p) => p.id === projectId)
  if (!found) return
  projectStore.currentProject = found
  sessionStore.clearSession()
  await startSession(projectId)
}

// 创建对话 session
async function startSession(projectId: string) {
  if (sessionCreating.value) return
  sessionCreating.value = true
  try {
    await sessionStore.createSession(projectId)
  } catch (e: any) {
    ElMessage.error('创建会话失败: ' + (e.message || '未知错误'))
  } finally {
    sessionCreating.value = false
  }
}

// 发送消息
async function handleSend() {
  const text = inputMessage.value.trim()
  if (!text) return

  // 没有 session 时自动创建
  if (!sessionStore.currentSession) {
    const id = selectedProject.value?.id
    if (!id) {
      ElMessage.warning('请先在左侧选择一个项目')
      return
    }
    await startSession(id)
    if (!sessionStore.currentSession) return
  }

  inputMessage.value = ''
  await sessionStore.sendMessage(text)
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight
  }
}

onMounted(async () => {
  await projectStore.fetchProjects()
  const projectId = typeof route.query.project === 'string' ? route.query.project : null
  if (projectId) {
    await selectProject(projectId)
    return
  }
  // 如果已有当前项目且没有会话，自动建一个
  if (selectedProject.value && !sessionStore.currentSession) {
    await startSession(selectedProject.value.id)
  }
})

watch(
  () => route.query.project,
  async (projectId) => {
    if (typeof projectId === 'string' && projectId !== selectedProject.value?.id) {
      await selectProject(projectId)
    }
  }
)
</script>

<template>
  <div class="chat-page">
    <!-- 左侧项目面板 -->
    <div class="project-panel">
      <div class="panel-title">项目列表</div>

      <div v-if="readyProjects.length === 0" class="panel-empty">
        <p>暂无已完成发现的项目</p>
        <el-button type="primary" size="small" @click="$router.push('/projects')">
          去导入项目
        </el-button>
      </div>

      <div
        v-for="p in readyProjects"
        :key="p.id"
        class="project-item"
        :class="{ active: selectedProject?.id === p.id }"
        @click="selectProject(p.id)"
      >
        <div class="project-item-name">{{ p.name }}</div>
        <div class="project-item-url">{{ p.base_url }}</div>
      </div>

      <div class="panel-divider" v-if="projectStore.projects.filter(p => p.discovery_status !== 'completed').length > 0" />
      <div class="panel-title-sm" v-if="projectStore.projects.filter(p => p.discovery_status !== 'completed').length > 0">
        其他项目（建模未完成）
      </div>
      <div
        v-for="p in projectStore.projects.filter(p => p.discovery_status !== 'completed')"
        :key="p.id"
        class="project-item disabled"
        :title="`状态: ${p.discovery_status} — 请先完成 AI 建模后再使用`"
      >
        <div class="project-item-name">{{ p.name }}</div>
        <el-tag size="small" type="info">{{ p.discovery_status }}</el-tag>
      </div>
    </div>

    <!-- 右侧对话区 -->
    <div class="chat-area">
      <!-- 顶栏 -->
      <div class="chat-topbar">
        <template v-if="selectedProject">
          <span class="chat-project-name">{{ selectedProject.name }}</span>
          <span class="chat-project-url">{{ selectedProject.base_url }}</span>
        </template>
        <span v-else class="chat-hint-topbar">← 请在左侧选择一个项目</span>
        <el-button v-if="sessionStore.currentSession" text size="small" @click="selectProject(selectedProject!.id)">
          新建会话
        </el-button>
      </div>

      <!-- 消息流 -->
      <div class="message-list" ref="messageContainer">
        <!-- 欢迎语 -->
        <div v-if="sessionStore.messages.length === 0 && !sessionStore.loading" class="welcome-screen">
          <template v-if="selectedProject">
            <div class="welcome-icon">💬</div>
            <div class="welcome-title">与 {{ selectedProject.name }} 开始对话</div>
            <div class="welcome-desc">你可以用自然语言描述你想完成的操作，AI 会自动帮你调用对应接口。</div>
          </template>
          <template v-else>
            <div class="welcome-icon">🔍</div>
            <div class="welcome-title">请先选择项目</div>
            <div class="welcome-desc">在左侧选择一个已完成 AI 建模的项目，然后就可以开始对话了。</div>
          </template>
        </div>

        <div
          v-for="msg in sessionStore.messages"
          :key="msg.id"
          :class="['message-item', msg.role]"
        >
          <div class="message-avatar">
            <span v-if="msg.role === 'user'">👤</span>
            <span v-else>🤖</span>
          </div>
          <div class="message-bubble">
            <div class="message-text">{{ msg.content }}</div>
          </div>
        </div>

        <!-- UI Blocks -->
        <div class="ui-blocks" v-if="sessionStore.uiBlocks.length > 0">
          <BlockRenderer
            v-for="(block, index) in sessionStore.uiBlocks"
            :key="index"
            :block="block"
          />
        </div>

        <div
          v-if="sessionStore.isStreaming || sessionStore.runtimeEvents.length > 0"
          class="runtime-panel"
        >
          <div class="runtime-header">
            <span class="runtime-title">实时执行进度</span>
            <span class="runtime-percent">{{ sessionStore.progressPercent }}%</span>
          </div>
          <el-progress
            :percentage="sessionStore.progressPercent"
            :indeterminate="sessionStore.isStreaming && sessionStore.progressPercent === 0"
            :show-text="false"
            :stroke-width="8"
          />
          <div class="runtime-message">{{ sessionStore.progressMessage || 'AI 正在处理中...' }}</div>
          <div v-if="sessionStore.runtimeEvents.length > 0" class="runtime-event-list">
            <div
              v-for="event in sessionStore.runtimeEvents.slice(-8)"
              :key="event.id"
              class="runtime-event-item"
            >
              <span class="runtime-event-title">{{ event.title }}</span>
              <span class="runtime-event-detail">{{ event.detail }}</span>
            </div>
          </div>
        </div>

        <!-- 加载中 -->
        <div class="loading-row" v-if="sessionStore.loading || sessionCreating || sessionStore.isStreaming">
          <div class="loading-dots">
            <span></span><span></span><span></span>
          </div>
          <span class="loading-text">{{ sessionCreating ? '正在建立会话...' : (sessionStore.progressMessage || 'AI 处理中...') }}</span>
        </div>

        <!-- 错误提示 -->
        <div class="error-row" v-if="sessionStore.error">
          <el-alert :title="sessionStore.error" type="error" :closable="false" show-icon />
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-wrapper">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="3"
            :placeholder="selectedProject ? `描述你想对「${selectedProject.name}」执行的操作...` : '请先在左侧选择一个项目'"
            :disabled="!selectedProject || sessionCreating"
            @keydown.enter.ctrl.prevent="handleSend"
            @keydown.enter.exact.prevent="handleSend"
            resize="none"
            class="chat-input"
          />
          <div class="input-toolbar">
            <span class="input-hint">Enter 发送 &nbsp;·&nbsp; Shift+Enter 换行</span>
            <el-button
              type="primary"
              :loading="sessionStore.loading || sessionCreating"
              :disabled="!inputMessage.trim() || !selectedProject"
              @click="handleSend"
            >
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  height: 100%;
  display: flex;
  overflow: hidden;
  background: var(--bg-color-main, #f5f7fb);
}

/* ============ 左侧面板 ============ */
.project-panel {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-color-light, #e5e9f0);
  background: var(--bg-color-glass, rgba(255,255,255,0.7));
  backdrop-filter: blur(12px);
  overflow-y: auto;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.panel-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-secondary, #7a8599);
  padding: 4px 8px 8px;
}

.panel-title-sm {
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-secondary, #7a8599);
  padding: 4px 8px 4px;
}

.runtime-panel {
  margin: 12px 0 16px;
  padding: 14px 16px;
  border: 1px solid var(--border-color-light, #e5e9f0);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: var(--shadow-sm, 0 1px 2px rgba(0, 0, 0, 0.05));
}

.runtime-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.runtime-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-primary, #1a2035);
}

.runtime-percent {
  font-size: 12px;
  color: var(--color-text-secondary, #7a8599);
}

.runtime-message {
  margin-top: 10px;
  font-size: 13px;
  color: var(--color-text-secondary, #607086);
}

.runtime-event-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.runtime-event-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(var(--el-color-primary-rgb, 64, 133, 255), 0.06);
}

.runtime-event-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary, #1a2035);
}

.runtime-event-detail {
  font-size: 12px;
  color: var(--color-text-secondary, #7a8599);
}

.panel-divider {
  height: 1px;
  background: var(--border-color-light, #e5e9f0);
  margin: 8px 0;
}

.panel-empty {
  padding: 20px 12px;
  text-align: center;
  color: var(--color-text-secondary, #7a8599);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}

.project-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  border: 1px solid transparent;
}

.project-item:not(.disabled):hover {
  background: rgba(var(--el-color-primary-rgb, 64, 133, 255), 0.08);
  border-color: rgba(var(--el-color-primary-rgb, 64, 133, 255), 0.2);
}

.project-item.active {
  background: rgba(var(--el-color-primary-rgb, 64, 133, 255), 0.12);
  border-color: var(--color-primary, #4085ff);
}

.project-item.disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.project-item-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary, #1a2035);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-item-url {
  font-size: 11px;
  color: var(--color-text-secondary, #7a8599);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

/* ============ 右侧聊天区 ============ */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 顶栏 */
.chat-topbar {
  height: 48px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color-light, #e5e9f0);
  background: var(--bg-color-glass, rgba(255,255,255,0.7));
  backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.chat-project-name {
  font-weight: 700;
  font-size: 14px;
  color: var(--color-text-primary, #1a2035);
}

.chat-project-url {
  font-size: 12px;
  color: var(--color-text-secondary, #7a8599);
  flex: 1;
}

.chat-hint-topbar {
  font-size: 13px;
  color: var(--color-text-secondary, #7a8599);
  flex: 1;
}

/* 消息列表 */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  scroll-behavior: smooth;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 欢迎屏 */
.welcome-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 60px 20px;
  gap: 12px;
}

.welcome-icon { font-size: 48px; }
.welcome-title { font-size: 20px; font-weight: 700; color: var(--color-text-primary, #1a2035); }
.welcome-desc { font-size: 14px; color: var(--color-text-secondary, #7a8599); max-width: 400px; line-height: 1.6; }

/* 消息气泡 */
.message-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  animation: fade-in 0.3s ease-out;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
  font-size: 22px;
  margin-top: 2px;
}

.message-bubble {
  max-width: 72%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
  white-space: pre-wrap;
}

.message-item.user .message-bubble {
  background: linear-gradient(135deg, #4085ff, #5b6fff);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message-item.assistant .message-bubble {
  background: #fff;
  color: var(--color-text-primary, #1a2035);
  border: 1px solid var(--border-color-light, #e5e9f0);
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.message-text { line-height: 1.65; }

/* UI Blocks */
.ui-blocks {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 加载动画 */
.loading-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-primary, #4085ff);
  animation: bounce 1.2s infinite;
}

.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.loading-text {
  font-size: 13px;
  color: var(--color-text-secondary, #7a8599);
}

.error-row { padding: 4px 0; }

/* ============ 输入区 ============ */
.input-area {
  padding: 16px 20px;
  border-top: 1px solid var(--border-color-light, #e5e9f0);
  background: var(--bg-color-glass, rgba(255,255,255,0.85));
  backdrop-filter: blur(12px);
  flex-shrink: 0;
}

.input-wrapper {
  border-radius: 12px;
  border: 1px solid var(--border-color-light, #e5e9f0);
  background: #fff;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  overflow: hidden;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.input-wrapper:focus-within {
  box-shadow: 0 0 0 2px rgba(64, 133, 255, 0.25);
  border-color: var(--color-primary, #4085ff);
}

.chat-input :deep(.el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  border-radius: 0;
  padding: 14px 16px;
  font-size: 14px;
  resize: none;
  background: transparent;
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-top: 1px solid #f0f2f5;
}

.input-hint {
  font-size: 12px;
  color: #b0b7c3;
}
</style>
