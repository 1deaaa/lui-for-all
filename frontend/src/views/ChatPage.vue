<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useWindowSize } from '@vueuse/core'
import { useRoute } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useProjectStore } from '@/stores/project'
import { useI18n } from 'vue-i18n'
import type { Session } from '@/vite-env.d'
import BlockRenderer from '@/components/BlockRenderer.vue'
import ConfirmPanel from '@/components/blocks/ConfirmPanel.vue'
import { ElMessage } from 'element-plus'
import MarkdownRenderer from '@/components/llm-markdown-render/MarkdownRenderer.vue'
import RouteMapAnalyzer from '@/components/project/RouteMapDrawer.vue'
import { formatHttpStatusTooltip } from '@/utils/httpStatus'
import BrandLogo from '@/components/BrandLogo.vue'

const emit = defineEmits(['openDrawer'])

const sessionStore = useSessionStore()
const projectStore = useProjectStore()
const route = useRoute()
const { t } = useI18n()

const inputMessage = ref('')
const messageContainer = ref<HTMLElement | null>(null)
const sessionCreating = ref(false)
const runtimeExpanded = ref(false)
const { width: windowWidth } = useWindowSize()
const isMobile = computed(() => windowWidth.value <= 768)

const isSidebarCollapsed = ref(isMobile.value)

watch(isMobile, (mobile) => {
  if (mobile) isSidebarCollapsed.value = true
})

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}
// 每条消息的思考内容折叠状态（默认折叠）
const thoughtExpanded = ref<Record<string, boolean>>({})
function toggleThought(msgId: string) {
  thoughtExpanded.value[msgId] = !thoughtExpanded.value[msgId]
}

// 当前选中的项目
const selectedProject = computed(() =>
  projectStore.currentProject ||
  projectStore.projects.find((p) => p.discovery_status === 'completed') ||
  null
)

// 已完成发现的项目列表
const readyProjects = computed(() =>
  projectStore.projects.filter((p) => p.discovery_status === 'completed')
)

const canSend = computed(() => {
  return !!inputMessage.value.trim() && !!selectedProject.value && !sessionStore.isStreaming && !sessionCreating.value
})

// 快速切换项目
async function selectProject(projectId: string) {
  const found = projectStore.projects.find((p) => p.id === projectId)
  if (!found) return
  projectStore.currentProject = found
  sessionStore.clearSession()
  projectStore.fetchProjectDetails(projectId)
  await sessionStore.fetchHistory(projectId)
  
  if (isMobile.value) {
    isSidebarCollapsed.value = true
  }
}

// 切换到历史会话
async function switchToHistory(session: Session) {
  if (sessionStore.currentSession?.id === session.id) return
  sessionStore.clearSession()
  sessionStore.currentSession = session
  await sessionStore.loadSession(session.id)
  
  if (isMobile.value) {
    isSidebarCollapsed.value = true
  }
  
  await nextTick()
  scrollToBottom()
}

// 删除历史会话
async function handleDeleteSession(session: Session, e: MouseEvent) {
  e.stopPropagation()
  await sessionStore.deleteSession(session.id)
}

// 创建对话 session
async function startSession(projectId: string) {
  if (sessionCreating.value) return
  sessionCreating.value = true
  try {
    await sessionStore.createSession(projectId)
    await sessionStore.fetchHistory(projectId)
  } catch (e: any) {
    ElMessage.error(
      t('chat.messages.createSessionFailed', {
        reason: e.message || t('common.unknown'),
      }),
    )
  } finally {
    sessionCreating.value = false
  }
}

// 新建对话
function handleNewChat() {
  sessionStore.clearSession()
}

// 发送消息
async function handleSend() {
  if (sessionStore.isStreaming || sessionCreating.value) return

  const text = inputMessage.value.trim()
  if (!text) return

  if (!sessionStore.currentSession) {
    const id = selectedProject.value?.id
    if (!id) {
      ElMessage.warning(t('chat.messages.selectProjectFirst'))
      return
    }
    await startSession(id)
    if (!sessionStore.currentSession) return
  }

  inputMessage.value = ''
  await sessionStore.sendMessage(text)
}

