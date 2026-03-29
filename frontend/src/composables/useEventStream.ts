/**
 * SSE 事件流解析 Composable
 * 基于 AG-UI 标准同步承接后端 SSE 流转
 */

import { ref, onUnmounted } from 'vue'
import type { UIBlock } from '@/vite-env.d'

// SSE 事件类型
export interface SSEEvent {
  event: string
  data: any
  id?: string
  retry?: number
}

// 事件处理器类型
export type EventHandler = (data: any) => void

/**
 * SSE 事件流 Composable
 */
export function useEventStream() {
  // 连接状态
  const isConnected = ref(false)
  const error = ref<string | null>(null)
  
  // 事件源实例
  let eventSource: EventSource | null = null
  
  // 事件处理器映射
  const handlers: Map<string, Set<EventHandler>> = new Map()
  
  // 接收到的 UI Blocks
  const uiBlocks = ref<UIBlock[]>([])
  
  // 当前会话状态
  const sessionStatus = ref<'idle' | 'running' | 'completed' | 'error'>('idle')
  
  // 进度信息
  const progress = ref<{
    current: number
    total: number
    message: string
  } | null>(null)

  /**
   * 解析 SSE 消息
   */
  function parseMessage(event: MessageEvent): SSEEvent {
    const eventType = event.type || 'message'
    let data: any
    
    // Guard against undefined or null data (e.g. from native browser error events)
    if (event.data === undefined || event.data === null || event.data === 'undefined') {
      return {
        event: eventType,
        data: null,
        id: event.lastEventId,
      }
    }

    try {
      data = JSON.parse(event.data)
    } catch {
      data = event.data
    }
    
    return {
      event: eventType,
      data,
      id: event.lastEventId,
    }
  }

  /**
   * 处理 SSE 事件
   */
  function handleEvent(event: MessageEvent | Event) {
    // 忽略没有 data 属性的标准连接错误事件
    if (!('data' in event) || event.data === undefined) {
        return;
    }

    const sseEvent = parseMessage(event as MessageEvent)
    
    // 更新连接状态
    isConnected.value = true
    
    // 调用注册的处理器
    const eventHandlers = handlers.get(sseEvent.event)
    if (eventHandlers) {
      eventHandlers.forEach(handler => {
        try {
          handler(sseEvent.data)
        } catch (e) {
          console.error(`事件处理器错误 [${sseEvent.event}]:`, e)
        }
      })
    }
    
    // 默认处理
    switch (sseEvent.event) {
      case 'session_started':
        sessionStatus.value = 'running'
        break
        
      case 'task_progress':
        progress.value = {
          current: sseEvent.data.current || 0,
          total: sseEvent.data.total || 100,
          message: sseEvent.data.message || '',
        }
        break
        
      case 'ui_block_emitted':
        if (sseEvent.data.block) {
          uiBlocks.value.push(sseEvent.data.block)
        }
        break
        
      case 'task_completed':
        sessionStatus.value = 'completed'
        progress.value = null
        disconnect() // 任务完成，主动关闭连接，避免 EventSource 自动重连
        break
        
      case 'error':
        sessionStatus.value = 'error'
        error.value = sseEvent.data.message || '未知错误'
        disconnect() // 发生后端明确抛出的错误，主动关闭连接
        break
    }
  }

  /**
   * 连接到 SSE 端点
   */
  function connect(url: string) {
    // 断开现有连接
    disconnect()
    
    // 重置状态
    error.value = null
    uiBlocks.value = []
    sessionStatus.value = 'idle'
    progress.value = null
    
    // 创建 EventSource
    eventSource = new EventSource(url)
    
    // 连接成功
    eventSource.onopen = () => {
      isConnected.value = true
      console.log('SSE 连接已建立:', url)
    }
    
    // 接收消息
    eventSource.onmessage = handleEvent
    
    // 自定义事件类型
    const eventTypes = [
      'session_started',
      'task_progress',
      'ui_block_emitted',
      'approval_required',
      'task_completed',
      'error',
    ]
    
    eventTypes.forEach(type => {
      eventSource?.addEventListener(type, handleEvent)
    })
    
    // 连接错误
    eventSource.onerror = (e) => {
      isConnected.value = false
      error.value = 'SSE 连接错误'
      console.error('SSE 连接错误:', e)
    }
  }

  /**
   * 断开连接
   */
  function disconnect() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    isConnected.value = false
  }

  /**
   * 注册事件处理器
   */
  function on(event: string, handler: EventHandler) {
    if (!handlers.has(event)) {
      handlers.set(event, new Set())
    }
    handlers.get(event)!.add(handler)
    
    // 返回取消注册函数
    return () => {
      handlers.get(event)?.delete(handler)
    }
  }

  /**
   * 清空 UI Blocks
   */
  function clearBlocks() {
    uiBlocks.value = []
  }

  // 组件卸载时断开连接
  onUnmounted(() => {
    disconnect()
  })

  return {
    // 状态
    isConnected,
    error,
    sessionStatus,
    progress,
    uiBlocks,
    
    // 方法
    connect,
    disconnect,
    on,
    clearBlocks,
  }
}
