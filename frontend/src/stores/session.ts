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
  const streamingMessageId = ref<string | null>(null)  // 正文消息 ID
  const streamingThoughtId = ref<string | null>(null)   // 推理消息 ID

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

  function startEventStream(taskRunId: string, resumeOpts?: { resumeWriteId: string, resumeAction: string }) {
    if (eventSource.value) {
      eventSource.value.close()
    }

    let url = `/api/sessions/${currentSession.value?.id}/events/stream?task_run_id=${taskRunId}`
    if (resumeOpts) {
      url += `&resume_write_id=${resumeOpts.resumeWriteId}&resume_action=${resumeOpts.resumeAction}`
    }
    
    eventSource.value = new EventSource(url)
    isStreaming.value = true
    progressPercent.value = 0
    progressMessage.value = 'AI 已接收请求，正在启动执行链路'
    runtimeEvents.value = []
    // 重置流式消息 ID
    streamingMessageId.value = null
    streamingThoughtId.value = null

    const register = (eventName: string) => {
      eventSource.value?.addEventListener(eventName, (rawEvent) => {
        const event = rawEvent as MessageEvent
        // Native SSE connection error gives no .data
        if (event.data === undefined || event.data === null) return
        
        // If the backend literally sent `data: undefined` for some reason
        if (event.data === 'undefined') {
          console.warn(`[Diagnostics] Received exact string 'undefined' for event ${eventName}. rawEvent:`, rawEvent)
          return
        }

        try {
          const data = JSON.parse(event.data)
          handleSSEEvent({ event: eventName, ...data })
        } catch (e) {
          console.error(`解析 SSE 事件失败 [${eventName}]: raw data was:`, event.data, e)
        }
      })
    }

    eventSource.value.onmessage = (event) => {
      if (event.data === undefined || event.data === null) return
      if (event.data === 'undefined') return
      
      try {
        const data: SSEEvent = JSON.parse(event.data)
        handleSSEEvent(data)
      } catch (e) {
        console.error('解析 SSE 事件失败:', event.data, e)
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
      'token_emitted',
      'thought_emitted',
      'approval_required',
      'write_approval_required',
      'agentic_iteration',
      'task_completed',
      'error',
    ].forEach(register)

    eventSource.value.onerror = (e) => {
      console.error('SSE 连接错误:', e)
      
      // 检查是否是因为审批中断导致的正常关闭
      const isExpectedPause = uiBlocks.value.some(b => b.block_type === 'confirm_panel')
      
      if (!isExpectedPause && !error.value) {
        error.value = 'SSE 连接中断，请检查后端服务'
      }

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
        streamingMessageId.value = null
        break

      case 'token_emitted':
        // 正文内容，使用独立的 streamingMessageId
        if (!streamingMessageId.value) {
          const newId = `assistant-${Date.now()}`
          messages.value.push({
            id: newId,
            role: 'assistant',
            content: event.token || '',
            task_run_id: event.task_run_id,
            created_at: new Date().toISOString(),
          })
          streamingMessageId.value = newId
        } else {
          // 用 findIndex + splice 替换触发 Vue 响应式
          const idx = messages.value.findIndex((m) => m.id === streamingMessageId.value)
          if (idx !== -1) {
            const old = messages.value[idx]
            messages.value.splice(idx, 1, { ...old, content: old.content + (event.token || '') })
          }
        }
        break

      case 'thought_emitted':
        // 推理内容，使用独立的 streamingThoughtId
        if (!streamingThoughtId.value) {
          const newId = `assistant-thought-${Date.now()}`
          messages.value.push({
            id: newId,
            role: 'assistant',
            content: '',
            thought: event.token || '',
            task_run_id: event.task_run_id,
            created_at: new Date().toISOString(),
          })
          streamingThoughtId.value = newId
        } else {
          // 用 findIndex + splice 替换触发 Vue 响应式
          const idx = messages.value.findIndex((m) => m.id === streamingThoughtId.value)
          if (idx !== -1) {
            const old = messages.value[idx]
            messages.value.splice(idx, 1, { ...old, thought: (old.thought || '') + (event.token || '') })
          }
        }
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
          if (streamingMessageId.value) {
            // 已有流式正文消息：不覆盖，保留已输出的内容（避免重复）
            // 仅将 summary_text 存到 currentTaskRun，不再 push 新消息
          } else if (!streamingMessageId.value && !streamingThoughtId.value) {
            // 没有任何流式输出时，才 push、为常规非流式路径准备
            messages.value.push({
              id: `assistant-${Date.now()}`,
              role: 'assistant',
              content: event.summary,
              task_run_id: event.task_run_id,
              created_at: new Date().toISOString(),
            })
          }
        }
        currentTaskRun.value = currentTaskRun.value
          ? { ...currentTaskRun.value, status: 'completed', summary_text: event.summary }
          : currentTaskRun.value
        progressPercent.value = 100
        progressMessage.value = '任务已完成'
        isStreaming.value = false
        streamingMessageId.value = null
        streamingThoughtId.value = null
        closeEventStream()
        break

      case 'ui_block_emitted':
        if (event.block_data) {
          uiBlocks.value.push(event.block_data as UIBlock)
        }
        break

      case 'write_approval_required':
        uiBlocks.value.push({
          block_type: 'confirm_panel',
          approval_id: (event as any).write_id,
          title: `需要审核写入操作: ${(event as any).method} ${(event as any).path}`,
          description: (event as any).reasoning || '此操作涉及数据修改，请人工审核。',
          risk_level: (event as any).safety_level === 'critical' ? 'critical' : 'warning',
          timeout_seconds: 300,
          route_id: (event as any).route_id,
          parameters: (event as any).parameters
        })
        break

      case 'agentic_iteration':
        pushRuntimeEvent({
          id: `iteration-${Date.now()}-${Math.random()}`,
          type: 'progress',
          title: `开始第 ${(event as any).iteration} 轮迭代`,
          detail: 'AI 正在自主规划与执行下一步行动...',
          status: 'running',
          created_at: new Date().toISOString()
        })
        break

      case 'approval_required':
        uiBlocks.value.push({
          block_type: 'confirm_panel',
          approval_id: (event as any).approval_id,
          title: (event as any).title || '操作需要确认',
          description: (event as any).description || '此操作涉及敏感权限，请核实后批准。',
          risk_level: (event as any).risk_level || 'warning',
          timeout_seconds: (event as any).timeout_seconds || 300
        })
        break

      case 'error':
        if ((event as any).error_code === 'APPROVAL_REQUIRED') {
            // 已通过 ui_block 处理，此处不再设为全局错误
            break
        }
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
