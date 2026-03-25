import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import type { Project } from '@/vite-env.d'

export const useProjectStore = defineStore('project', () => {
  // 状态
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 计算属性
  const projectCount = computed(() => projects.value.length)

  // 获取项目列表
  async function fetchProjects() {
    loading.value = true
    error.value = null
    try {
      const response = await axios.get('/api/projects/')
      projects.value = response.data.projects || []
    } catch (e: any) {
      error.value = e.message || '获取项目列表失败'
      console.error('获取项目列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  // 获取单个项目（优先从列表缓存命中，避免不必要的 API 调用和字段缺失风险）
  async function fetchProject(id: string) {
    // 先查内存缓存
    const cached = projects.value.find((p) => p.id === id)
    if (cached) {
      currentProject.value = cached
      return cached
    }
    // 缓存未命中时才请求接口
    loading.value = true
    error.value = null
    try {
      const response = await axios.get(`/api/projects/${id}/status`)
      const p: Project = {
        id,
        name: response.data.name || '\u672a知项目',
        discovery_status: response.data.status,
        base_url: response.data.base_url || '',
        created_at: new Date().toISOString(),
      }
      currentProject.value = p
      return p
    } catch (e: any) {
      error.value = e.message || '获取项目失败'
      console.error('获取项目失败:', e)
    } finally {
      loading.value = false
    }
  }

  // 导入新项目
  async function importProject(data: {
    name: string
    base_url: string
    openapi_url?: string
    description?: string
  }) {
    loading.value = true
    error.value = null
    try {
      const response = await axios.post('/api/projects/import', data)
      const newProject: Project = {
        id: response.data.project_id,
        name: response.data.name,
        discovery_status: response.data.status,
        base_url: data.base_url,
        created_at: new Date().toISOString(),
      }
      projects.value.unshift(newProject)
      return newProject
    } catch (e: any) {
      error.value = e.message || '导入项目失败'
      console.error('导入项目失败:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  // 触发项目发现
  async function triggerDiscovery(projectId: string) {
    try {
      await axios.post(`/api/projects/${projectId}/discover`)
      // 更新本地状态
      const project = projects.value.find((p) => p.id === projectId)
      if (project) {
        project.discovery_status = 'in_progress'
      }
    } catch (e: any) {
      console.error('触发发现失败:', e)
      throw e
    }
  }

  return {
    // 状态
    projects,
    currentProject,
    loading,
    error,
    // 计算属性
    projectCount,
    // 方法
    fetchProjects,
    fetchProject,
    importProject,
    triggerDiscovery,
  }
})
