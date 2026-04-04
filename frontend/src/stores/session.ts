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
  const historyList = ref<Session[]>([])
  const historyLoading = ref(false)
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
  const runtimeEventsByTaskRun = ref<Record<string, RuntimeEventItem[]>>({})
  const streamingMessageId = ref<string | null>(null)  // 正文消息 ID
  const streamingThoughtId = ref<string | null>(null)   // 推理消息 ID
  const currentTaskRunId = ref<string | null>(null)
  // 当前任务流式期间收集的 HTTP 调用记录
  const pendingHttpCalls = ref<NonNullable<import('@/vite-env.d').Message['metadata']>['http_calls']>( [])

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
        updated_at: new Date().toISOString(),
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

      // 若当前会话还没有标题，取本条消息前 20 字同步到 historyList
      if (currentSession.value && !currentSession.value.title) {
        const autoTitle = content.slice(0, 20)
        currentSession.value = { ...currentSession.value, title: autoTitle }
        const idx = historyList.value.findIndex(s => s.id === currentSession.value!.id)
        if (idx !== -1) {
          historyList.value.splice(idx, 1, { ...historyList.value[idx], title: autoTitle })
        }
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
    if (currentTaskRunId.value) {
      const key = currentTaskRunId.value
      if (!runtimeEventsByTaskRun.value[key]) {
        runtimeEventsByTaskRun.value[key] = []
      }
      runtimeEventsByTaskRun.value[key].push(event)
    }
  }

  function startEventStream(taskRunId: string, resumeOpts?: { resumeWriteId?: string, resumeBatchId?: string, resumeAction: string, approvedIds?: string[] }) {
    if (eventSource.value) {
      eventSource.value.close()
    }

    let url = `/api/sessions/${currentSession.value?.id}/events/stream?task_run_id=${taskRunId}`
    if (resumeOpts) {
      url += `&resume_write_id=${resumeOpts.resumeWriteId || ''}&resume_action=${resumeOpts.resumeAction}`
      if (resumeOpts.resumeBatchId) {
        url += `&resume_batch_id=${resumeOpts.resumeBatchId}`
      }
      if (resumeOpts.approvedIds) {
        url += `&resume_approved_ids=${resumeOpts.approvedIds.join(',')}`
      }
    }
    
    eventSource.value = new EventSource(url)
    isStreaming.value = true
    progressPercent.value = 0
    progressMessage.value = resumeOpts ? 'AI 正在执行已批准操作...' : 'AI 已接收请求，正在启动执行链路'
    runtimeEvents.value = []
    if (!resumeOpts) {
      // 全新任务：清空所有状态
      pendingHttpCalls.value = []
      uiBlocks.value = []
      streamingMessageId.value = null
      streamingThoughtId.value = null
    } else {
      // resume 模式：保留审批面板（uiBlocks）和已有流式消息索引
      // 不重置 streamingMessageId，让恢复后的正文 token 继续追加到已有消息中
      // 不清除审批面板，以保证就地批准标记不消失
    }
    currentTaskRunId.value = taskRunId

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
      'approval_pending',
      'task_completed',
      'error',
    ].forEach(register)

    eventSource.value.onerror = (e) => {
      // 如果 isStreaming 已经是 false，说明已通过 approval_pending 事件正常处理，不当作错误
      if (!isStreaming.value) return

      console.error('SSE 连接错误:', e)

      // 检查是否是因为审批中断导致的正常关闭（兜底，有 confirm_panel 时不报错）
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

      case 'tool_completed': {
        // 从 route_id 拆出 HTTP method（格式可能是 "GET /api/xxx" 或 "GET:/api/xxx" 或仅有路径）
        const routeId: string = event.route_id || ''
        let httpMethod = ''
        let httpPath = routeId
        
        if (routeId.includes(' ')) {
          const parts = routeId.split(' ')
          httpMethod = parts[0].toUpperCase()
          httpPath = parts.slice(1).join(' ')
        } else if (routeId.includes(':')) {
          const parts = routeId.split(':')
          httpMethod = parts[0].toUpperCase()
          httpPath = parts.slice(1).join(':')
        }
        const sc: number | undefined = event.status_code
        // 收集到临时列表，task_completed 时写入消息 metadata
        if (sc) {
          pendingHttpCalls.value = [
            ...(pendingHttpCalls.value || []),
            { method: httpMethod, url: httpPath, status_code: sc },
          ]
        }
        pushRuntimeEvent({
          id: `tool-done-${Date.now()}-${Math.random()}`,
          type: 'tool_completed',
          title: event.title || '工具调用完成',
          detail: event.detail,
          status: sc && sc >= 400 ? 'failed' : 'completed',
          status_code: sc,
          method: httpMethod || undefined,
          url: httpPath || undefined,
          created_at: new Date().toISOString(),
        })
        break
      }

      case 'task_completed': {
        const httpCallsSnapshot = pendingHttpCalls.value?.length ? [...pendingHttpCalls.value] : undefined
        pendingHttpCalls.value = []
        if (event.summary) {
          if (streamingMessageId.value) {
            // 已有流式正文消息：写入 http_calls metadata
            const idx = messages.value.findIndex(m => m.id === streamingMessageId.value)
            if (idx !== -1 && httpCallsSnapshot) {
              const old = messages.value[idx]
              messages.value.splice(idx, 1, { ...old, metadata: { http_calls: httpCallsSnapshot } })
            }
          } else if (!streamingThoughtId.value) {
            // 没有任何流式输出时，才 push、为常规非流式路径准备
            messages.value.push({
              id: `assistant-${Date.now()}`,
              role: 'assistant',
              content: event.summary,
              task_run_id: event.task_run_id,
              created_at: new Date().toISOString(),
              metadata: httpCallsSnapshot ? { http_calls: httpCallsSnapshot } : undefined,
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
      }

      case 'ui_block_emitted':
        if (event.block_data) {
          uiBlocks.value.push(event.block_data as UIBlock)
        }
        break

      case 'write_approval_required':
        uiBlocks.value.push({
          block_type: 'confirm_panel',
          batch_id: (event as any).batch_id,
          items: (event as any).items,
          approval_id: (event as any).write_id,
          title: `需要审核写入操作: ${(event as any).method || ''} ${(event as any).path || ''}`,
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

      case 'approval_pending':
        // 图因 interrupt 暂停，SSE 将由后端关闭
        // 前端停止 streaming 状态，但 uiBlocks（审批面板）保留
        isStreaming.value = false
        progressPercent.value = 0
        progressMessage.value = '等待审批中...'
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

  const HISTORY_CACHE_PREFIX = 'lui_history_'

  function _loadHistoryCache(projectId: string): Session[] {
    try {
      const raw = localStorage.getItem(HISTORY_CACHE_PREFIX + projectId)
      return raw ? JSON.parse(raw) : []
    } catch {
      return []
    }
  }

  function _saveHistoryCache(projectId: string, list: Session[]) {
    try {
      localStorage.setItem(HISTORY_CACHE_PREFIX + projectId, JSON.stringify(list))
    } catch {}
  }

  async function fetchHistory(projectId: string) {
    // 1. 先读本地缓存，立即展示
    const cached = _loadHistoryCache(projectId)
    if (cached.length > 0) {
      historyList.value = cached
    } else {
      historyLoading.value = true
    }

    // 2. 后台向服务器同步，差异比对后更新
    try {
      const response = await axios.get('/api/sessions/', { params: { project_id: projectId, limit: 50 } })
      const serverList: Session[] = response.data.sessions || []

      // 差异比对：id 集合或 title/updated_at 有变化才更新
      const changed =
        serverList.length !== historyList.value.length ||
        serverList.some((s, i) => {
          const c = historyList.value[i]
          return !c || c.id !== s.id || c.title !== s.title || c.updated_at !== s.updated_at
        })

      if (changed) {
        historyList.value = serverList
        _saveHistoryCache(projectId, serverList)
      }
    } catch (e: any) {
      console.error('获取历史会话失败:', e)
    } finally {
      historyLoading.value = false
    }
  }

  async function loadSession(sessionId: string) {
    closeEventStream()
    loading.value = true
    isStreaming.value = false
    try {
      const response = await axios.get(`/api/sessions/${sessionId}/messages`)
      messages.value = (response.data.messages || []).map((m: any) => ({
        ...m,
        thought: m.metadata?.thought,
      }))
      uiBlocks.value = []
      runtimeEvents.value = []
      runtimeEventsByTaskRun.value = {}
      currentTaskRunId.value = null
    } catch (e: any) {
      error.value = e.message || '加载会话失败'
    } finally {
      loading.value = false
    }
  }

  function deleteSession(sessionId: string) {
    // 乐观删除 UI
    const projectId = historyList.value.find(s => s.id === sessionId)?.project_id
      || currentSession.value?.project_id
    historyList.value = historyList.value.filter(s => s.id !== sessionId)
    if (projectId) {
      _saveHistoryCache(projectId, historyList.value)
    }
    if (currentSession.value?.id === sessionId) {
      clearSession()
    }

    // 后端异步执行删除，不阻塞用户的后续操作与本地 UI 更新
    axios.delete(`/api/sessions/${sessionId}`).catch(e => {
      console.error('异步删除会话失败:', e)
    })
  }

  async function fetchMessages(sessionId: string) {
    loading.value = true
    try {
      const response = await axios.get(`/api/sessions/${sessionId}/messages`)
      messages.value = (response.data.messages || []).map((m: any) => ({
        ...m,
        thought: m.metadata?.thought,
      }))
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
    runtimeEventsByTaskRun.value = {}
    currentTaskRunId.value = null
  }

  return {
    currentSession,
    historyList,
    historyLoading,
    messages,
    currentTaskRun,
    uiBlocks,
    loading,
    isStreaming,
    error,
    progressPercent,
    progressMessage,
    runtimeEvents,
    runtimeEventsByTaskRun,
    messageCount,
    createSession,
    sendMessage,
    fetchMessages,
    fetchHistory,
    loadSession,
    deleteSession,
    clearSession,
    startEventStream,
    closeEventStream,
  }
})
