<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useProjectStore } from '@/stores/project'
import type { Session } from '@/vite-env.d'
import BlockRenderer from '@/components/BlockRenderer.vue'
import { ElMessage } from 'element-plus'
import MarkdownRenderer from '@/components/llm-markdown-render/MarkdownRenderer.vue'

const sessionStore = useSessionStore()
const projectStore = useProjectStore()
const route = useRoute()

const inputMessage = ref('')
const messageContainer = ref<HTMLElement | null>(null)
const sessionCreating = ref(false)
const runtimeExpanded = ref(false)
// 每条消息的思考内容折叠状态（默认折叠）
const thoughtExpanded = ref<Record<string, boolean>>({})
function toggleThought(msgId: string) {
  thoughtExpanded.value[msgId] = !thoughtExpanded.value[msgId]
}

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

// 快速切换项目：选中 -> 拉取历史 -> 创建新会话
async function selectProject(projectId: string) {
  const found = projectStore.projects.find((p) => p.id === projectId)
  if (!found) return
  projectStore.currentProject = found
  sessionStore.clearSession()
  await sessionStore.fetchHistory(projectId)
  await startSession(projectId)
}

// 切换到历史会话
async function switchToHistory(session: Session) {
  if (sessionStore.currentSession?.id === session.id) return
  sessionStore.clearSession()
  sessionStore.currentSession = session
  await sessionStore.loadSession(session.id)
}

// 删除历史会话
async function handleDeleteSession(session: Session, e: MouseEvent) {
  e.stopPropagation()
  await sessionStore.deleteSession(session.id)
  // 若删完后无活跃会话，自动建一条新的
  if (!sessionStore.currentSession && selectedProject.value) {
    await startSession(selectedProject.value.id)
  }
}

