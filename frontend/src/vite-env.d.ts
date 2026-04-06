/// <reference types="vite/client" />

// UI Block 类型定义
export type BlockType =
  | 'text_block'
  | 'metric_card'
  | 'data_table'
  | 'echart_card'
  | 'confirm_panel'
  | 'filter_form'
  | 'timeline_card'
  | 'diff_card'

export interface UIBlock {
  block_type: BlockType
  [key: string]: any
}

export interface Project {
  id: string
  name: string
  description?: string
  base_url: string
  discovery_status: string
  discovery_progress?: number
  discovery_message?: string
  discovery_error?: string
  model_version?: string
  created_at: string
  updated_at?: string
}

export interface Session {
  id: string
  project_id: string
  title?: string
  status: string
  thread_id?: string
  created_at: string
  updated_at: string
}

export interface HttpCallRecord {
  method: string
  url: string
  status_code: number
  duration_ms?: number
}

export interface ApprovalBlock {
  block_type: 'confirm_panel'
  batch_id?: string
  items?: Array<{
    write_id: string
    route_id: string
    method: string
    path: string
    parameters: any
    reasoning: string
    safety_level: string
  }>
  approval_id?: string
  title?: string
  description?: string
  risk_level?: string
  route_id?: string
  parameters?: any
  /** 已决策状态：undefined=待决策, 'approved'=已批准, 'rejected'=已拒绝 */
  resolved_action?: 'approved' | 'rejected'
}

export interface Message {
  id: string
  /** user=用户消息, assistant=AI回复, confirmation=审批面板（嵌入消息流） */
  role: 'user' | 'assistant' | 'system' | 'confirmation'
  content: string
  thought?: string
  task_run_id?: string
  created_at: string
  metadata?: {
    http_calls?: HttpCallRecord[]
    thought?: string
    /** 审批面板数据（持久化字段） */
    approval_block?: ApprovalBlock
  }
  /** 审批面板数据（仅confirmation消息使用） */
  approvalBlock?: ApprovalBlock
}

export interface TaskRun {
  id: string
  session_id: string
  project_id: string
  user_message: string
  normalized_intent?: string
  status: string
  summary_text?: string
  error?: string
  trace_id: string
  created_at: string
}

export interface RuntimeEventItem {
  id: string
  type: string
  title: string
  detail?: string
  status?: string
  status_code?: number
  method?: string
  url?: string
  created_at: string
}

export interface SSEEvent {
  event: string
  session_id?: string
  task_run_id?: string
  [key: string]: any
}

export interface ThoughtEmittedEvent extends SSEEvent {
  token: string
}
