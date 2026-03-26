import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import axios from 'axios'
import type {
  Message,
  RuntimeEventItem,
  Session,
  SSEEvent,
  TaskRun,
  UIBlock,
} from '@/vite-env.d'

export const useSessionStore = defineStore('session', () => {
  const currentSession = ref<Session | null>(null)
  const messages = ref<Message[]>([])
  const currentTaskRun = ref<TaskRun | null>(null)
  const uiBlocks = ref<UIBlock[]>([])
  const loading = ref(false)
  const isStreaming = ref(false)
  const error = ref<string | null>(null)
  const eventSource = ref<EventSource | null>(null)
  const progressPercent = ref(0)
  const progressMessage = ref('')
  const runtimeEvents = ref<RuntimeEventItem[]>([])

  const messageCount = computed(() => messages.value.length)

  async function createSession(projectId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await axios.post('/api/sessions/', {
        project_id: projectId,
      })
      currentSession.value = {
        id: response.data.session_id,
        project_id: projectId,
        status: response.data.status,
        created_at: new Date().toISOString(),
      }
      messages.value = []
      uiBlocks.value = []
      runtimeEvents.value = []
      return currentSession.value
    } catch (e: any) {
      error.value = e.message || '创建会话失败'
      console.error('创建会话失败:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function sendMessage(content: string) {
    if (!currentSession.value) {
      error.value = '没有活动会话'
      return
    }

    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMessage)

    loading.value = true
    error.value = null

    try {
      const response = await axios.post(
        `/api/sessions/${currentSession.value.id}/messages`,
        { content }
      )

      currentTaskRun.value = {
        id: response.data.task_run_id,
        session_id: currentSession.value.id,
        project_id: currentSession.value.project_id,
        user_message: content,
        status: response.data.status,
        trace_id: '',
        created_at: new Date().toISOString(),
      }

      startEventStream(response.data.task_run_id)
      return response.data
    } catch (e: any) {
      error.value = e.message || '发送消息失败'
      console.error('发送消息失败:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  function pushRuntimeEvent(event: RuntimeEventItem) {
    runtimeEvents.value.push(event)
    if (runtimeEvents.value.length > 30) {
      runtimeEvents.value.splice(0, runtimeEvents.value.length - 30)
    }
  }

  function startEventStream(taskRunId: string) {
    if (eventSource.value) {
      eventSource.value.close()
    }

    const url = `/api/sessions/${currentSession.value?.id}/events/stream?task_run_id=${taskRunId}`
    eventSource.value = new EventSource(url)
    isStreaming.value = true
    progressPercent.value = 0
    progressMessage.value = 'AI 已接收请求，正在启动执行链路'
    runtimeEvents.value = []

    const register = (eventName: string) => {
      eventSource.value?.addEventListener(eventName, (rawEvent) => {
        const event = rawEvent as MessageEvent
        try {
          const data = JSON.parse(event.data)
          handleSSEEvent({ event: eventName, ...data })
        } catch (e) {
          console.error(`解析 SSE 事件失败 [${eventName}]:`, e)
        }
      })
    }

    eventSource.value.onmessage = (event) => {
      try {
        const data: SSEEvent = JSON.parse(event.data)
        handleSSEEvent(data)
      } catch (e) {
        console.error('解析 SSE 事件失败:', e)
      }
    }

    ;[
      'session_started',
      'task_started',
      'task_progress',
      'node_completed',
      'tool_started',
      'tool_completed',
      'ui_block_emitted',
      'task_completed',
      'error',
    ].forEach(register)

    eventSource.value.onerror = (e) => {
      console.error('SSE 连接错误:', e)
      error.value = error.value || 'SSE 连接中断'
      if (eventSource.value) {
        eventSource.value.close()
        eventSource.value = null
      }
      isStreaming.value = false
    }
  }

  function handleSSEEvent(event: SSEEvent) {
    switch (event.event) {
      case 'task_started':
        currentTaskRun.value = currentTaskRun.value
          ? { ...currentTaskRun.value, status: 'running' }
          : currentTaskRun.value
        progressMessage.value = '任务开始执行'
        break

      case 'task_progress':
        progressPercent.value = Math.min(100, Math.max(0, Math.round((event.progress || 0) * 100)))
        progressMessage.value = event.message || 'AI 处理中'
        pushRuntimeEvent({
          id: `progress-${Date.now()}-${Math.random()}`,
          type: 'progress',
          title: event.node_name || '执行进度更新',
          detail: event.message,
          status: 'running',
          created_at: new Date().toISOString(),
        })
        break

      case 'node_completed':
        pushRuntimeEvent({
          id: `node-${Date.now()}-${Math.random()}`,
          type: 'node_completed',
          title: `节点完成：${event.node_name}`,
          detail: `当前整体进度 ${Math.round((event.progress || 0) * 100)}%`,
          status: 'completed',
          created_at: new Date().toISOString(),
        })
        break

      case 'tool_started':
        pushRuntimeEvent({
          id: `tool-start-${Date.now()}-${Math.random()}`,
          type: 'tool_started',
          title: event.title || '开始调用工具',
          detail: event.detail,
          status: 'running',
          created_at: new Date().toISOString(),
        })
        break

      case 'tool_completed':
        pushRuntimeEvent({
          id: `tool-done-${Date.now()}-${Math.random()}`,
          type: 'tool_completed',
          title: event.title || '工具调用完成',
          detail: event.detail,
          status: event.status_code && event.status_code >= 400 ? 'failed' : 'completed',
          created_at: new Date().toISOString(),
        })
        break

      case 'task_completed':
        if (event.summary) {
          messages.value.push({
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content: event.summary,
            task_run_id: event.task_run_id,
            created_at: new Date().toISOString(),
          })
        }
        currentTaskRun.value = currentTaskRun.value
          ? { ...currentTaskRun.value, status: 'completed', summary_text: event.summary }
          : currentTaskRun.value
        progressPercent.value = 100
        progressMessage.value = '任务已完成'
        isStreaming.value = false
        closeEventStream()
        break

      case 'ui_block_emitted':
        if (event.block_data) {
          uiBlocks.value.push(event.block_data as UIBlock)
        }
        break

      case 'error':
        error.value = event.error_message || '发生未知错误'
        currentTaskRun.value = currentTaskRun.value
          ? { ...currentTaskRun.value, status: 'failed', error: error.value || undefined }
          : currentTaskRun.value
        isStreaming.value = false
        closeEventStream()
        break

      default:
        console.log('收到 SSE 事件:', event)
    }
  }

  function closeEventStream() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
    isStreaming.value = false
  }

  async function fetchMessages(sessionId: string) {
    loading.value = true
    try {
      const response = await axios.get(`/api/sessions/${sessionId}/messages`)
      messages.value = response.data.messages || []
    } catch (e: any) {
      error.value = e.message || '获取消息失败'
      console.error('获取消息失败:', e)
    } finally {
      loading.value = false
    }
  }

  function clearSession() {
    closeEventStream()
    currentSession.value = null
    messages.value = []
    currentTaskRun.value = null
    uiBlocks.value = []
    error.value = null
    progressPercent.value = 0
    progressMessage.value = ''
    runtimeEvents.value = []
  }

  return {
    currentSession,
    messages,
    currentTaskRun,
    uiBlocks,
    loading,
    isStreaming,
    error,
    progressPercent,
    progressMessage,
    runtimeEvents,
    messageCount,
    createSession,
    sendMessage,
    fetchMessages,
    clearSession,
    startEventStream,
    closeEventStream,
  }
})
