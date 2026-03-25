/**
 * UI Block 渲染器 Composable
 * 将 JSON 配置映射到 Vue 组件实例
 */

import { computed, ref } from 'vue'
import type { UIBlock } from '@/vite-env.d'

// Block 组件映射类型
export type BlockComponentMap = Record<string, any>

// 默认 Block 组件映射
const defaultBlockComponents: BlockComponentMap = {
  text_block: () => import('@/components/blocks/TextBlock.vue'),
  metric_card: () => import('@/components/blocks/MetricCard.vue'),
  data_table: () => import('@/components/blocks/DataTable.vue'),
  echart_card: () => import('@/components/blocks/EchartCard.vue'),
  confirm_panel: () => import('@/components/blocks/ConfirmPanel.vue'),
  filter_form: () => import('@/components/blocks/FilterForm.vue'),
  timeline_card: () => import('@/components/blocks/TimelineCard.vue'),
  diff_card: () => import('@/components/blocks/DiffCard.vue'),
}

/**
 * UI Block 渲染器 Composable
 */
export function useBlockRenderer(customComponents?: BlockComponentMap) {
  // 合并组件映射
  const componentMap = {
    ...defaultBlockComponents,
    ...customComponents,
  }
  
  // 当前活跃的 Block
  const activeBlockId = ref<string | null>(null)
  
  // 渲染队列
  const renderQueue = ref<UIBlock[]>([])
  
  // 渲染完成计数
  const renderedCount = ref(0)

  /**
   * 获取 Block 对应的组件
   */
  function getComponent(block: UIBlock) {
    const blockType = block.block_type as string
    return componentMap[blockType] || componentMap.text_block
  }

  /**
   * 添加 Block 到渲染队列
   */
  function enqueueBlock(block: UIBlock) {
    renderQueue.value.push(block)
  }

  /**
   * 批量添加 Blocks
   */
  function enqueueBlocks(blocks: UIBlock[]) {
    blocks.forEach(block => {
      renderQueue.value.push(block)
    })
  }

  /**
   * 标记 Block 渲染完成
   */
  function markRendered(blockId: string) {
    renderedCount.value++
    
    // 从队列中移除
    const index = renderQueue.value.findIndex(
      b => (b as any).block_id === blockId
    )
    if (index >= 0) {
      renderQueue.value.splice(index, 1)
    }
  }

  /**
   * 设置活跃 Block
   */
  function setActive(block: UIBlock | null) {
    activeBlockId.value = block ? (block as any).block_id || null : null
  }

  /**
   * 清空渲染队列
   */
  function clearQueue() {
    renderQueue.value = []
    renderedCount.value = 0
    activeBlockId.value = null
  }

  /**
   * 获取 Block 的唯一 key
   */
  function getBlockKey(block: UIBlock, index: number): string {
    return `${block.block_type}_${index}_${Date.now()}`
  }

  /**
   * 计算 Block 是否需要交互
   */
  function isInteractive(block: UIBlock): boolean {
    const interactiveTypes = ['confirm_panel', 'filter_form']
    return interactiveTypes.includes(block.block_type)
  }

  /**
   * 计算 Block 优先级
   */
  function getPriority(block: UIBlock): number {
    const priorityMap: Record<string, number> = {
      text_block: 10,
      metric_card: 20,
      data_table: 30,
      echart_card: 25,
      confirm_panel: 100, // 最高优先级
      filter_form: 90,
      timeline_card: 40,
      diff_card: 50,
    }
    return priorityMap[block.block_type] || 0
  }

  /**
   * 排序 Blocks (按优先级)
   */
  function sortBlocks(blocks: UIBlock[]): UIBlock[] {
    return [...blocks].sort((a, b) => {
      // 确认面板始终在最前
      if (a.block_type === 'confirm_panel') return -1
      if (b.block_type === 'confirm_panel') return 1
      
      // 其他按优先级排序
      return getPriority(b) - getPriority(a)
    })
  }

  /**
   * 渲染进度
   */
  const renderProgress = computed(() => {
    const total = renderQueue.value.length + renderedCount.value
    if (total === 0) return 100
    return Math.round((renderedCount.value / total) * 100)
  })

  return {
    // 状态
    activeBlockId,
    renderQueue,
    renderedCount,
    renderProgress,
    
    // 方法
    getComponent,
    enqueueBlock,
    enqueueBlocks,
    markRendered,
    setActive,
    clearQueue,
    getBlockKey,
    isInteractive,
    getPriority,
    sortBlocks,
  }
}
