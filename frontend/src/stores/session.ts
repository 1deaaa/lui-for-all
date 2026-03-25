import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import type { Session, Message, TaskRun, UIBlock, SSEEvent } from '@/vite-env.d'

export const useSessionStore = defineStore('session', () => {
  // 状态
  const currentSession = ref<Session | null>(null)
  const messages = ref<Message[]>([])
  const currentTaskRun = ref<TaskRun | null>(null)
  const uiBlocks = ref<UIBlock[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const eventSource = ref<EventSource | null>(null)

  // 计算属性
  const messageCount = computed(() => messages.value.length)

  // 创建新会话
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
      return currentSession.value
    } catch (e: any) {
      error.value = e.message || '创建会话失败'
      console.error('创建会话失败:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  // 发送消息
  async function sendMessage(content: string) {
    if (!currentSession.value) {
      error.value = '没有活动会话'
      return
    }

    // 添加用户消息到列表
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

      // 更新任务运行信息
      currentTaskRun.value = {
        id: response.data.task_run_id,
        session_id: currentSession.value.id,
        project_id: currentSession.value.project_id,
        user_message: content,
        status: response.data.status,
        trace_id: '',
        created_at: new Date().toISOString(),
      }

      // 启动 SSE 流
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

  // 启动 SSE 事件流
  function startEventStream(taskRunId: string) {
    if (eventSource.value) {
      eventSource.value.close()
    }

    const url = `/api/sessions/${currentSession.value?.id}/events/stream?task_run_id=${taskRunId}`
    eventSource.value = new EventSource(url)

    eventSource.value.onmessage = (event) => {
      try {
        const data: SSEEvent = JSON.parse(event.data)
        handleSSEEvent(data)
      } catch (e) {
        console.error('解析 SSE 事件失败:', e)
      }
    }

    eventSource.value.onerror = (e) => {
      console.error('SSE 连接错误:', e)
      if (eventSource.value) {
        eventSource.value.close()
        eventSource.value = null
      }
    }
  }

  // 处理 SSE 事件
  function handleSSEEvent(event: SSEEvent) {
    switch (event.event) {
      case 'task_completed':
        // 添加助手消息
        if (event.summary) {
          messages.value.push({
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content: event.summary,
            task_run_id: event.task_run_id,
            created_at: new Date().toISOString(),
          })
        }
        closeEventStream()
        break

      case 'ui_block_emitted':
        // 添加 UI Block
        if (event.block_data) {
          uiBlocks.value.push(event.block_data as UIBlock)
        }
        break

      case 'error':
        error.value = event.error_message || '发生未知错误'
        closeEventStream()
        break

      default:
        // 其他事件类型可以在这里处理
        console.log('收到 SSE 事件:', event)
    }
  }

  // 关闭事件流
  function closeEventStream() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
  }

  // 获取消息列表
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

  // 清空会话
  function clearSession() {
    closeEventStream()
    currentSession.value = null
    messages.value = []
    currentTaskRun.value = null
    uiBlocks.value = []
    error.value = null
  }

  return {
    // 状态
    currentSession,
    messages,
    currentTaskRun,
    uiBlocks,
    loading,
    error,
    // 计算属性
    messageCount,
    // 方法
    createSession,
    sendMessage,
    fetchMessages,
    clearSession,
    startEventStream,
    closeEventStream,
  }
})