async function handleStop() {
  await sessionStore.stopCurrentTask()
}

function scrollToBottom(smooth = false) {
  if (!messageContainer.value) return
  const scroll = () => {
    if (!messageContainer.value) return
    if (smooth) {
      messageContainer.value.scrollTo({
        top: messageContainer.value.scrollHeight,
        behavior: 'smooth',
      })
    } else {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight
    }
  }
  // 双保险以应对可能的大元素渲染延迟
  requestAnimationFrame(() => {
    scroll()
    setTimeout(scroll, 50)
  })
}

onMounted(async () => {
  // 向 store 注入滚动函数
  sessionStore.registerScrollFn(async () => {
    await nextTick()
    scrollToBottom()
  })

  await projectStore.fetchProjects()
  const projectId = typeof route.query.project === 'string' ? route.query.project : null
  if (projectId) {
    await selectProject(projectId)
    return
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

// 流式输出时自动滚动（平滑）
watch(
  () => sessionStore.messages.length,
  async () => {
    await nextTick()
    scrollToBottom()
  }
)

function getProjectStatusLabel(status: string): string {
  switch (status) {
    case 'completed':
      return t('projects.status.completed')
    case 'in_progress':
      return t('projects.status.inProgress')
    case 'failed':
      return t('projects.status.failed')
    case 'pending':
      return t('projects.status.pending')
    default:
      return status
  }
}
</script>

<template>
  <div class="chat-page">
    <!-- 左侧项目面板 -->
    <div class="project-panel" :class="{ collapsed: isSidebarCollapsed }">
      <div class="project-panel-inner">
      <div class="panel-title">{{ t('chat.sidebar.projectsTitle') }}</div>

      <div v-if="readyProjects.length === 0" class="panel-empty">
        <p>{{ t('chat.sidebar.emptyProjects') }}</p>
        <el-button type="primary" size="small" @click="$router.push('/projects')">
          {{ t('chat.sidebar.goImport') }}
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
        <div class="panel-title-sm">{{ t('chat.sidebar.historyTitle') }}</div>
        <TransitionGroup name="history-list" tag="div" class="history-list-wrapper">
          <div
            v-for="s in sessionStore.historyList"
            :key="s.id"
            class="history-item"
            :class="{ active: sessionStore.currentSession?.id === s.id }"
            @click="switchToHistory(s)"
          >
            <div class="history-item-title">{{ s.title || t('chat.sidebar.untitledSession') }}</div>
            <button class="history-item-del" @click="handleDeleteSession(s, $event)" :title="t('chat.sidebar.deleteSession')">&times;</button>
          </div>
        </TransitionGroup>
      </template>

      <div class="panel-divider" v-if="projectStore.projects.filter(p => p.discovery_status !== 'completed').length > 0" />
      <div class="panel-title-sm" v-if="projectStore.projects.filter(p => p.discovery_status !== 'completed').length > 0">
        {{ t('chat.sidebar.otherProjects') }}
      </div>
      <div
        v-for="p in projectStore.projects.filter(p => p.discovery_status !== 'completed')"
        :key="p.id"
        class="project-item disabled"
        :title="t('chat.sidebar.disabledProjectHint', { status: getProjectStatusLabel(p.discovery_status) })"
      >
        <div class="project-item-name">{{ p.name }}</div>
        <el-tag size="small" type="info">{{ getProjectStatusLabel(p.discovery_status) }}</el-tag>
      </div>
      </div>
    </div>

    <!-- 右侧对话区 -->
    <div class="chat-area">
      <!-- 顶栏 -->
      <div class="chat-topbar" :class="{ 'is-mobile-topbar': isMobile }">
        <!-- 移动端时，最左侧显示全局 Logo 呼出抽屉 -->
        <button v-if="isMobile" class="icon-btn global-drawer-btn" @click="emit('openDrawer')" :title="t('chat.topbar.globalMenu')">
          <BrandLogo :size="24" />
        </button>

        <!-- 原有的项目侧边栏 Toggle 按钮 -->
        <button class="icon-btn sidebar-toggle-btn" @click="toggleSidebar" :title="t('chat.topbar.toggleSidebar')" :style="isMobile ? 'margin-left: 8px;' : ''">
          <Icon :icon="isSidebarCollapsed ? 'solar:hamburger-menu-linear' : 'solar:sidebar-minimalistic-linear'" />
        </button>
        <template v-if="selectedProject">
          <span class="chat-project-name">{{ selectedProject.name }}</span>
          <span class="chat-project-url">{{ selectedProject.base_url }}</span>
        </template>
        <span v-else class="chat-hint-topbar">{{ t('chat.topbar.selectProjectHint') }}</span>
        
        <div class="topbar-actions" v-if="selectedProject">
          <RouteMapAnalyzer />
          <button
            :disabled="sessionStore.isStreaming || sessionCreating"
            @click="handleNewChat"
            class="new-chat-btn custom"
          >
            <Icon v-if="sessionCreating" icon="solar:spinner-bold-duotone" class="is-loading" />
            <Icon v-else icon="solar:chat-round-line-bold-duotone" class="btn-icon" />
            <span class="btn-text">{{ t('chat.topbar.newChat') }}</span>
          </button>
        </div>
      </div>

      <!-- 消息流 -->
      <div class="message-list" ref="messageContainer">
        <!-- 欢迎语 -->
        <div v-if="sessionStore.messages.length === 0 && !sessionStore.loading" class="welcome-screen">
          <template v-if="selectedProject">
            <div class="welcome-icon">
              <Icon icon="solar:chat-round-dots-bold-duotone" />
            </div>
            <div class="welcome-title">{{ t('chat.welcome.title', { name: selectedProject.name }) }}</div>
            <div class="welcome-desc">{{ t('chat.welcome.desc') }}</div>
          </template>
          <template v-else>
            <div class="welcome-icon">
              <Icon icon="solar:magnifer-bold-duotone" />
            </div>
            <div class="welcome-title">{{ t('chat.welcome.noProjectTitle') }}</div>
            <div class="welcome-desc">{{ t('chat.welcome.noProjectDesc') }}</div>
          </template>
        </div>

        <!-- 消息列表（含嵌入式审批面板） -->
        <template v-for="msg in sessionStore.messages" :key="msg.id">
          <!-- ===== 审批面板（confirmation消息类型）===== -->
          <div v-if="msg.role === 'confirmation' && msg.approvalBlock" class="message-item confirmation-row">
            <div class="message-avatar ai-avatar">
              <Icon icon="solar:shield-warning-bold-duotone" />
            </div>
            <div class="confirmation-bubble">
              <ConfirmPanel :block="msg.approvalBlock" />
            </div>
          </div>

          <!-- ===== 普通消息（user / assistant）===== -->
          <div
            v-else-if="msg.role !== 'system'"
            :class="['message-item', msg.role]"
          >
            <div class="message-avatar" :class="msg.role === 'assistant' ? 'ai-avatar' : ''">
              <Icon v-if="msg.role === 'user'" icon="solar:user-bold-duotone" />
              <!-- AI 头像：使用统一几何品牌 Logo -->
              <BrandLogo v-else :size="24" />
            </div>
            <div class="message-bubble">
              <div v-if="msg.thought" class="message-thought">
                <div class="thought-header" @click="toggleThought(msg.id)">
                  <el-icon v-if="sessionStore.isStreaming && !msg.content" class="is-loading"><Loading /></el-icon>
                  <el-icon v-else><Monitor /></el-icon>
                  <span>{{ t('chat.message.thoughtProcess') }}</span>
                  <el-icon class="thought-toggle" :class="{ expanded: thoughtExpanded[msg.id] }"><ArrowDown /></el-icon>
                </div>
                <div
                  class="thought-body"
                  :class="{
                    expanded: thoughtExpanded[msg.id],
                    streaming: sessionStore.isStreaming && !msg.content && !thoughtExpanded[msg.id],
                  }"
                >
                  <div class="thought-content">
                    <MarkdownRenderer :content="msg.thought" />
                  </div>
                </div>
              </div>
              <!-- HTTP 执行标签 -->
              <div
                v-if="msg.role === 'assistant' && msg.metadata?.http_calls?.length"
                class="msg-http-calls"
              >
                <el-tooltip
                  v-for="(call, ci) in msg.metadata.http_calls"
                  :key="ci"
                  :show-after="120"
                  :hide-after="0"
                  placement="top"
                  effect="dark"
                  trigger="hover"
                  popper-class="http-status-tooltip"
                  :content="formatHttpStatusTooltip(call.status_code)"
                >
                  <span
                    class="http-badge"
                    :class="{
                      'http-badge--ok': call.status_code >= 200 && call.status_code < 300,
                      'http-badge--redirect': call.status_code >= 300 && call.status_code < 400,
                      'http-badge--client-err': call.status_code >= 400 && call.status_code < 500,
                      'http-badge--server-err': call.status_code >= 500,
                      'http-badge--unknown': !call.status_code || call.status_code === 0,
                    }"
                  >{{ call.method }} {{ call.url }} <span class="http-badge-code">{{ call.status_code }}</span></span>
                </el-tooltip>
              </div>
              <div v-if="msg.content" class="message-text">
                <MarkdownRenderer :content="msg.content" />
              </div>
            </div>
          </div>
        </template>

        <!-- UI Blocks（非审批型块） -->
        <div class="ui-blocks" v-if="sessionStore.uiBlocks.filter(b => b.block_type !== 'confirm_panel').length > 0">
          <BlockRenderer
            v-for="(block, index) in sessionStore.uiBlocks.filter(b => b.block_type !== 'confirm_panel')"
            :key="index"
            :block="block"
          />
        </div>

        <!-- 加载中 -->
        <div class="loading-row" v-if="sessionStore.loading || sessionCreating">
          <div class="loading-dots">
            <span></span><span></span><span></span>
          </div>
          <span class="loading-text">{{ sessionCreating ? t('chat.loading.creatingSession') : t('chat.loading.processing') }}</span>
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
          <span class="runtime-bar-msg">{{ sessionStore.progressMessage || t('chat.runtime.processingHint') }}{{ sessionStore.progressPercent > 0 ? '　' + sessionStore.progressPercent + '%' : '' }}</span>
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
            <template v-if="event.type === 'tool_completed' && event.status_code !== undefined && event.status_code !== null">
              <el-tooltip
                :show-after="120"
                :hide-after="0"
                placement="top"
                effect="dark"
                trigger="hover"
                popper-class="http-status-tooltip"
                :content="formatHttpStatusTooltip(event.status_code)"
              >
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
              </el-tooltip>
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
          <div class="input-main">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              :placeholder="selectedProject ? t('chat.input.placeholder', { name: selectedProject.name }) : t('chat.input.placeholderNoProject')"
              :disabled="!selectedProject || sessionCreating"
              @keydown.enter.ctrl.prevent="handleSend"
              @keydown.enter.exact.prevent="handleSend"
              resize="none"
              class="chat-input"
            />
            <div class="input-actions">
              <el-button
                class="send-icon-btn"
                type="primary"
                :loading="sessionStore.loading || sessionCreating"
                :disabled="!canSend"
                :title="t('chat.input.send')"
                @click="handleSend"
              >
                <Icon icon="solar:chat-round-line-bold-duotone" class="send-icon" />
              </el-button>

              <el-button
                v-if="sessionStore.isStreaming || sessionStore.stopLoading"
                class="stop-icon-btn"
                :loading="sessionStore.stopLoading"
                :disabled="!sessionStore.isStreaming"
                :title="t('chat.input.stop')"
                @click="handleStop"
              >
                <Icon icon="solar:shield-warning-bold-duotone" class="stop-icon" />
              </el-button>
            </div>
          </div>
          <div class="input-toolbar" v-if="!isMobile">
            <span class="input-hint">{{ t('chat.input.hint') }}</span>
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
  overflow-y: hidden;
  overflow-x: hidden;
  transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.project-panel.collapsed {
  width: 0;
  opacity: 0;
  border-right-color: transparent;
}

.project-panel-inner {
  width: 260px;
  height: 100%;
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

/* ============ 历史列表过渡动画 ============ */
.history-list-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
}
.history-list-enter-active,
.history-list-leave-active {
  transition: all 0.4s cubic-bezier(0.25, 1, 0.5, 1);
}
.history-list-enter-from {
  opacity: 0;
  transform: translateY(-15px) scale(0.98);
}
.history-list-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}
.history-list-leave-active {
  position: absolute;
  width: calc(100% - 16px);
}
.history-list-move {
  transition: transform 0.4s cubic-bezier(0.25, 1, 0.5, 1);
}

