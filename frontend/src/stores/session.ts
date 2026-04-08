import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import axios from 'axios'
import { getLocale, translate } from '@/i18n'
import type {
  ApprovalBlock,
  Message,
  RuntimeEventItem,
  Session,
  SSEEvent,
  TaskRun,
  UIBlock,
} from '@/vite-env.d'

export const useSessionStore = defineStore('session', () => {
  const t = translate

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
  const pendingHttpCalls = ref<NonNullable<import('@/vite-env.d').Message['metadata']>['http_calls']>([])
  // 滚动回调（由 ChatPage 注入）
  const _scrollToBottomFn = ref<(() => void) | null>(null)

  const messageCount = computed(() => messages.value.length)

  /** 注册滚动到底部函数（由 ChatPage 在 onMounted 时注入） */
  function registerScrollFn(fn: () => void) {
    _scrollToBottomFn.value = fn
  }

  function _scrollToBottom() {
    _scrollToBottomFn.value?.()
  }

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
      error.value = e.message || t('sessionStore.createSessionFailed')
      console.error('创建会话失败:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function sendMessage(content: string) {
    if (!currentSession.value) {
      error.value = t('sessionStore.noActiveSession')
      return
    }

    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMessage)

    // 立即滚动到底部（显示用户消息）
    _scrollToBottom()

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
      error.value = e.message || t('sessionStore.sendMessageFailed')
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

    const params = new URLSearchParams({
      task_run_id: taskRunId,
      locale: getLocale(),
    })

    if (resumeOpts) {
      params.set('resume_write_id', resumeOpts.resumeWriteId || '')
      params.set('resume_action', resumeOpts.resumeAction)
      if (resumeOpts.resumeBatchId) {
        params.set('resume_batch_id', resumeOpts.resumeBatchId)
      }
      if (resumeOpts.approvedIds) {
        params.set('resume_approved_ids', resumeOpts.approvedIds.join(','))
      }
    }

    const url = `/api/sessions/${currentSession.value?.id}/events/stream?${params.toString()}`
    
    eventSource.value = new EventSource(url)
    isStreaming.value = true
    progressPercent.value = 0
    progressMessage.value = resumeOpts ? t('sessionStore.approvedActionRunning') : t('sessionStore.requestAccepted')
    runtimeEvents.value = []
    if (!resumeOpts) {
      // 全新任务：清空临时状态（uiBlocks不清，审批记录已嵌入messages）
      pendingHttpCalls.value = []
      uiBlocks.value = []
      streamingMessageId.value = null
      streamingThoughtId.value = null
    }
    // resume 模式：保留审批面板和已有流式消息索引
    currentTaskRunId.value = taskRunId

    const register = (eventName: string) => {
      eventSource.value?.addEventListener(eventName, (rawEvent) => {
        const event = rawEvent as MessageEvent
        if (event.data === undefined || event.data === null) return
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

      // 检查是否是因为审批中断导致的正常关闭
      const isExpectedPause = messages.value.some(m =>
        m.role === 'confirmation' && !m.approvalBlock?.resolved_action
      )

      if (!isExpectedPause && !error.value) {
        error.value = t('sessionStore.sseDisconnected')
      }

      if (eventSource.value) {
        eventSource.value.close()
        eventSource.value = null
      }
      isStreaming.value = false
    }
  }

  /** 在 messages 中找到对应 confirmation 消息并标记为已决策 */
  function markApprovalResolved(batchId: string | undefined, approvalId: string | undefined, action: 'approved' | 'rejected') {
    const idx = messages.value.findIndex(m =>
      m.role === 'confirmation' && (
        (batchId && m.approvalBlock?.batch_id === batchId) ||
        (approvalId && m.approvalBlock?.approval_id === approvalId)
      )
    )
    if (idx !== -1) {
      const old = messages.value[idx]
      messages.value.splice(idx, 1, {
        ...old,
        approvalBlock: { ...old.approvalBlock!, resolved_action: action }
      })
    }
  }

  function handleSSEEvent(event: SSEEvent) {
    switch (event.event) {
      case 'task_started':
        currentTaskRun.value = currentTaskRun.value
          ? { ...currentTaskRun.value, status: 'running' }
          : currentTaskRun.value
        progressMessage.value = t('sessionStore.taskStarted')
        streamingMessageId.value = null
        break

      case 'token_emitted':
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
          const idx = messages.value.findIndex((m) => m.id === streamingMessageId.value)
          if (idx !== -1) {
            const old = messages.value[idx]
            messages.value.splice(idx, 1, { ...old, content: old.content + (event.token || '') })
          }
        }
        _scrollToBottom()
        break

      case 'thought_emitted':
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
          const idx = messages.value.findIndex((m) => m.id === streamingThoughtId.value)
          if (idx !== -1) {
            const old = messages.value[idx]
            messages.value.splice(idx, 1, { ...old, thought: (old.thought || '') + (event.token || '') })
          }
        }
        _scrollToBottom()
        break

      case 'task_progress':
        progressPercent.value = Math.min(100, Math.max(0, Math.round((event.progress || 0) * 100)))
        progressMessage.value = event.message || t('sessionStore.progressDefault')
        pushRuntimeEvent({
          id: `progress-${Date.now()}-${Math.random()}`,
          type: 'progress',
          title: event.node_name || t('sessionStore.eventTitleUnknown'),
          detail: event.message,
          status: 'running',
          created_at: new Date().toISOString(),
        })
        break

      case 'node_completed':
        pushRuntimeEvent({
          id: `node-${Date.now()}-${Math.random()}`,
          type: 'node_completed',
          title: t('sessionStore.progressNodeDone', { node: event.node_name || '-' }),
          detail: t('sessionStore.progressOverall', { progress: Math.round((event.progress || 0) * 100) }),
          status: 'completed',
          created_at: new Date().toISOString(),
        })
        break

      case 'tool_started':
        pushRuntimeEvent({
          id: `tool-start-${Date.now()}-${Math.random()}`,
          type: 'tool_started',
          title: event.title || t('sessionStore.toolStarted'),
          detail: event.detail,
          status: 'running',
          created_at: new Date().toISOString(),
        })
        break

      case 'tool_completed': {
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
        if (sc) {
          pendingHttpCalls.value = [
            ...(pendingHttpCalls.value || []),
            { method: httpMethod, url: httpPath, status_code: sc },
          ]
        }
        pushRuntimeEvent({
          id: `tool-done-${Date.now()}-${Math.random()}`,
          type: 'tool_completed',
          title: event.title || t('sessionStore.toolCompleted'),
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
          let summaryRendered = false
          if (streamingMessageId.value) {
            const idx = messages.value.findIndex(m => m.id === streamingMessageId.value)
            if (idx !== -1) {
              const old = messages.value[idx]
              messages.value.splice(idx, 1, {
                ...old,
                content: old.content || event.summary,
                metadata: httpCallsSnapshot ? { http_calls: httpCallsSnapshot } : old.metadata,
              })
              summaryRendered = true
            }
          }

          if (!summaryRendered) {
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
        progressMessage.value = t('sessionStore.taskCompleted')
        isStreaming.value = false
        streamingMessageId.value = null
        streamingThoughtId.value = null
        closeEventStream()
        // 任务完成后滚动到最底部
        _scrollToBottom()
        break
      }

      case 'ui_block_emitted':
        if (event.block_data) {
          uiBlocks.value.push(event.block_data as UIBlock)
        }
        break

      case 'write_approval_required': {
        // 将审批面板嵌入消息流，固定在当前位置
        const approvalBlock: ApprovalBlock = {
          block_type: 'confirm_panel',
          batch_id: (event as any).batch_id,
          items: (event as any).items,
          approval_id: (event as any).write_id,
          title:
            (event as any).title ||
            t('confirmPanel.messages.defaultTitle', {
              method: (event as any).method || '',
              path: (event as any).path || '',
            }),
          description: (event as any).reasoning || t('confirmPanel.messages.defaultDescription'),
          risk_level: (event as any).safety_level === 'critical' ? 'critical' : 'warning',
          route_id: (event as any).route_id,
          parameters: (event as any).parameters,
        }
        const msgId = `confirmation-${(event as any).batch_id || Date.now()}`
        // 幂等：避免 resume 时重复插入同一个审批面板
        const already = messages.value.find(m => m.id === msgId)
        if (!already) {
          messages.value.push({
            id: msgId,
            role: 'confirmation',
            content: '',
            task_run_id: event.task_run_id,
            created_at: new Date().toISOString(),
            approvalBlock,
          })
          _scrollToBottom()
        }
        break
      }

      case 'agentic_iteration':
        pushRuntimeEvent({
          id: `iteration-${Date.now()}-${Math.random()}`,
          type: 'progress',
          title: t('sessionStore.iterationStarted', { iteration: (event as any).iteration }),
          detail: t('sessionStore.iterationDetail'),
          status: 'running',
          created_at: new Date().toISOString()
        })
        break

      case 'approval_required':
        // 旧版审批面板（兼容）
        messages.value.push({
          id: `confirmation-legacy-${Date.now()}`,
          role: 'confirmation',
          content: '',
          task_run_id: event.task_run_id,
          created_at: new Date().toISOString(),
          approvalBlock: {
            block_type: 'confirm_panel',
            approval_id: (event as any).approval_id,
            title: (event as any).title || t('sessionStore.approvalTitle'),
            description: (event as any).description || t('sessionStore.approvalDescription'),
            risk_level: (event as any).risk_level || 'warning',
          }
        })
        _scrollToBottom()
        break

      case 'error':
        if ((event as any).error_code === 'APPROVAL_REQUIRED') {
            break
        }
        error.value = event.error_message || t('sessionStore.taskError')
        currentTaskRun.value = currentTaskRun.value
          ? { ...currentTaskRun.value, status: 'failed', error: error.value || undefined }
          : currentTaskRun.value
        isStreaming.value = false
        closeEventStream()
        break

      case 'approval_pending':
        // 图因 interrupt 暂停，SSE 将由后端关闭
        isStreaming.value = false
        progressPercent.value = 0
        progressMessage.value = t('sessionStore.waitingApproval')
        closeEventStream()
        _scrollToBottom()
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
    const cached = _loadHistoryCache(projectId)
    if (cached.length > 0) {
      historyList.value = cached
    } else {
      historyLoading.value = true
    }

    try {
      const response = await axios.get('/api/sessions/', { params: { project_id: projectId, limit: 50 } })
      const serverList: Session[] = response.data.sessions || []

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
      messages.value = (response.data.messages || []).flatMap((m: any) => {
        const result: Message[] = []
        // 从 metadata 恢复审批面板（持久化的 confirmation 消息）
        if (m.role === 'system' && m.metadata?.approval_block) {
          result.push({
            id: m.id,
            role: 'confirmation',
            content: '',
            task_run_id: m.task_run_id,
            created_at: m.created_at,
            approvalBlock: m.metadata.approval_block as ApprovalBlock,
          })
        } else {
          result.push({
            ...m,
            thought: m.metadata?.thought,
          })
        }
        return result
      })
      uiBlocks.value = []
      runtimeEvents.value = []
      runtimeEventsByTaskRun.value = {}
      currentTaskRunId.value = null
    } catch (e: any) {
      error.value = e.message || t('sessionStore.loadingSessionFailed')
    } finally {
      loading.value = false
    }
  }

  function deleteSession(sessionId: string) {
    const projectId = historyList.value.find(s => s.id === sessionId)?.project_id
      || currentSession.value?.project_id
    historyList.value = historyList.value.filter(s => s.id !== sessionId)
    if (projectId) {
      _saveHistoryCache(projectId, historyList.value)
    }
    if (currentSession.value?.id === sessionId) {
      clearSession()
    }

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
      error.value = e.message || t('sessionStore.fetchMessagesFailed')
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
    markApprovalResolved,
    registerScrollFn,
  }
})