// 创建对话 session
async function startSession(projectId: string) {
  if (sessionCreating.value) return
  sessionCreating.value = true
  try {
    await sessionStore.createSession(projectId)
    await sessionStore.fetchHistory(projectId)
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
// 监听 messages 变化，流式输出时自动滚动到底部
watch(
  () => sessionStore.messages.map(m => m.content + (m.thought || '')),
  async () => {
    if (sessionStore.isStreaming) {
      await nextTick()
      scrollToBottom()
    }
  },
  { deep: false }
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

      <!-- 历史会话列表 -->
      <template v-if="selectedProject && sessionStore.historyList.length > 0">
        <div class="panel-divider" />
        <div class="panel-title-sm">历史对话</div>
        <div
          v-for="s in sessionStore.historyList"
          :key="s.id"
          class="history-item"
          :class="{ active: sessionStore.currentSession?.id === s.id }"
          @click="switchToHistory(s)"
        >
          <div class="history-item-title">{{ s.title || '未命名对话' }}</div>
          <button class="history-item-del" @click="handleDeleteSession(s, $event)" title="删除">&times;</button>
        </div>
      </template>

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
        <el-button
          v-if="selectedProject"
          size="small"
          :loading="sessionCreating"
          :disabled="sessionStore.isStreaming"
          @click="startSession(selectedProject.id)"
          class="new-chat-btn"
        >
          + 新建对话
        </el-button>
      </div>

      <!-- 消息流 -->
      <div class="message-list" ref="messageContainer">
        <!-- 欢迎语 -->
        <div v-if="sessionStore.messages.length === 0 && !sessionStore.loading" class="welcome-screen">
          <template v-if="selectedProject">
            <div class="welcome-icon">
              <Icon icon="solar:chat-round-dots-bold-duotone" />
            </div>
            <div class="welcome-title">与 {{ selectedProject.name }} 开始对话</div>
            <div class="welcome-desc">你可以用自然语言描述你想完成的操作，AI 会自动帮你调用对应接口。</div>
          </template>
          <template v-else>
            <div class="welcome-icon">
              <Icon icon="solar:magnifer-bold-duotone" />
            </div>
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
            <Icon v-if="msg.role === 'user'" icon="solar:user-bold-duotone" />
            <Icon v-else icon="solar:smart-home-robot-bold-duotone" />
          </div>
          <div class="message-bubble">
            <div v-if="msg.thought" class="message-thought">
              <div class="thought-header" @click="toggleThought(msg.id)">
                <el-icon v-if="sessionStore.isStreaming && !msg.content" class="is-loading"><Loading /></el-icon>
                <el-icon v-else><Monitor /></el-icon>
                <span>AI 思考过程</span>
                <el-icon class="thought-toggle" :class="{ expanded: thoughtExpanded[msg.id] }"><ArrowDown /></el-icon>
              </div>
              <div class="thought-body" :class="{ expanded: thoughtExpanded[msg.id] || (sessionStore.isStreaming && !msg.content) }">
                <div class="thought-content">{{ msg.thought }}</div>
              </div>
            </div>
            <!-- HTTP 执行标签（仅 assistant 消息且有 http_calls 时显示）-->
            <div
              v-if="msg.role === 'assistant' && msg.metadata?.http_calls?.length"
              class="msg-http-calls"
            >
              <span
                v-for="(call, ci) in msg.metadata.http_calls"
                :key="ci"
                class="http-badge"
                :class="{
                  'http-badge--ok': call.status_code >= 200 && call.status_code < 300,
                  'http-badge--redirect': call.status_code >= 300 && call.status_code < 400,
                  'http-badge--client-err': call.status_code >= 400 && call.status_code < 500,
                  'http-badge--server-err': call.status_code >= 500,
                  'http-badge--unknown': !call.status_code || call.status_code === 0,
                }"
              >{{ call.method }} {{ call.url }} <span class="http-badge-code">{{ call.status_code }}</span></span>
            </div>
            <div v-if="msg.content" class="message-text">
              <MarkdownRenderer :content="msg.content" />
            </div>
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

        <!-- 加载中 -->
        <div class="loading-row" v-if="sessionStore.loading || sessionCreating">
          <div class="loading-dots">
            <span></span><span></span><span></span>
          </div>
          <span class="loading-text">{{ sessionCreating ? '正在建立会话...' : 'AI 处理中...' }}</span>
        </div>

        <!-- 错误提示 -->
        <div class="error-row" v-if="sessionStore.error">
          <el-alert :title="sessionStore.error" type="error" :closable="false" show-icon />
        </div>
      </div>

      <!-- 运行时进度条 -->
      <div
        v-if="sessionStore.isStreaming || sessionStore.runtimeEvents.length > 0"
        class="runtime-bar"
      >
        <div class="runtime-bar-summary" @click="runtimeExpanded = !runtimeExpanded">
          <el-progress
            :percentage="sessionStore.progressPercent"
            :indeterminate="sessionStore.isStreaming && sessionStore.progressPercent === 0"
            :show-text="false"
            :stroke-width="3"
            class="runtime-bar-progress"
          />
          <span class="runtime-bar-msg">{{ sessionStore.progressMessage || 'AI 正在处理中...' }}{{ sessionStore.progressPercent > 0 ? '　' + sessionStore.progressPercent + '%' : '' }}</span>
          <el-icon class="runtime-bar-toggle" :class="{ expanded: runtimeExpanded }">
            <ArrowDown />
          </el-icon>
        </div>
        <div v-if="runtimeExpanded && sessionStore.runtimeEvents.length > 0" class="runtime-bar-events">
          <div
            v-for="event in sessionStore.runtimeEvents.slice(-8)"
            :key="event.id"
            class="runtime-event-item"
          >
            <!-- HTTP 执行结果标签 -->
            <template v-if="event.type === 'tool_completed' && event.status_code">
              <span
                class="http-badge"
                :class="{
                  'http-badge--ok': event.status_code >= 200 && event.status_code < 300,
                  'http-badge--redirect': event.status_code >= 300 && event.status_code < 400,
                  'http-badge--client-err': event.status_code >= 400 && event.status_code < 500,
                  'http-badge--server-err': event.status_code >= 500,
                  'http-badge--unknown': !event.status_code || event.status_code === 0,
                }"
              >{{ event.method ? event.method + ' ' : '' }}{{ event.status_code }}</span>
              <span class="runtime-event-title">{{ event.url || event.title }}</span>
              <span class="runtime-event-detail">{{ event.detail }}</span>
            </template>
            <template v-else>
              <span class="runtime-event-title">{{ event.title }}</span>
              <span class="runtime-event-detail">{{ event.detail }}</span>
            </template>
          </div>
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
  background: var(--bg-color-main, #ffffff);
}

/* ============ 左侧面板 ============ */
.project-panel {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-color-light, #e5e5e5);
  background: var(--bg-color-main, #ffffff);
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px 0 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.panel-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-secondary, #737373);
  padding: 0 16px 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.panel-title-sm {
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-secondary, #737373);
  padding: 12px 16px 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.history-item {
  position: relative;
  display: flex;
  align-items: center;
  padding: 8px 16px;
  cursor: pointer;
  border-radius: 6px;
  margin: 0 8px 2px;
  transition: background 0.15s;
}
.history-item:hover {
  background: var(--color-bg-hover, #f5f5f5);
}
.history-item.active {
  background: var(--color-primary-light, #eff6ff);
}
.history-item-title {
  flex: 1;
  font-size: 13px;
  color: var(--color-text-primary, #171717);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-item-del {
  display: none;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  color: #a3a3a3;
  padding: 0 2px;
  line-height: 1;
  flex-shrink: 0;
}
.history-item:hover .history-item-del {
  display: block;
}

/* ============ 运行时进度条（输入框上方折叠式） ============ */
.runtime-bar {
  flex-shrink: 0;
  border-top: 1px solid var(--border-color-light, #e5e5e5);
  background: #fafafa;
}

.runtime-bar-summary {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 8px 24px;
  cursor: pointer;
  user-select: none;
}

.runtime-bar-progress {
  width: 64px;
  flex-shrink: 0;
}

.runtime-bar-msg {
  font-size: 13px;
  color: var(--color-text-secondary, #737373);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.runtime-bar-toggle {
  position: absolute;
  right: 24px;
  font-size: 12px;
  color: #a3a3a3;
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.runtime-bar-toggle.expanded {
  transform: rotate(180deg);
}

.runtime-bar-events {
  padding: 0 24px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
  align-items: center;
}


.runtime-event-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 6px;
  background: #fdfdfd;
  border: 1px solid #e5e5e5;
  border-left: 3px solid #a3a3a3;
  width: 100%;
}

.http-badge {
  flex-shrink: 0;
  display: inline-block;
  padding: 1px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  font-family: monospace;
  letter-spacing: 0.5px;
}
.http-badge--ok {
  background: #dcfce7;
  color: #15803d;
}
.http-badge--redirect {
  background: #fef9c3;
  color: #92400e;
}
.http-badge--client-err {
  background: #fee2e2;
  color: #b91c1c;
}
.http-badge--server-err {
  background: #fce7f3;
  color: #9d174d;
}
.http-badge--unknown {
  background: #f3f4f6;
  color: #6b7280;
}

.runtime-event-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary, #0f0f0f);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.runtime-event-detail {
  font-size: 11px;
  color: var(--color-text-secondary, #737373);
  flex-shrink: 0;
}

.panel-divider {
  height: 1px;
  background: var(--border-color-light, #e5e5e5);
  margin: 12px 0;
}

.panel-empty {
  padding: 24px 16px;
  text-align: center;
  color: var(--color-text-secondary, #737373);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: center;
}

.project-item {
  padding: 10px 16px;
  border-radius: 0;
  cursor: pointer;
  transition: background 0.25s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  border-left: 3px solid transparent;
}

.project-item:not(.disabled):hover {
  background: #ebebeb;
}

.project-item.active {
  background: #e0e0e0;
  color: #0f0f0f;
  border-left: 3px solid #0f0f0f;
}
.project-item.active .project-item-name {
  color: #0f0f0f;
}
.project-item.active .project-item-url {
  color: #737373;
}

.project-item.disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.project-item-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #0f0f0f);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.2s ease;
}

.project-item-url {
  font-size: 12px;
  color: var(--color-text-secondary, #737373);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
  max-height: 0;
  opacity: 0;
  transition: max-height 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.project-item:hover .project-item-url,
.project-item.active .project-item-url {
  max-height: 20px;
  opacity: 1;
}

/* ============ 右侧聊天区 ============ */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
  overflow: hidden;
}

/* 顶栏 */
.chat-topbar {
  height: 64px;
  padding: 0 24px;
  border-bottom: 1px solid var(--border-color-light, #e5e5e5);
  background: var(--bg-color-main, #ffffff);
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.chat-project-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--color-text-primary, #0f0f0f);
}

.new-chat-btn {
  margin-left: auto;
  flex-shrink: 0;
}

.chat-project-url {
  font-size: 12px;
  color: var(--color-text-secondary, #a3a3a3);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}

.chat-hint-topbar {
  font-size: 14px;
  color: var(--color-text-secondary, #737373);
  flex: 1;
}

/* 消息列表 */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px 24px;
  scroll-behavior: smooth;
  display: flex;
  flex-direction: column;
  align-items: center; /* 居中内容流 */
}

/* 内部限制宽度以达成优雅阅读 */
.message-list > * {
  width: 100%;
  max-width: 1120px;
}

/* 欢迎屏 */
.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 100px 20px;
  gap: 16px;
}

.welcome-icon { font-size: 48px; color: #0f0f0f; }
.welcome-title { font-size: 24px; font-weight: 600; color: var(--color-text-primary, #0f0f0f); }
.welcome-desc { font-size: 15px; color: var(--color-text-secondary, #737373); max-width: 480px; line-height: 1.6; }

/* 消息气泡整体排布 */
.message-item {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 24px 0;
  animation: fade-in 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}

.message-item.user {
  flex-direction: row-reverse; /* 用户气泡靠右 */
}

.message-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  border-radius: 0; /* 绝对直角 */
}

.message-item.user .message-avatar {
  background: #0f0f0f;
  color: #ffffff;
}

.message-item.assistant .message-avatar {
  background: #ffffff;
  border: 1px solid #e5e5e5;
  color: #0f0f0f;
}

.message-bubble {
  max-width: 92%;
  font-size: 15px;
  line-height: 1.7;
  word-break: break-word;
}

.message-item.user .message-bubble {
  background: #ffffff;
  color: #0f0f0f;
  padding: 12px 16px;
  border-radius: 0;
  border: 1px solid #e5e5e5;
}

.message-item.assistant .message-bubble {
  background: transparent;
  color: var(--color-text-primary, #0f0f0f);
  padding: 4px 0;
  width: 100%;
}

.msg-http-calls {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.http-badge-code {
  font-weight: 800;
  margin-left: 4px;
}

/* Markdown 渲染样式规范化 */
.message-text :deep(p) { margin: 0 0 12px; }
.message-text :deep(p:last-child) { margin-bottom: 0; }
.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4) {
  margin: 24px 0 12px;
  font-weight: 600;
  line-height: 1.4;
  color: #000;
}
.message-text :deep(ul),
.message-text :deep(ol) {
  margin: 12px 0;
  padding-left: 1.5em;
}
.message-text :deep(li) { margin: 6px 0; }
.message-text :deep(strong) { font-weight: 600; color: #000; }
.message-text :deep(code) {
  font-family: 'JetBrains Mono', monospace;
  background: #f4f4f4;
  padding: 2px 6px;
  border-radius: 0;
  font-size: 0.85em;
}
.message-text :deep(pre) {
  background: #0f0f0f;
  color: #f4f4f4;
  border-radius: 0;
  padding: 16px;
  overflow-x: auto;
  margin: 16px 0;
  font-size: 13px;
  line-height: 1.6;
}
.message-text :deep(blockquote) {
  border-left: 2px solid #0f0f0f;
  margin: 16px 0;
  padding: 4px 16px;
  color: #737373;
}
.message-text :deep(a) { color: #0f0f0f; text-decoration: underline; text-underline-offset: 4px; }
.message-text :deep(hr) { border: none; border-top: 1px solid #e5e5e5; margin: 24px 0; }
.message-text :deep(table) { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px; }
.message-text :deep(th), .message-text :deep(td) { border: 1px solid #e5e5e5; padding: 10px 14px; text-align: left; }
.message-text :deep(th) { background: #f9f9f9; font-weight: 600; }

/* 思考过程样式 (Mental Model Block) */
.message-thought {
  margin-bottom: 16px;
  background: #fafafa;
  border-left: 2px solid #d4d4d4;
  font-size: 14px;
  color: #525252;
}

.thought-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #525252;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
}

.thought-toggle {
  margin-left: auto;
  font-size: 11px;
  color: #a3a3a3;
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.thought-toggle.expanded {
  transform: rotate(180deg);
}

/* 默认折叠（仅显示标题），展开后全显 */
.thought-body {
  overflow: hidden;
  max-height: 0;
  opacity: 0;
  /* 收起方向：ease-in，先慢后快，干脆收回 */
  transition: max-height 0.3s cubic-bezier(0.4, 0, 0.6, 1), opacity 0.2s cubic-bezier(0.4, 0, 0.6, 1);
  padding: 0 14px;
}
.thought-body.expanded {
  max-height: 800px;
  opacity: 1;
  padding: 0 14px 10px;
  /* 展开方向：ease-out，先快后慢，自然展开 */
  transition: max-height 0.45s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.thought-content {
  white-space: pre-wrap;
  line-height: 1.6;
}

/* 内联 HTTP 执行记录 chip */
.inline-events {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.inline-event-chip {
  display: inline-block;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f0f0f0;
  color: #525252;
  border: 1px solid #e0e0e0;
  white-space: nowrap;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.inline-event-chip.completed {
  background: #f0fdf4;
  color: #16a34a;
  border-color: #bbf7d0;
}
.inline-event-chip.failed {
  background: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}
.inline-event-chip.running {
  background: #eff6ff;
  color: #2563eb;
  border-color: #bfdbfe;
}

.message-item.user .message-thought { display: none; }

/* UI Blocks */
.ui-blocks {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

/* 高级打字机式闪烁光标 / 脉冲 Loading */
.loading-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 0;
}

.loading-dots {
  display: flex;
  gap: 6px;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  border-radius: 0;
  background: #0f0f0f;
  animation: pulse-op 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes pulse-op {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.2; }
}

.loading-text { font-size: 14px; color: #737373; }
.error-row { padding: 16px 0; width: 100%; }

/* ============ 底部浮岛输入区 ============ */
.input-area {
  padding: 16px 24px 24px;
  background: #ffffff;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  border-top: 1px solid var(--border-color-light, #e5e5e5);
}

.input-wrapper {
  width: 100%;
  max-width: 1120px; /* 匹配主阅读流宽度 */
  border-radius: 0;
  border: 1px solid var(--border-color-light, #e5e5e5);
  background: #ffffff;
  box-shadow: 0 4px 20px rgba(0,0,0,0.04);
  overflow: hidden;
  transition: box-shadow 0.35s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}

.input-wrapper:focus-within {
  box-shadow: 0 8px 32px rgba(0,0,0,0.08);
  border-color: #a3a3a3;
}

.chat-input :deep(.el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  border-radius: 0;
  padding: 16px 20px;
  font-size: 15px;
  line-height: 1.6;
  resize: none;
  background: transparent;
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #fdfdfd;
}

.input-hint {
  font-size: 12px;
  color: #a3a3a3;
}
</style>