/* ============ 运行时进度条 ============ */
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
  font-family: var(--font-mono);
  letter-spacing: 0.5px;
  cursor: help;
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

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
  flex-shrink: 0;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #0f0f0f;
  color: #fff;
  border: 1px solid #0f0f0f;
  padding: 10px 18px;
  border-radius: 0;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  margin-left: auto;
  flex-shrink: 0;
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.2s, box-shadow 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.new-chat-btn.custom:hover {
  background: #2a2a2a;
  transform: scale(1.02);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.new-chat-btn.custom:active {
  transform: scale(0.97);
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.new-chat-btn.custom:disabled {
  background: #a3a3a3;
  border-color: #a3a3a3;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
.new-chat-btn.custom .btn-icon {
  font-size: 18px;
}
.new-chat-btn.custom .is-loading {
  font-size: 18px;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.icon-btn.sidebar-toggle-btn, .icon-btn.global-drawer-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  font-size: 20px;
  color: #0f0f0f;
  cursor: pointer;
  padding: 6px;
  border-radius: 0;
  transition: background 0.15s, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  margin-right: 4px;
}
.icon-btn.sidebar-toggle-btn:hover, .icon-btn.global-drawer-btn:hover {
  background: #f0f0f0;
}
.icon-btn.sidebar-toggle-btn:active, .icon-btn.global-drawer-btn:active {
  transform: scale(0.92);
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
  display: flex;
  flex-direction: column;
  align-items: center;
}

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
  flex-direction: row-reverse;
}

/* 审批面板行 */
.confirmation-row {
  padding: 12px 0;
}
.confirmation-bubble {
  flex: 1;
  max-width: 680px;
}

.message-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  border-radius: 0;
}

.message-item.user .message-avatar {
  background: #0f0f0f;
  color: #ffffff;
}

/* AI 头像：搭配几何极简 Logo 的素雅纯白背景与投影 */
.ai-avatar {
  background: #ffffff;
  color: #171717;
  border: 1px solid #e5e5e5;
  box-shadow: 0 4px 12px rgba(0,0,0,0.04);
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

:global(.http-status-tooltip) {
  max-width: 360px;
  white-space: pre-line;
  line-height: 1.6;
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
  font-family: var(--font-mono);
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

/* 思考过程样式 */
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

.thought-body {
  display: grid;
  grid-template-rows: 0fr;
  opacity: 0;
  transition: grid-template-rows 0.35s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1), padding 0.3s;
  padding: 0 14px;
}
.thought-body.expanded,
.thought-body.streaming {
  grid-template-rows: 1fr;
  opacity: 1;
  padding: 0 14px 10px;
}

.thought-content {
  line-height: 1.6;
  overflow: hidden;
  font-size: 13px !important;
  color: #8c8c8c !important;
}

.thought-body.streaming .thought-content {
  max-height: calc(1.6em * 5);
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 2px;
}

.thought-body.expanded .thought-content {
  max-height: none;
  overflow: visible;
}
.thought-content :deep(.markdown-renderer),
.thought-content :deep(.rendered-content),
.thought-content :deep(p),
.thought-content :deep(li),
.thought-content :deep(span),
.thought-content :deep(strong),
.thought-content :deep(em),
.thought-content :deep(a),
.thought-content :deep(h1),
.thought-content :deep(h2),
.thought-content :deep(h3),
.thought-content :deep(h4),
.thought-content :deep(h5),
.thought-content :deep(h6),
.thought-content :deep(th),
.thought-content :deep(td) {
  color: #8c8c8c !important;
  font-size: 13px !important;
}

.thought-content :deep(code) {
  color: #6b6b6b !important;
  font-size: 12px !important;
  background-color: rgba(15, 23, 42, 0.04) !important;
}

.inline-events {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.inline-event-chip {
  display: inline-block;
  font-size: 11px;
  font-family: var(--font-mono);
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

/* Loading */
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

/* ============ 底部输入区 ============ */
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
  max-width: 1120px;
  border-radius: 0;
  border: 1px solid var(--border-color-light, #e5e5e5);
  background: #ffffff;
  box-shadow: 0 4px 20px rgba(0,0,0,0.04);
  overflow: hidden;
  transition: box-shadow 0.35s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}

.input-main {
  display: flex;
  align-items: stretch;
  width: 100%;
}

.chat-input {
  flex: 1;
  min-width: 0;
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
  overflow-y: auto !important;
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 10px 16px;
  background: #fdfdfd;
  border-top: 1px solid var(--border-color-light, #e5e5e5);
}

.input-hint {
  font-size: 12px;
  color: #a3a3a3;
}

.input-actions {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px;
  border-left: 1px solid var(--border-color-light, #e5e5e5);
  background: #fdfdfd;
}

.send-icon-btn,
.stop-icon-btn {
  width: 36px;
  height: 36px;
  min-width: 36px;
  padding: 0;
  border-radius: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.send-icon,
.stop-icon {
  font-size: 18px;
}

.stop-icon-btn {
  color: #b42318;
  border-color: #fecdca;
  background: #fef3f2;
}

.stop-icon-btn:hover,
.stop-icon-btn:focus {
  color: #912018;
  border-color: #fda29b;
  background: #fee4e2;
}

/* ============ 移动端响应式布局适配 ============ */
@media (max-width: 768px) {
  .project-panel {
    position: absolute;
    left: 0;
    top: 64px; /* 顶栏高度 */
    height: calc(100% - 64px);
    z-index: 20;
    box-shadow: 4px 0 20px rgba(0,0,0,0.08); /* 给覆盖在上面的面板加上阴影 */
  }

  .message-item {
    gap: 8px; /* 消息项内部元素间距缩小 */
    padding: 16px 0;
  }

  .message-list {
    padding: 0 16px 16px;
  }

  .input-area {
    padding: 12px 16px 16px;
  }

  .input-actions {
    padding: 10px;
    gap: 6px;
  }

  .send-icon-btn,
  .stop-icon-btn {
    width: 34px;
    height: 34px;
    min-width: 34px;
  }

  .send-icon,
  .stop-icon {
    font-size: 16px;
  }

  .chat-padding-mobile {
    margin-left: 0 !important;
  }
  
  .chat-topbar {
    padding: 0 10px;
    gap: 6px;
  }

  .topbar-actions {
    gap: 4px;
  }
  
  /* 移动端：路由按钮与新建对话按钮统一为纯图标方块 */
  .new-chat-btn.custom .btn-text {
    display: none;
  }
  .new-chat-btn.custom {
    background: transparent;
    color: #0f0f0f;
    border: none;
    padding: 0;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: none;
    margin-left: 0;
  }
  .new-chat-btn.custom:hover {
    background: #f0f0f0;
    box-shadow: none;
    transform: none;
  }
  .new-chat-btn.custom:disabled {
    background: transparent;
    color: #c0c0c0;
  }

  .topbar-actions :deep(.custom-analyzer-btn) {
    background: transparent !important;
    color: #0f0f0f !important;
    border: none !important;
    padding: 0 !important;
    width: 36px !important;
    height: 36px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: none !important;
  }
  .topbar-actions :deep(.custom-analyzer-btn:hover) {
    background: #f0f0f0 !important;
  }

  .chat-project-name {
    font-size: 14px;
  }
  .chat-project-url {
    display: none;
  }
}
</style>
