/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

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
  status: string
  thread_id?: string
  created_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  thought?: string
  task_run_id?: string
  created_at: string
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
