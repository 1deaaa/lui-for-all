import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import type { Project } from '@/vite-env.d'

export const useProjectStore = defineStore('project', () => {
  // 状态
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)
  
  // 详情数据缓存
  const currentRouteMap = ref<any>(null)
  const currentCapabilities = ref<any[]>([])
  const isDetailsLoading = ref(false)

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

  // 获取正在对话的选定项目附加详情（能力和路由图谱，后台预加载）
  async function fetchProjectDetails(id: string) {
    // 快速从 localStorage 恢复（实现刷新后瞬间可见）
    const localRouteStr = localStorage.getItem(`lui_route_map_${id}`)
    const localCapsStr = localStorage.getItem(`lui_caps_${id}`)
    
    let hasLocalData = false
    if (localRouteStr && localCapsStr) {
      try {
        currentRouteMap.value = JSON.parse(localRouteStr)
        currentCapabilities.value = JSON.parse(localCapsStr)
        hasLocalData = true
      } catch (e) {
        console.warn('解析本地缓存失败，弃用缓存')
      }
    }

    if (!hasLocalData && currentRouteMap.value?.project_id !== id) {
      // 如果没有本地缓存且内存不是当前项目，先暂且设为空，避免查看到上个项目的脏数据
      currentRouteMap.value = null
      currentCapabilities.value = []
    }

    isDetailsLoading.value = true

    // 静默发起网络请求拉取最新数据（Stale-While-Revalidate）
    try {
      const [routeRes, capRes] = await Promise.allSettled([
        axios.get(`/api/projects/${id}/route-map`),
        axios.get(`/api/projects/${id}/capabilities`)
      ])

      if (routeRes.status === 'fulfilled') {
        currentRouteMap.value = routeRes.value.data
        try {
          localStorage.setItem(`lui_route_map_${id}`, JSON.stringify(routeRes.value.data))
        } catch (err) {
          console.warn('localStorage 写入失败(可能超限):', err)
        }
      }
      if (capRes.status === 'fulfilled') {
        const caps = capRes.value.data.capabilities || []
        currentCapabilities.value = caps
        try {
          localStorage.setItem(`lui_caps_${id}`, JSON.stringify(caps))
        } catch (err) {
          console.warn('localStorage 写入失败(可能超限):', err)
        }
      }
    } catch (e: any) {
      console.error('后台加载项目详情时发生错误:', e)
    } finally {
      isDetailsLoading.value = false
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
      const response = await axios.post(`/api/projects/${projectId}/discover`)
      // 更新本地状态
      const project = projects.value.find((p) => p.id === projectId)
      if (project) {
        project.discovery_status = 'in_progress'
        project.discovery_progress = response.data.progress ?? 0
        project.discovery_message = response.data.message ?? '项目建图已启动'
      }
    } catch (e: any) {
      console.error('触发发现失败:', e)
      throw e
    }
  }

  async function deleteProject(projectId: string) {
    loading.value = true
    error.value = null
    try {
      await axios.delete(`/api/projects/${projectId}`)
      projects.value = projects.value.filter((p) => p.id !== projectId)
      if (currentProject.value?.id === projectId) {
        currentProject.value = null
      }
    } catch (e: any) {
      error.value = e.message || '删除项目失败'
      console.error('删除项目失败:', e)
      throw e
    } finally {
      loading.value = false
    }
  }


  // 修改项目描述（手动纠正 AI 总结）
  async function updateProjectDescription(projectId: string, description: string) {
    try {
      await axios.patch(`/api/projects/${projectId}`, { description })
      const project = projects.value.find((p) => p.id === projectId)
      if (project) {
        project.description = description
      }
      if (currentProject.value?.id === projectId) {
        currentProject.value.description = description
      }
    } catch (e: any) {
      console.error('更新描述失败:', e)
      throw e
    }
  }

  return {
    // 状态
    projects,
    currentProject,
    currentRouteMap,
    currentCapabilities,
    isDetailsLoading,
    loading,
    error,
    // 计算属性
    projectCount,
    // 方法
    fetchProjects,
    fetchProject,
    fetchProjectDetails,
    importProject,
    triggerDiscovery,
    deleteProject,
    updateProjectDescription,
  }
})
